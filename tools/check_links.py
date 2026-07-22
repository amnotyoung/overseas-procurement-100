#!/usr/bin/env python3
"""데이터에 적힌 모든 외부 URL이 살아 있는지 확인한다.

근거를 검증하는 프로젝트에서 근거 링크가 깨져 있으면 곤란하다.
법령 원문(verification.sources), 기관 사이트(canvas.authorities),
직접 지정한 법령 URL(canvas.legalBasis)을 모두 훑는다.

사용법:
    python3 tools/check_links.py           전부 확인
    python3 tools/check_links.py --slow    타임아웃을 20초로 늘려 확인

종료코드 0 = 모두 정상(또는 판정 보류), 1 = 죽은 링크 있음
"""
from __future__ import annotations

import json
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INST_DIR = ROOT / "data" / "institutions"

TIMEOUT = 30 if "--slow" in sys.argv else 12
# 정부 사이트는 기본 UA를 막는 경우가 많다
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")

# 네팔 정부 사이트는 중간 인증서를 빠뜨리고 보내는 곳이 많다.
# 파이썬 기본 CA로는 검증이 깨지지만 브라우저에서는 열린다 — certifi가 있으면 그걸 쓴다.
try:
    import certifi
    SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CTX = ssl.create_default_context()


def collect() -> dict[str, list[str]]:
    """URL → 그 URL이 등장하는 위치 목록"""
    urls: dict[str, list[str]] = {}

    def add(u: str | None, where: str) -> None:
        if u:
            urls.setdefault(u, []).append(where)

    for f in sorted(INST_DIR.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        slug = d["slug"]
        for a in d["canvas"].get("authorities", []):
            add(a.get("url"), f"{slug} · 권한기관 {a['name']}")
        for lb in d["canvas"].get("legalBasis", []):
            add(lb.get("url"), f"{slug} · 법적근거 {lb['law']}")
        v = d.get("verification", {})
        for s in v.get("sources", []):
            add(s.get("officialUrl"), f"{slug} · 원문 {s['law']}")
        for u in v.get("unresolved", []):
            add(u.get("url"), f"{slug} · 미확인 {u['law']}")
    return urls


def probe(url: str) -> tuple[str, str]:
    """(판정, 설명). 판정은 ok / dead / unknown.

    '보류(unknown)'는 자동 확인이 막힌 것이고 링크가 죽었다는 뜻이 아니다.
    죽었다고 단정하는 것은 서버가 4xx/5xx로 명확히 없다고 답했을 때뿐이다.
    """
    req = urllib.request.Request(url, headers={"User-Agent": UA}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=SSL_CTX) as r:
            code = r.getcode()
            if code < 300:
                return "ok", f"HTTP {code}"
            if code < 400:
                # 세션·쿠키 기반 리다이렉트. 브라우저에서는 정상적으로 열린다
                return "ok", f"HTTP {code} (리다이렉트)"
            return "dead", f"HTTP {code}"
    except urllib.error.HTTPError as ex:
        if 300 <= ex.code < 400:
            # 세션 기반 리다이렉트를 urllib이 못 따라간 것
            return "unknown", f"HTTP {ex.code} 리다이렉트 반복 — 브라우저로 확인할 것"
        if ex.code in (403, 405, 429):
            # 봇 차단·메서드 거부는 링크가 죽었다는 뜻이 아니다
            return "unknown", f"HTTP {ex.code} (접근 제한 — 브라우저로 확인할 것)"
        return "dead", f"HTTP {ex.code}"
    except urllib.error.URLError as ex:
        reason = str(ex.reason)
        if "CERTIFICATE_VERIFY_FAILED" in reason:
            return "unknown", "인증서 체인 불완전 — 브라우저로 확인할 것"
        if "reset by peer" in reason or "Connection refused" in reason:
            return "unknown", f"서버가 연결을 끊음(봇 차단 가능) — {reason}"
        if "timed out" in reason:
            return "unknown", f"{TIMEOUT}초 내 응답 없음"
        return "dead", f"연결 실패 — {reason}"
    except TimeoutError:
        return "unknown", f"{TIMEOUT}초 내 응답 없음"
    except Exception as ex:  # noqa: BLE001
        return "unknown", f"{type(ex).__name__}: {ex}"


def curl_probe(url: str) -> tuple[str, str] | None:
    """urllib이 판정을 못 냈을 때의 2차 확인. curl은 시스템 키체인을 쓴다."""
    if not shutil.which("curl"):
        return None
    try:
        r = subprocess.run(
            ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "-L",
             "--max-redirs", "5", "--max-time", str(TIMEOUT), "-A", UA, url],
            capture_output=True, text=True, timeout=TIMEOUT + 8,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    code = (r.stdout or "").strip()
    if not code.isdigit() or code == "000":
        return None
    n = int(code)
    if n < 400:
        return "ok", f"HTTP {n} (curl 확인)"
    if n in (403, 405, 429):
        return "unknown", f"HTTP {n} (접근 제한 — 브라우저로 확인할 것)"
    return "dead", f"HTTP {n} (curl 확인)"


def main() -> int:
    urls = collect()
    if not urls:
        print("확인할 URL이 없습니다.")
        return 0

    print(f"URL {len(urls)}개 확인 (타임아웃 {TIMEOUT}초)\n")
    dead, unknown = [], []

    for u, where in sorted(urls.items()):
        verdict, note = probe(u)
        if verdict == "unknown":
            # curl은 시스템 키체인을 쓰므로 인증서 체인이 불완전한 사이트도 통과한다
            c = curl_probe(u)
            if c:
                verdict, note = c
        mark = {"ok": "정상", "dead": "죽음", "unknown": "보류"}[verdict]
        print(f"[{mark}] {u}")
        print(f"       {note}")
        for w in where:
            print(f"       ← {w}")
        if verdict == "dead":
            dead.append((u, note, where))
        elif verdict == "unknown":
            unknown.append((u, note))
        print()

    print("─" * 60)
    print(f"정상 {len(urls) - len(dead) - len(unknown)} · 보류 {len(unknown)} · 죽음 {len(dead)}")

    if unknown:
        print("\n보류 — 자동 확인이 막힌 것들. 브라우저로 직접 열어 볼 것")
        for u, note in unknown:
            print(f"  {u}  ({note})")

    if dead:
        print("\n죽음 — 데이터에서 고치거나 제거할 것")
        for u, note, where in dead:
            print(f"  {u}  ({note})")
            for w in where:
                print(f"      ← {w}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
