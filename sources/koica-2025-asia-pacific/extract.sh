#!/bin/bash
# KOICA 참여전략 자료집 PDF → 국가별 텍스트 추출
#
# 자료집은 좌우 2면 스프레드(1228.82 × 841.89 pt)로 조판돼 있다.
# 그냥 pdftotext를 돌리면 좌우 페이지의 텍스트가 한 줄에 섞여 나와
# "Ⅰ 우리나라 지원방향   Ⅱ 협력국 개발협력현황"처럼 읽을 수 없는 결과가 된다.
# 페이지를 좌/우로 잘라 따로 추출해야 한다.
#
# 사용법:
#   ./extract.sh <PDF경로> [출력디렉터리]
#
# 필요: poppler (pdftotext, pdfinfo)  —  brew install poppler

set -euo pipefail

PDF="${1:?사용법: ./extract.sh <PDF경로> [출력디렉터리]}"
OUT="${2:-pages}"

if ! command -v pdftotext >/dev/null; then
  echo "pdftotext가 없습니다. brew install poppler" >&2
  exit 1
fi

PAGES=$(pdfinfo "$PDF" | awk '/^Pages:/ {print $2}')
WIDTH=$(pdfinfo "$PDF" | awk '/^Page size:/ {print int($3)}')
HEIGHT=$(pdfinfo "$PDF" | awk '/^Page size:/ {print int($5)}')
HALF=$((WIDTH / 2))

echo "PDF: $PDF"
echo "페이지 ${PAGES}장 / 크기 ${WIDTH}x${HEIGHT}pt / 분할 기준 ${HALF}pt"

mkdir -p "$OUT"

for p in $(seq 1 "$PAGES"); do
  n=$(printf '%03d' "$p")
  pdftotext -layout -f "$p" -l "$p" -x 0      -y 0 -W "$HALF" -H "$HEIGHT" "$PDF" "$OUT/p${n}_L.txt"
  pdftotext -layout -f "$p" -l "$p" -x "$HALF" -y 0 -W "$HALF" -H "$HEIGHT" "$PDF" "$OUT/p${n}_R.txt"
done

echo "추출 완료: $OUT/ (${PAGES}장 × 2면)"
echo
echo "국가별 페이지 범위는 data/manifest.json의 countries[].pdfPages 참조."
echo "예) 네팔 = PDF 5-14  →  $OUT/p005_L.txt ~ p014_R.txt"
echo
echo "표가 섞인 면을 읽을 때는 연속 공백을 구분자로 바꾸면 열 구조가 보인다:"
echo "  sed -e 's/[[:space:]]\\{3,\\}/ | /g' $OUT/p007_R.txt"
