#!/usr/bin/env python3
"""Publish and reconcile PR previews in a dedicated Pages repository."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import stat
import struct
import zipfile
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse


PREVIEW_MARKER = "pages-pr-preview-banner"
CLEANUP_STATE_NAME = ".preview-cleanups.json"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
PREVIEW_DIR_RE = re.compile(r"^pr-([1-9][0-9]*)$")
CLEANUP_ATTEMPT_RE = re.compile(r"^[1-9][0-9]*-[1-9][0-9]*$")
MAX_FILES = 10_000
MAX_BYTES = 250 * 1024 * 1024
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_COMPRESSION_RATIO = 500
ALLOWED_SUFFIXES = {
    ".css",
    ".gif",
    ".htm",
    ".html",
    ".ico",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".mjs",
    ".otf",
    ".png",
    ".svg",
    ".ttf",
    ".txt",
    ".webmanifest",
    ".webp",
    ".woff",
    ".woff2",
    ".xml",
}
ALLOWED_EXTENSIONLESS = {".nojekyll"}
SENSITIVE_NAMES = {
    ".env",
    ".npmrc",
    ".pypirc",
    "id_dsa",
    "id_ed25519",
    "id_ecdsa",
    "id_rsa",
}
SENSITIVE_SUFFIXES = {
    ".7z",
    ".bak",
    ".db",
    ".gz",
    ".key",
    ".p12",
    ".pem",
    ".pfx",
    ".sqlite",
    ".sqlite3",
    ".tar",
    ".tgz",
    ".zip",
}
PRIVATE_KEY_MARKERS = (
    b"-----BEGIN PRIVATE KEY-----",
    b"-----BEGIN ENCRYPTED PRIVATE KEY-----",
    b"-----BEGIN RSA PRIVATE KEY-----",
    b"-----BEGIN EC PRIVATE KEY-----",
    b"-----BEGIN DSA PRIVATE KEY-----",
    b"-----BEGIN OPENSSH PRIVATE KEY-----",
    b"-----BEGIN PGP PRIVATE KEY BLOCK-----",
    b"PuTTY-User-Key-File-",
)
CSS_ROOT_TOKEN = r"(?:/|\\/|\\(?:0{0,4}2f)(?:[ \t\r\n\f]?))"
CSS_ROOT_URL_RE = re.compile(
    rf"(?:url\(\s*['\"]?\s*{CSS_ROOT_TOKEN}|"
    rf"@import\s+(?:url\(\s*)?['\"]?\s*{CSS_ROOT_TOKEN})",
    re.IGNORECASE,
)
JS_ROOT_URL_RE = re.compile(
    r"(?:\bfetch|\bimportScripts|\bimport|\bopen)\s*\(\s*['\"`]\s*/|"
    r"\bnew\s+(?:EventSource|URL|WebSocket)\s*\(\s*['\"`]\s*/|"
    r"\bnew\s+(?:SharedWorker|Worker)\s*\(\s*['\"`]\s*/|"
    r"\.open\s*\(\s*[^,\n]{1,160},\s*['\"`]\s*/|"
    r"\b(?:import|export)\s+(?:[^;\n]*?\s+from\s*)?['\"]\s*/|"
    r"\blocation(?:\.href)?\s*=\s*['\"`]\s*/|"
    r"\blocation\.(?:assign|replace)\s*\(\s*['\"`]\s*/",
    re.IGNORECASE,
)
URL_ATTRIBUTES = {
    "action",
    "background",
    "cite",
    "data",
    "formaction",
    "href",
    "manifest",
    "poster",
    "src",
}


class NewerPreviewPresent(ValueError):
    """Raised when an older workflow operation must not replace newer output."""


def _is_root_relative(value: str | None) -> bool:
    return value is not None and value.lstrip().startswith("/")


class _PreviewHTMLValidator(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.problem: str | None = None
        self._style_depth = 0

    def _check_tag(self, tag: str, attributes: list[tuple[str, str | None]]) -> None:
        normalized = tag.casefold()
        values = {name.casefold(): value for name, value in attributes}
        if normalized == "base":
            self.problem = self.problem or "<base> element"
        for name, value in values.items():
            local_name = name.rsplit(":", 1)[-1]
            if name == "xml:base":
                self.problem = self.problem or "xml:base attribute"
            if local_name in URL_ATTRIBUTES and _is_root_relative(value):
                self.problem = self.problem or f"root-relative {name}"
            if name == "srcset" and value is not None:
                candidates = [part.strip().split()[0] for part in value.split(",") if part.strip()]
                if any(_is_root_relative(candidate) for candidate in candidates):
                    self.problem = self.problem or "root-relative srcset"
            if name == "srcdoc":
                self.problem = self.problem or "embedded srcdoc"
            if value is not None and CSS_ROOT_URL_RE.search(value):
                self.problem = self.problem or f"root-relative CSS URL in {name}"
        if normalized == "meta" and (values.get("http-equiv") or "").casefold() == "refresh":
            content = values.get("content") or ""
            if re.search(r"(?:^|;)\s*url\s*=\s*['\"]?\s*/", content, flags=re.IGNORECASE):
                self.problem = self.problem or "root-relative meta refresh"
        if normalized == "style":
            self._style_depth += 1

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._check_tag(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._check_tag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "style" and self._style_depth:
            self._style_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._style_depth and CSS_ROOT_URL_RE.search(data):
            self.problem = self.problem or "root-relative stylesheet URL"


def _manifest_has_root_url(value: object, key: str | None = None) -> bool:
    if isinstance(value, dict):
        return any(_manifest_has_root_url(item, str(name)) for name, item in value.items())
    if isinstance(value, list):
        return any(_manifest_has_root_url(item, key) for item in value)
    return (
        isinstance(value, str)
        and key in {"action", "id", "scope", "src", "start_url", "url"}
        and _is_root_relative(value)
    )


def _validate_subpath_content(path: Path) -> None:
    suffix = path.suffix.casefold()
    if suffix not in {".css", ".htm", ".html", ".js", ".mjs", ".svg", ".webmanifest"}:
        return
    source = path.read_text(encoding="utf-8")
    if suffix in {".htm", ".html", ".svg"}:
        validator = _PreviewHTMLValidator()
        validator.feed(source)
        validator.close()
        if validator.problem is not None:
            raise ValueError(f"preview content is unsafe under /pr-N/ ({validator.problem}): {path}")
        if JS_ROOT_URL_RE.search(source):
            raise ValueError(f"preview content contains a root-relative script URL: {path}")
    elif suffix == ".css" and CSS_ROOT_URL_RE.search(source):
        raise ValueError(f"preview stylesheet contains a root-relative URL: {path}")
    elif suffix in {".js", ".mjs"} and JS_ROOT_URL_RE.search(source):
        raise ValueError(f"preview script contains a root-relative URL: {path}")
    elif suffix == ".webmanifest":
        try:
            manifest = json.loads(source)
        except json.JSONDecodeError as error:
            raise ValueError(f"preview web manifest is invalid JSON: {path}") from error
        if _manifest_has_root_url(manifest):
            raise ValueError(f"preview web manifest contains a root-relative URL: {path}")


def _read_zip_entry_count(archive: Path) -> int:
    """Count raw central-directory records before zipfile allocates ZipInfo objects."""

    archive_bytes = archive.stat().st_size
    tail_bytes = min(archive_bytes, 22 + 65_535)
    with archive.open("rb") as stream:
        stream.seek(archive_bytes - tail_bytes)
        tail = stream.read(tail_bytes)
    signature = b"PK\x05\x06"
    offset = tail.rfind(signature)
    if offset < 0 or offset + 22 > len(tail):
        raise ValueError("preview archive has no valid ZIP end record")
    (
        _,
        disk_number,
        central_disk,
        entries_on_disk,
        total_entries,
        central_bytes,
        central_offset,
        comment_bytes,
    ) = struct.unpack_from("<4s4H2LH", tail, offset)
    if offset + 22 + comment_bytes != len(tail):
        raise ValueError("preview archive contains trailing or malformed data")
    if disk_number != 0 or central_disk != 0 or entries_on_disk != total_entries:
        raise ValueError("multi-disk preview archives are not accepted")
    if total_entries == 0xFFFF or central_bytes == 0xFFFFFFFF or central_offset == 0xFFFFFFFF:
        raise ValueError("ZIP64 preview archives are not accepted")
    eocd_offset = archive_bytes - tail_bytes + offset
    central_end = central_offset + central_bytes
    if central_end != eocd_offset:
        raise ValueError("preview archive central directory is out of bounds")

    actual_entries = 0
    cursor = central_offset
    with archive.open("rb") as stream:
        stream.seek(central_offset)
        while cursor < central_end:
            fixed = stream.read(46)
            if len(fixed) != 46 or fixed[:4] != b"PK\x01\x02":
                raise ValueError("preview archive has a malformed central directory")
            (
                _,
                _,
                _,
                _,
                _,
                _,
                _,
                _,
                compressed_bytes,
                uncompressed_bytes,
                filename_bytes,
                extra_bytes,
                entry_comment_bytes,
                entry_disk,
                _,
                _,
                local_header_offset,
            ) = struct.unpack("<4s6H3L5H2L", fixed)
            variable_bytes = filename_bytes + extra_bytes + entry_comment_bytes
            cursor += 46 + variable_bytes
            if cursor > central_end or len(stream.read(variable_bytes)) != variable_bytes:
                raise ValueError("preview archive has a truncated central directory")
            if entry_disk != 0 or local_header_offset >= central_offset:
                raise ValueError("preview archive central directory is invalid")
            if compressed_bytes == 0xFFFFFFFF or uncompressed_bytes == 0xFFFFFFFF:
                raise ValueError("ZIP64 preview archives are not accepted")
            actual_entries += 1
            if actual_entries > MAX_FILES + 1_000:
                raise ValueError("preview archive has an invalid number of entries")
    if cursor != central_end or actual_entries != total_entries:
        raise ValueError("preview archive entry count does not match its central directory")
    return actual_entries


def _validate_pr_number(pr_number: int) -> None:
    if pr_number < 1:
        raise ValueError("PR number must be positive")


def _validate_sha(head_sha: str) -> None:
    if not SHA_RE.fullmatch(head_sha):
        raise ValueError("head SHA must be a 40-character lowercase hexadecimal commit SHA")


def _validate_repository(source_repository: str) -> None:
    if not REPOSITORY_RE.fullmatch(source_repository):
        raise ValueError("source repository must use owner/name format")


def _validate_base_url(preview_base_url: str) -> str:
    parsed = urlparse(preview_base_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("preview base URL must be an HTTPS origin/path without query or fragment")
    return preview_base_url.rstrip("/")


def _validate_site(root: Path) -> list[Path]:
    if root.is_symlink():
        raise ValueError(f"preview artifact root must not be a symlink: {root}")
    if not root.is_dir() or not (root / "index.html").is_file():
        raise ValueError(f"preview artifact must contain a site/index.html: {root}")

    files: list[Path] = []
    total_bytes = 0
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(
            part.casefold() == ".git" or any(ord(character) < 32 or ord(character) == 127 for character in part)
            for part in relative.parts
        ):
            raise ValueError(f"preview artifact contains a forbidden path: {relative}")
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError(f"preview artifact contains a symlink: {relative}")
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError(f"preview artifact contains a non-regular file: {relative}")
        if path.lstat().st_nlink != 1:
            raise ValueError(f"preview artifact contains a hard-linked file: {relative}")
        if mode & 0o111:
            raise ValueError(f"preview artifact contains an executable file: {relative}")
        basename = path.name.casefold()
        suffix = path.suffix.casefold()
        if (
            basename in SENSITIVE_NAMES
            or suffix in SENSITIVE_SUFFIXES
            or (suffix not in ALLOWED_SUFFIXES and basename not in ALLOWED_EXTENSIONLESS)
        ):
            raise ValueError(f"preview artifact contains a forbidden file type: {relative}")
        file_bytes = path.stat().st_size
        if file_bytes > MAX_FILE_BYTES:
            raise ValueError(f"preview artifact contains an oversized file: {relative}")
        carry = b""
        with path.open("rb") as stream:
            while chunk := stream.read(64 * 1024):
                sample = carry + chunk
                if any(marker in sample for marker in PRIVATE_KEY_MARKERS):
                    raise ValueError(f"preview artifact contains private-key material: {relative}")
                carry = sample[-64:]
        _validate_subpath_content(path)
        files.append(path)
        total_bytes += file_bytes
        if len(files) > MAX_FILES or total_bytes > MAX_BYTES:
            raise ValueError("preview artifact exceeds the file-count or byte-size limit")
    return files


def _safe_archive_parts(filename: str) -> tuple[str, ...]:
    if not filename or "\\" in filename or any(
        ord(character) < 32 or ord(character) == 127 for character in filename
    ):
        raise ValueError(f"preview archive contains a forbidden path: {filename!r}")
    path = PurePosixPath(filename)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"preview archive contains an unsafe path: {filename}")
    if any(part.casefold() == ".git" for part in path.parts):
        raise ValueError(f"preview archive contains a forbidden path: {filename}")
    return path.parts


def extract_preview_archive(archive_path: Path, destination: Path) -> Path:
    """Validate a GitHub artifact ZIP before extracting its static site."""

    archive = archive_path.absolute()
    target_root = destination.absolute()
    if not archive.is_file() or archive.is_symlink():
        raise ValueError(f"preview archive is not a regular file: {archive}")
    if archive.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("compressed preview artifact exceeds the byte-size limit")
    if target_root.exists() or target_root.is_symlink():
        raise ValueError(f"preview extraction destination must not exist: {target_root}")

    declared_entries = _read_zip_entry_count(archive)
    if declared_entries < 1 or declared_entries > MAX_FILES + 1_000:
        raise ValueError("preview archive has an invalid number of entries")

    seen: set[tuple[str, ...]] = set()
    total_bytes = 0
    try:
        with zipfile.ZipFile(archive) as bundle:
            entries = bundle.infolist()
            if len(entries) != declared_entries:
                raise ValueError("preview archive has an invalid number of entries")
            validated: list[tuple[zipfile.ZipInfo, tuple[str, ...]]] = []
            for entry in entries:
                parts = _safe_archive_parts(entry.filename.rstrip("/"))
                if parts in seen:
                    raise ValueError(f"preview archive contains a duplicate path: {entry.filename}")
                seen.add(parts)
                if entry.flag_bits & 0x1:
                    raise ValueError("encrypted preview archives are not accepted")
                unix_mode = entry.external_attr >> 16
                file_type = stat.S_IFMT(unix_mode)
                if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
                    raise ValueError(f"preview archive contains a non-regular entry: {entry.filename}")
                if entry.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                    raise ValueError(f"preview archive uses an unsupported compression: {entry.filename}")
                if entry.file_size > MAX_FILE_BYTES:
                    raise ValueError(f"preview archive contains an oversized entry: {entry.filename}")
                if entry.file_size and entry.file_size / max(entry.compress_size, 1) > MAX_COMPRESSION_RATIO:
                    raise ValueError(f"preview archive contains an excessive compression ratio: {entry.filename}")
                total_bytes += entry.file_size
                if total_bytes > MAX_BYTES:
                    raise ValueError("preview archive exceeds the uncompressed byte-size limit")
                validated.append((entry, parts))

            target_root.mkdir(parents=True)
            try:
                for entry, parts in validated:
                    target = target_root.joinpath(*parts)
                    if entry.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    written = 0
                    with bundle.open(entry) as source, target.open("xb") as output:
                        while chunk := source.read(64 * 1024):
                            written += len(chunk)
                            if written > entry.file_size or written > MAX_FILE_BYTES:
                                raise ValueError(f"preview archive entry expanded past its declared size: {entry.filename}")
                            output.write(chunk)
                    if written != entry.file_size:
                        raise ValueError(f"preview archive entry size mismatch: {entry.filename}")
            except Exception:
                shutil.rmtree(target_root, ignore_errors=True)
                raise
    except zipfile.BadZipFile as error:
        raise ValueError("preview archive is not a valid ZIP file") from error

    site = target_root / "site"
    try:
        _validate_site(site)
    except Exception:
        shutil.rmtree(target_root, ignore_errors=True)
        raise
    return site


def _validate_repository_root(repository_root: Path) -> Path:
    root = repository_root.resolve()
    if root == Path(root.anchor) or not (root / ".git").exists():
        raise ValueError(f"preview repository root is not a Git checkout: {root}")
    return root


def _inject_preview_notice(
    page: Path,
    pr_number: int,
    head_sha: str,
    source_repository: str,
) -> None:
    source = page.read_text(encoding="utf-8")
    if PREVIEW_MARKER in source:
        raise ValueError(f"HTML contains the reserved preview marker: {page}")

    pr_url = f"https://github.com/{source_repository}/pull/{pr_number}"
    head_extra = f"""
