#!/usr/bin/env python3
"""Regression checks for the dedicated Pages preview publisher."""

from __future__ import annotations

import json
import os
import stat
import struct
import tempfile
import warnings
import zipfile
from pathlib import Path

from publish_pages_preview import (
    CLEANUP_STATE_NAME,
    NewerPreviewPresent,
    PREVIEW_MARKER,
    _parse_cleanup_numbers_json,
    _read_cleanup_state,
    _write_cleanup_state,
    extract_preview_archive,
    publish_preview,
    reconcile_previews,
    remove_preview,
)


HTML = "<!doctype html><html><head><title>T</title></head><body><a href='nested/page.html'>go</a></body></html>"
SHA_1 = "a" * 40
SHA_2 = "b" * 40
BASE_URL = "https://example.github.io/previews"
SOURCE_REPOSITORY = "example/source"


def make_site(root: Path, label: str) -> None:
    (root / "nested").mkdir(parents=True)
    (root / "index.html").write_text(HTML.replace("T", label), encoding="utf-8")
    (root / "nested" / "page.html").write_text(
        HTML.replace("T", f"{label} nested"), encoding="utf-8"
    )
    (root / "asset.txt").write_text(label, encoding="utf-8")


def publish(
    source: Path,
    repository: Path,
    pr_number: int,
    head_sha: str,
    run_id: int,
    run_attempt: int = 1,
) -> Path:
    return publish_preview(
        source,
        repository,
        pr_number,
        head_sha,
        run_id,
        run_attempt,
        SOURCE_REPOSITORY,
        BASE_URL,
    )


def expect_rejected(source: Path, repository: Path, message: str) -> None:
    try:
        publish(source, repository, 99, SHA_1, 9900)
    except ValueError as error:
        assert message in str(error), error
    else:
        raise AssertionError(f"unsafe preview was not rejected: {message}")


