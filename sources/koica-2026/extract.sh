#!/bin/bash
# KOICA 2026 참여전략 자료집 PDF를 물리 면별 텍스트로 추출한다.
#
# 사용법:
#   ./extract.sh <PDF경로> [출력디렉터리]
#
# 2026년판은 612 × 858 pt 단면 조판이므로 좌우 분할하지 않는다.

set -euo pipefail

PDF="${1:?사용법: ./extract.sh <PDF경로> [출력디렉터리]}"
OUT="${2:-pages}"

if ! command -v pdftotext >/dev/null; then
  echo "pdftotext가 없습니다. brew install poppler" >&2
  exit 1
fi

PAGES=$(pdfinfo "$PDF" | awk '/^Pages:/ {print $2}')
mkdir -p "$OUT"

for p in $(seq 1 "$PAGES"); do
  n=$(printf '%03d' "$p")
  pdftotext -layout -f "$p" -l "$p" "$PDF" "$OUT/p${n}.txt"
done

echo "추출 완료: $OUT/ (${PAGES}면)"