<meta name="robots" content="noindex,nofollow,noarchive">
<style id="{PREVIEW_MARKER}">
  html {{ scroll-padding-top: 44px; }}
  body {{ padding-top: 44px !important; }}
  .pages-pr-preview {{
    position: fixed; inset: 0 0 auto 0; z-index: 2147483647;
    min-height: 44px; box-sizing: border-box; padding: 10px 18px;
    background: #7c2d12; color: #fff; text-align: center;
    font: 700 14px/24px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    box-shadow: 0 2px 8px rgba(0,0,0,.2);
  }}
  .pages-pr-preview a {{ color: #fff; text-decoration: underline; }}
</style>"""
    banner = (
        '<div class="pages-pr-preview" role="status">'
        f'미리보기 · PR #{pr_number} · 운영 사이트 아님 · {html.escape(head_sha[:12])} · '
        f'<a href="{html.escape(pr_url, quote=True)}">PR에서 검토하기</a>'
        "</div>"
    )

    with_head = re.sub(
        r"(<head(?:\s[^>]*)?>)",
        lambda match: match.group(1) + head_extra,
        source,
        count=1,
        flags=re.IGNORECASE,
    )
    if with_head == source:
        raise ValueError(f"HTML has no <head>: {page}")
    with_body = re.sub(
        r"(<body(?:\s[^>]*)?>)",
        lambda match: match.group(1) + banner,
        with_head,
        count=1,
        flags=re.IGNORECASE,
    )
    if with_body == with_head:
        raise ValueError(f"HTML has no <body>: {page}")
    page.write_text(with_body, encoding="utf-8")


def _read_manifest(preview_dir: Path) -> dict[str, object] | None:
    manifest_path = preview_dir / "preview-manifest.json"
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    pr_number = value.get("pullRequest")
    head_sha = value.get("headSha")
    workflow_run_id = value.get("workflowRunId")
    workflow_run_attempt = value.get("workflowRunAttempt")
    if (
        not isinstance(pr_number, int)
        or pr_number < 1
        or not isinstance(head_sha, str)
        or not SHA_RE.fullmatch(head_sha)
        or not isinstance(workflow_run_id, int)
        or workflow_run_id < 1
        or not isinstance(workflow_run_attempt, int)
        or workflow_run_attempt < 1
    ):
        return None
    return value


def _write_repository_index(repository_root: Path, preview_base_url: str) -> None:
    entries: list[tuple[int, str]] = []
    for candidate in repository_root.iterdir():
        match = PREVIEW_DIR_RE.fullmatch(candidate.name)
        if not match or not candidate.is_dir():
            continue
        manifest = _read_manifest(candidate)
        if manifest is None:
            continue
        pr_number = int(manifest["pullRequest"])
        if pr_number != int(match.group(1)):
            continue
        head_sha = str(manifest["headSha"])
        entries.append((pr_number, head_sha))
    entries.sort()

    if entries:
        links = "\n".join(
            f'<li><a href="{html.escape(preview_base_url, quote=True)}/pr-{number}/">'
            f'PR #{number}</a> <code>{html.escape(head_sha[:12])}</code></li>'
            for number, head_sha in entries
        )
    else:
        links = "<li>현재 게시된 미리보기가 없습니다.</li>"

    index = f"""<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<title>overseas-procurement-100 PR previews</title>
<style>body{{max-width:760px;margin:60px auto;padding:0 20px;font:16px/1.7 system-ui,sans-serif;color:#20242b}}code{{color:#667085}}</style>
</head><body>
<h1>Pull Request 미리보기</h1>
<p>검토 전용 사이트입니다. 운영 사이트가 아닙니다.</p>
<ul>{links}</ul>
</body></html>
"""
    (repository_root / "index.html").write_text(index, encoding="utf-8")
    (repository_root / ".nojekyll").write_text("", encoding="utf-8")
    (repository_root / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")


def publish_preview(
    source_site: Path,
    repository_root: Path,
    pr_number: int,
    head_sha: str,
    workflow_run_id: int,
    workflow_run_attempt: int,
    source_repository: str,
    preview_base_url: str,
) -> Path:
    _validate_pr_number(pr_number)
    _validate_sha(head_sha)
    _validate_repository(source_repository)
    if workflow_run_id < 1:
        raise ValueError("workflow run ID must be positive")
    if workflow_run_attempt < 1:
        raise ValueError("workflow run attempt must be positive")
    base_url = _validate_base_url(preview_base_url)
    source = source_site.absolute()
    files = _validate_site(source)
    root = _validate_repository_root(repository_root)

    destination = root / f"pr-{pr_number}"
    if destination.exists():
        if not destination.is_dir() or destination.is_symlink():
            raise ValueError(f"refusing to replace unexpected preview path: {destination}")
        current = _read_manifest(destination)
        current_order = (
            int(current["workflowRunId"]),
            int(current["workflowRunAttempt"]),
        ) if current is not None else None
        if current_order is not None and current_order > (workflow_run_id, workflow_run_attempt):
            raise NewerPreviewPresent(
                "refusing to replace a preview created by a newer workflow run "
                f"({current_order} > {(workflow_run_id, workflow_run_attempt)})"
            )
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    for source_file in files:
        relative = source_file.relative_to(source)
        if relative.suffix.lower() in {".htm", ".html"}:
            _inject_preview_notice(destination / relative, pr_number, head_sha, source_repository)

    manifest = {
        "pullRequest": pr_number,
        "headSha": head_sha,
        "workflowRunId": workflow_run_id,
        "workflowRunAttempt": workflow_run_attempt,
        "sourceRepository": source_repository,
    }
    (destination / "preview-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    cleanup_pending = [number for number in _read_cleanup_state(root) if number != pr_number]
    _write_cleanup_state(
        root,
        cleanup_pending,
        f"{workflow_run_id}-{workflow_run_attempt}",
    )
    _write_repository_index(root, base_url)
    return destination


def remove_preview(
    repository_root: Path,
    pr_number: int,
    preview_base_url: str,
    max_workflow_run_id: int | None = None,
    max_workflow_run_attempt: int | None = None,
) -> str:
    _validate_pr_number(pr_number)
    if (max_workflow_run_id is None) != (max_workflow_run_attempt is None):
        raise ValueError("maximum workflow run ID and attempt must be provided together")
    if max_workflow_run_id is not None and (
        max_workflow_run_id < 1 or max_workflow_run_attempt is None or max_workflow_run_attempt < 1
    ):
        raise ValueError("maximum workflow run ID and attempt must be positive")
    base_url = _validate_base_url(preview_base_url)
    root = _validate_repository_root(repository_root)
    destination = root / f"pr-{pr_number}"
    existed = destination.exists()
    if existed:
        if not destination.is_dir() or destination.is_symlink():
            raise ValueError(f"refusing to remove unexpected preview path: {destination}")
        current = _read_manifest(destination)
        if max_workflow_run_id is not None and current is not None:
            current_order = (int(current["workflowRunId"]), int(current["workflowRunAttempt"]))
            maximum_order = (max_workflow_run_id, int(max_workflow_run_attempt))
            if current_order > maximum_order:
                return "newer-present"
        shutil.rmtree(destination)
    if max_workflow_run_id is not None and max_workflow_run_attempt is not None:
        cleanup_pending = sorted(set(_read_cleanup_state(root)) | {pr_number})
        _write_cleanup_state(
            root,
            cleanup_pending,
            f"{max_workflow_run_id}-{max_workflow_run_attempt}",
        )
    _write_repository_index(root, base_url)
    return "removed" if existed else "absent"


def reconcile_previews(
    repository_root: Path,
    expected_previews: dict[int, str],
    source_repository: str,
    preview_base_url: str,
) -> list[int]:
    """Remove previews that do not match an open PR's current head commit."""

    _validate_repository(source_repository)
    for pr_number, head_sha in expected_previews.items():
        _validate_pr_number(pr_number)
        _validate_sha(head_sha)
    base_url = _validate_base_url(preview_base_url)
    root = _validate_repository_root(repository_root)
    removed: list[int] = []
    for candidate in sorted(root.iterdir(), key=lambda path: path.name):
        match = PREVIEW_DIR_RE.fullmatch(candidate.name)
        if match is None:
            continue
        pr_number = int(match.group(1))
        if not candidate.is_dir() or candidate.is_symlink():
            raise ValueError(f"refusing to remove unexpected preview path: {candidate}")
        manifest = _read_manifest(candidate)
        expected_sha = expected_previews.get(pr_number)
        if (
            expected_sha is not None
            and manifest is not None
            and manifest.get("pullRequest") == pr_number
            and manifest.get("headSha") == expected_sha
            and manifest.get("sourceRepository") == source_repository
        ):
            continue
        shutil.rmtree(candidate)
        removed.append(pr_number)
    _write_repository_index(root, base_url)
    return removed


def _active_preview_state(repository_root: Path) -> dict[str, str]:
    active: dict[str, str] = {}
    for candidate in repository_root.iterdir():
        match = PREVIEW_DIR_RE.fullmatch(candidate.name)
        manifest = _read_manifest(candidate) if match is not None and candidate.is_dir() else None
        if match is not None and manifest is not None:
            active[str(int(match.group(1)))] = str(manifest["headSha"])
    return dict(sorted(active.items(), key=lambda item: int(item[0])))


def _parse_expected_preview_json(value: str) -> dict[int, str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError("open PR list must be valid JSON") from error
    if not isinstance(parsed, dict):
        raise ValueError("open PR list must be a JSON object of PR numbers and head SHAs")
    if len(parsed) > 10_000:
        raise ValueError("open PR list is unexpectedly large")
    expected: dict[int, str] = {}
    for raw_number, head_sha in parsed.items():
        if not isinstance(raw_number, str) or not raw_number.isascii() or not raw_number.isdigit():
            raise ValueError("open PR keys must be positive decimal integers")
        pr_number = int(raw_number)
        _validate_pr_number(pr_number)
        if not isinstance(head_sha, str):
            raise ValueError("open PR values must be commit SHAs")
        _validate_sha(head_sha)
        expected[pr_number] = head_sha
    return expected


def _parse_cleanup_numbers_json(value: str) -> list[int]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError("pending cleanup list must be valid JSON") from error
    if not isinstance(parsed, list) or len(parsed) > 10_000:
        raise ValueError("pending cleanup list must be a bounded JSON array")
    numbers: set[int] = set()
    for number in parsed:
        if not isinstance(number, int) or isinstance(number, bool):
            raise ValueError("pending cleanup entries must be PR numbers")
        _validate_pr_number(number)
        numbers.add(number)
    return sorted(numbers)


def _read_cleanup_state(repository_root: Path) -> list[int]:
    root = _validate_repository_root(repository_root)
    path = root / CLEANUP_STATE_NAME
    if not path.exists() and not path.is_symlink():
        return []
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"refusing unexpected cleanup state path: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("cleanup state must be valid JSON") from error
    if not isinstance(value, dict) or set(value) != {"pullRequests", "attempt"}:
        raise ValueError("cleanup state has an invalid schema")
    if not isinstance(value["attempt"], str) or not CLEANUP_ATTEMPT_RE.fullmatch(value["attempt"]):
        raise ValueError("cleanup state has an invalid attempt")
    return _parse_cleanup_numbers_json(json.dumps(value["pullRequests"]))


def _write_cleanup_state(repository_root: Path, pr_numbers: list[int], attempt: str) -> None:
    if not CLEANUP_ATTEMPT_RE.fullmatch(attempt):
        raise ValueError("cleanup attempt must use workflow-run-id/workflow-run-attempt numbers")
    root = _validate_repository_root(repository_root)
    path = root / CLEANUP_STATE_NAME
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"refusing unexpected cleanup state path: {path}")
    if pr_numbers:
        path.write_text(
            json.dumps(
                {"pullRequests": sorted(set(pr_numbers)), "attempt": attempt},
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
    elif path.exists():
        path.unlink()


def _write_json_result(path: Path | None, value: object) -> None:
    if path is not None:
        path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    publish = subparsers.add_parser("publish")
    publish.add_argument("--source-site", type=Path, required=True)
    publish.add_argument("--repository-root", type=Path, required=True)
    publish.add_argument("--pr-number", type=int, required=True)
    publish.add_argument("--head-sha", required=True)
    publish.add_argument("--workflow-run-id", type=int, required=True)
    publish.add_argument("--workflow-run-attempt", type=int, required=True)
    publish.add_argument("--source-repository", required=True)
    publish.add_argument("--preview-base-url", required=True)
    publish.add_argument("--result-output", type=Path)

    remove = subparsers.add_parser("remove")
    remove.add_argument("--repository-root", type=Path, required=True)
    remove.add_argument("--pr-number", type=int, required=True)
    remove.add_argument("--preview-base-url", required=True)
    remove.add_argument("--max-workflow-run-id", type=int)
    remove.add_argument("--max-workflow-run-attempt", type=int)
    remove.add_argument("--result-output", type=Path)

    reconcile = subparsers.add_parser("reconcile")
    reconcile.add_argument("--repository-root", type=Path, required=True)
    reconcile.add_argument("--expected-previews-json", required=True)
    reconcile.add_argument("--source-repository", required=True)
    reconcile.add_argument("--preview-base-url", required=True)
    reconcile.add_argument("--pending-cleanups-json", default="[]")
    reconcile.add_argument("--completed-cleanups-json", default="[]")
    reconcile.add_argument("--cleanup-attempt", required=True)
    reconcile.add_argument("--state-output", type=Path)

    extract = subparsers.add_parser("extract")
    extract.add_argument("--archive", type=Path, required=True)
    extract.add_argument("--destination", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "publish":
        try:
            path = publish_preview(
                args.source_site,
                args.repository_root,
                args.pr_number,
                args.head_sha,
                args.workflow_run_id,
                args.workflow_run_attempt,
                args.source_repository,
                args.preview_base_url,
            )
        except NewerPreviewPresent as error:
            _write_json_result(
                args.result_output,
                {"metadataAllowed": False, "reason": "newer-preview-present"},
            )
            print(f"OK: skipped stale preview publication: {error}")
        else:
            _write_json_result(
                args.result_output,
                {"metadataAllowed": True, "reason": "published"},
            )
            print(f"OK: published preview files at {path}")
    elif args.command == "remove":
        outcome = remove_preview(
            args.repository_root,
            args.pr_number,
            args.preview_base_url,
            args.max_workflow_run_id,
            args.max_workflow_run_attempt,
        )
        _write_json_result(
            args.result_output,
            {
                "metadataAllowed": outcome != "newer-present",
                "reason": outcome,
            },
        )
        print(f"OK: preview removal outcome is {outcome}")
    elif args.command == "reconcile":
        expected = _parse_expected_preview_json(args.expected_previews_json)
        removed = reconcile_previews(
            args.repository_root,
            expected,
            args.source_repository,
            args.preview_base_url,
        )
        active = _active_preview_state(args.repository_root)
        missing = {
            str(number): sha
            for number, sha in sorted(expected.items())
            if active.get(str(number)) != sha
        }
        cleanup_pending = sorted(
            set(_parse_cleanup_numbers_json(args.pending_cleanups_json)) | set(removed)
        )
        cleanup_completed = sorted(
            set(_parse_cleanup_numbers_json(args.completed_cleanups_json))
            - set(cleanup_pending)
        )
        _write_cleanup_state(args.repository_root, cleanup_pending, args.cleanup_attempt)
        _write_json_result(
            args.state_output,
            {
                "active": active,
                "cleanupCompleted": cleanup_completed,
                "cleanupPending": cleanup_pending,
                "missing": missing,
                "removed": removed,
            },
        )
        print(f"OK: reconciled previews; removed {len(removed)}")
    else:
        site = extract_preview_archive(args.archive, args.destination)
        print(f"OK: safely extracted preview site at {site}")


if __name__ == "__main__":
    main()