def main() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        source = base / "source"
        repository = base / "repository"
        make_site(source, "preview")
        (source / "legacy.htm").write_text(HTML.replace("T", "legacy"), encoding="utf-8")
        (repository / ".git").mkdir(parents=True)
        assert _parse_cleanup_numbers_json("[43, 42, 43]") == [42, 43]
        _write_cleanup_state(repository, [43, 42], "9000-1")
        assert json.loads((repository / CLEANUP_STATE_NAME).read_text(encoding="utf-8")) == {
            "pullRequests": [42, 43],
            "attempt": "9000-1",
        }
        _write_cleanup_state(repository, [], "9001-1")
        assert not (repository / CLEANUP_STATE_NAME).exists()
        source_before = {
            path.relative_to(source): path.read_bytes()
            for path in source.rglob("*")
            if path.is_file()
        }

        preview_42 = publish(source, repository, 42, SHA_1, 9001)
        rendered = (preview_42 / "index.html").read_text(encoding="utf-8")
        assert PREVIEW_MARKER in rendered
        assert "noindex,nofollow,noarchive" in rendered
        assert "PR #42" in rendered
        assert SHA_1[:12] in rendered
        assert "https://github.com/example/source/pull/42" in rendered
        assert PREVIEW_MARKER in (preview_42 / "legacy.htm").read_text(encoding="utf-8")
        assert (preview_42 / "asset.txt").read_text(encoding="utf-8") == "preview"
        assert source_before == {
            path.relative_to(source): path.read_bytes()
            for path in source.rglob("*")
            if path.is_file()
        }
        manifest = json.loads((preview_42 / "preview-manifest.json").read_text(encoding="utf-8"))
        assert manifest == {
            "pullRequest": 42,
            "headSha": SHA_1,
            "workflowRunId": 9001,
            "workflowRunAttempt": 1,
            "sourceRepository": SOURCE_REPOSITORY,
        }

        preview_43 = publish(source, repository, 43, SHA_2, 9002, 2)
        root_index = (repository / "index.html").read_text(encoding="utf-8")
        assert "PR #42" in root_index and "PR #43" in root_index

        for stale_order in ((9002, 1), (9001, 99)):
            try:
                publish(source, repository, 43, SHA_1, *stale_order)
            except NewerPreviewPresent:
                pass
            else:
                raise AssertionError("an older workflow run replaced a newer preview")

        assert remove_preview(repository, 42, BASE_URL, 9000, 1) == "newer-present"
        assert preview_42.exists()
        assert remove_preview(repository, 42, BASE_URL, 9001, 1) == "removed"
        assert not preview_42.exists() and preview_43.exists()
        assert _read_cleanup_state(repository) == [42]
        assert remove_preview(repository, 42, BASE_URL) == "absent"

        preview_42 = publish(source, repository, 42, SHA_1, 9003)
        assert _read_cleanup_state(repository) == []
        removed = reconcile_previews(
            repository,
            {43: SHA_2},
            SOURCE_REPOSITORY,
            BASE_URL,
        )
        assert removed == [42]
        assert not preview_42.exists() and preview_43.exists()
        assert reconcile_previews(
            repository,
            {43: SHA_1},
            SOURCE_REPOSITORY,
            BASE_URL,
        ) == [43]
        assert not preview_43.exists()

        symlink_site = base / "symlink-site"
        make_site(symlink_site, "symlink")
        (symlink_site / "unsafe-link.txt").symlink_to(symlink_site / "asset.txt")
        expect_rejected(symlink_site, repository, "symlink")

        symlink_root = base / "symlink-root"
        symlink_root.symlink_to(source, target_is_directory=True)
        expect_rejected(symlink_root, repository, "root must not be a symlink")

        hardlink_site = base / "hardlink-site"
        make_site(hardlink_site, "hardlink")
        os.link(hardlink_site / "asset.txt", hardlink_site / "duplicate.txt")
        expect_rejected(hardlink_site, repository, "hard-linked")

        executable_site = base / "executable-site"
        make_site(executable_site, "executable")
        (executable_site / "asset.txt").chmod(0o755)
        expect_rejected(executable_site, repository, "executable")

        forbidden_site = base / "forbidden-site"
        make_site(forbidden_site, "forbidden")
        (forbidden_site / ".git").mkdir()
        (forbidden_site / ".git" / "config.txt").write_text("unsafe", encoding="utf-8")
        expect_rejected(forbidden_site, repository, "forbidden path")

        for index, marker in enumerate(
            (
                "-----BEGIN OPENSSH PRIVATE KEY-----",
                "-----BEGIN ENCRYPTED PRIVATE KEY-----",
                "-----BEGIN DSA PRIVATE KEY-----",
                "-----BEGIN PGP PRIVATE KEY BLOCK-----",
                "PuTTY-User-Key-File-3:",
            )
        ):
            secret_site = base / f"secret-site-{index}"
            make_site(secret_site, "secret")
            (secret_site / "secret.txt").write_text(f"{marker}\nunsafe", encoding="utf-8")
            expect_rejected(secret_site, repository, "private-key material")

        marker_site = base / "marker-site"
        make_site(marker_site, "marker")
        (marker_site / "index.html").write_text(
            HTML.replace("<body>", f"<body><!-- {PREVIEW_MARKER} -->"), encoding="utf-8"
        )
        expect_rejected(marker_site, repository, "reserved preview marker")

        root_url_site = base / "root-url-site"
        make_site(root_url_site, "root-url")
        (root_url_site / "index.html").write_text(
            HTML.replace("href='nested/page.html'", "href=/outside"), encoding="utf-8"
        )
        expect_rejected(root_url_site, repository, "root-relative")

        srcset_site = base / "srcset-site"
        make_site(srcset_site, "srcset")
        (srcset_site / "index.html").write_text(
            HTML.replace("<body>", '<body><img srcset="/outside.png 1x">'), encoding="utf-8"
        )
        expect_rejected(srcset_site, repository, "root-relative srcset")

        refresh_site = base / "refresh-site"
        make_site(refresh_site, "refresh")
        (refresh_site / "index.html").write_text(
            HTML.replace("<head>", '<head><meta http-equiv="refresh" content="0; url=/outside">'),
            encoding="utf-8",
        )
        expect_rejected(refresh_site, repository, "root-relative meta refresh")

        css_site = base / "css-site"
        make_site(css_site, "css")
        (css_site / "style.css").write_text('@import "/outside.css";', encoding="utf-8")
        expect_rejected(css_site, repository, "stylesheet contains a root-relative")

        css_escape_site = base / "css-escape-site"
        make_site(css_escape_site, "css-escape")
        (css_escape_site / "style.css").write_text(
            r"body { background: url(\2f outside.png); }", encoding="utf-8"
        )
        expect_rejected(css_escape_site, repository, "stylesheet contains a root-relative")

        script_site = base / "script-site"
        make_site(script_site, "script")
        (script_site / "app.js").write_text("fetch('/outside.json')", encoding="utf-8")
        expect_rejected(script_site, repository, "script contains a root-relative")

        for index, script in enumerate(
            (
                "import item from '/outside.js'",
                "request.open('GET', '/outside.json')",
                "const item = new URL('/outside', location.href)",
                "fetch(`/outside.json`)",
            )
        ):
            script_site = base / f"script-root-site-{index}"
            make_site(script_site, "script-root")
            (script_site / "app.js").write_text(script, encoding="utf-8")
            expect_rejected(script_site, repository, "script contains a root-relative")

        svg_site = base / "svg-site"
        make_site(svg_site, "svg")
        (svg_site / "image.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><image href="/outside.png"/></svg>',
            encoding="utf-8",
        )
        expect_rejected(svg_site, repository, "root-relative href")

        svg_xlink_site = base / "svg-xlink-site"
        make_site(svg_xlink_site, "svg-xlink")
        (svg_xlink_site / "image.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
            '<image xlink:href="/outside.png"/></svg>',
            encoding="utf-8",
        )
        expect_rejected(svg_xlink_site, repository, "root-relative xlink:href")

        svg_base_site = base / "svg-base-site"
        make_site(svg_base_site, "svg-base")
        (svg_base_site / "image.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" xml:base="/"><image href="outside.png"/></svg>',
            encoding="utf-8",
        )
        expect_rejected(svg_base_site, repository, "xml:base attribute")

        svg_filter_site = base / "svg-filter-site"
        make_site(svg_filter_site, "svg-filter")
        (svg_filter_site / "image.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><g filter="url(/filter.svg#x)"/></svg>',
            encoding="utf-8",
        )
        expect_rejected(svg_filter_site, repository, "root-relative CSS URL")

        srcdoc_site = base / "srcdoc-site"
        make_site(srcdoc_site, "srcdoc")
        (srcdoc_site / "index.html").write_text(
            HTML.replace("<body>", '<body><iframe srcdoc="&lt;a href=/outside&gt;x&lt;/a&gt;"></iframe>'),
            encoding="utf-8",
        )
        expect_rejected(srcdoc_site, repository, "embedded srcdoc")

        manifest_site = base / "manifest-site"
        make_site(manifest_site, "manifest")
        (manifest_site / "app.webmanifest").write_text(
            json.dumps({"shortcuts": [{"url": "/outside"}]}), encoding="utf-8"
        )
        expect_rejected(manifest_site, repository, "web manifest contains a root-relative")

        share_manifest_site = base / "share-manifest-site"
        make_site(share_manifest_site, "share-manifest")
        (share_manifest_site / "app.webmanifest").write_text(
            json.dumps({"share_target": {"action": "/share"}}), encoding="utf-8"
        )
        expect_rejected(share_manifest_site, repository, "web manifest contains a root-relative")

        valid_archive = base / "valid.zip"
        with zipfile.ZipFile(valid_archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in source.rglob("*"):
                if path.is_file():
                    bundle.write(path, Path("site") / path.relative_to(source))
        extracted_site = extract_preview_archive(valid_archive, base / "extracted")
        assert (extracted_site / "index.html").is_file()

        mismatched_count_archive = base / "mismatched-count.zip"
        mismatched_bytes = bytearray(valid_archive.read_bytes())
        eocd = mismatched_bytes.rfind(b"PK\x05\x06")
        assert eocd >= 0
        struct.pack_into("<H", mismatched_bytes, eocd + 8, 1)
        struct.pack_into("<H", mismatched_bytes, eocd + 10, 1)
        mismatched_count_archive.write_bytes(mismatched_bytes)
        try:
            extract_preview_archive(mismatched_count_archive, base / "mismatched-count-extracted")
        except ValueError as error:
            assert "entry count" in str(error)
        else:
            raise AssertionError("ZIP central-directory count mismatch was not rejected")

        trailing_archive = base / "trailing.zip"
        trailing_archive.write_bytes(valid_archive.read_bytes() + b"trailing")
        try:
            extract_preview_archive(trailing_archive, base / "trailing-extracted")
        except ValueError as error:
            assert "trailing or malformed" in str(error)
        else:
            raise AssertionError("ZIP trailing data was not rejected")

        duplicate_archive = base / "duplicate.zip"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(duplicate_archive, "w") as bundle:
                bundle.writestr("site/index.html", HTML)
                bundle.writestr("site/index.html", HTML)
        try:
            extract_preview_archive(duplicate_archive, base / "duplicate-extracted")
        except ValueError as error:
            assert "duplicate path" in str(error)
        else:
            raise AssertionError("ZIP duplicate paths were not rejected")

        ratio_archive = base / "ratio.zip"
        with zipfile.ZipFile(ratio_archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr("site/index.html", "0" * (1024 * 1024))
        try:
            extract_preview_archive(ratio_archive, base / "ratio-extracted")
        except ValueError as error:
            assert "compression ratio" in str(error)
        else:
            raise AssertionError("ZIP excessive compression ratio was not rejected")

        unsafe_archive = base / "unsafe.zip"
        with zipfile.ZipFile(unsafe_archive, "w") as bundle:
            bundle.writestr("../../escaped.html", HTML)
        try:
            extract_preview_archive(unsafe_archive, base / "unsafe-extracted")
        except ValueError as error:
            assert "unsafe path" in str(error)
        else:
            raise AssertionError("ZIP path traversal was not rejected")
        assert not (base / "escaped.html").exists()

        symlink_archive = base / "symlink.zip"
        symlink_entry = zipfile.ZipInfo("site/link.txt")
        symlink_entry.create_system = 3
        symlink_entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(symlink_archive, "w") as bundle:
            bundle.writestr("site/index.html", HTML)
            bundle.writestr(symlink_entry, "index.html")
        try:
            extract_preview_archive(symlink_archive, base / "symlink-extracted")
        except ValueError as error:
            assert "non-regular entry" in str(error)
        else:
            raise AssertionError("ZIP symlink was not rejected")

    print("OK: dedicated Pages previews are validated, ordered, and safely reconciled")


if __name__ == "__main__":
    main()
