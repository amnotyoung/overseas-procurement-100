# overseas-procurement-100

협력국 공공조달과 ODA 사업형성 절차를 국가당 3축으로 정규화하고, 공식 원문과 출처를 연결하는 데이터셋이다.

- `bidding`: 입찰제도
- `governance`: 조달 거버넌스·감독체계
- `pipeline`: ODA 사업 발굴·형성 절차

기준자료는 **KOICA 2026 국가별 개발협력사업 참여전략 자료집 4개 지역판**이다. 법령·기관 공식 자료로 현행 기준을 확인할 수 있는 항목은 그 기준을 산출물에 반영하고 출처를 함께 표시한다.

## 현재 범위

- 협력국 4개국 12개 제도: 네팔, 캄보디아, 미얀마, 탄자니아
- 발주자(KOICA) 규정 3개 제도
- 현행 기준 확인사항 16건
- 아시아·태평양 2026 자료집 수록국 12개국의 페이지 범위 등록

미얀마는 2026 아시아·태평양 자료집 미수록 보강국으로, 현지 지침·정책 원문을 직접 연결했다.

| 국가 | 입찰 | 거버넌스 | ODA 파이프라인 |
|---|---|---|---|
| 네팔 | `article-verified` | `article-verified` | `article-verified` |
| 캄보디아 | `law-linked` | `law-linked` | `source-document` |
| 미얀마 | `article-verified` | `article-verified` | `needs-review` |
| 탄자니아 | `article-verified` | `law-linked` | `source-document` |
| KOICA | `article-verified` | `article-verified` | `article-verified` |

자세한 현행 기준과 출처는 [현행 기준 확인 대장](docs/verification-log.md), [반영 출처](docs/errata.md), [영어 현장 확인 시트](docs/review-sheet.en.md)에서 확인한다.

## 출처

```text
참여전략설명회 자료집/
├── 2026 KOICA 국가별 개발협력사업 참여전략 자료집_아시아 및 태평양.pdf
├── 2026 KOICA 국가별 개발협력사업 참여전략 자료집_아프리카.pdf
├── 2026 KOICA 국가별 개발협력사업 참여전략 자료집_중남미.pdf
└── 2026 KOICA 국가별 개발협력사업 참여전략 자료집_중동 및 CIS.pdf

sources/koica-2026/
├── README.md
├── extract.sh
└── {region}/pages/*.txt
```

원본 PDF의 경로·페이지 수·SHA-256과 국가별 페이지 범위는 [data/manifest.json](data/manifest.json)에 기록한다. 추출 방식은 [sources/koica-2026/README.md](sources/koica-2026/README.md)에 정리돼 있다.

## 구조

```text
├── data/
│   ├── institutions/*.json      제도별 정규화 데이터
│   └── manifest.json            출처·국가·진행 대장
├── docs/
│   ├── data-contract.md         데이터 계약
│   ├── verification-log.md      현행 기준 확인 대장
│   ├── errata.md                현행 기준 반영 출처
│   └── review-sheet.en.md       영어 현장 확인 시트
├── sources/
│   ├── koica-2026/              2026 자료집 텍스트 추출본
│   └── laws/{country}/          법령·정책 원문
├── tools/
│   ├── validate.py              스키마·참조 무결성 검증
│   ├── check_links.py           외부 링크 확인
│   ├── build_docs.py            문서 생성
│   └── build_site.py            정적 사이트·국가별 배포 파일 생성
├── site/                        정적 사이트
└── dist/                        국가별 단일 HTML
```

`docs/verification-log.md`, `docs/errata.md`, `docs/review-sheet.en.md`, `site/`, `dist/`는 생성 산출물이다. 직접 수정하지 않고 `data/institutions/*.json`을 고친 뒤 다시 빌드한다.

## 빌드와 검증

```bash
python3 tools/validate.py
python3 tools/build_docs.py
python3 tools/build_site.py
```

선택 점검:

```bash
python3 tools/check_links.py
npm run check:boards
```

주요 화면:

| 경로 | 내용 |
|---|---|
| `site/index.html` | 국가·축 검색과 제도 대장 |
| `site/model/{slug}/index.html` | 업무구조도, 캔버스, 원문, 현행 기준, 검증 |
| `site/verification/index.html` | 현행 기준 확인 대장 |
| `site/errata/index.html` | 현행 기준 반영 출처 |
| `dist/{country}.html` | 국가별 오프라인 단일 파일 |

로컬 미리보기:

```bash
python3 -m http.server 8765 --directory site
```

## 다음 국가 추가

1. `data/manifest.json`에서 지역판과 국가 페이지 범위를 확인한다.
2. `sources/koica-2026/{region}/pages/`의 해당 텍스트를 읽는다.
3. 입찰·거버넌스·ODA 파이프라인 3개 JSON을 작성한다.
4. 인용 법령과 기관의 공식 원문을 확보하고 현행 여부를 확인한다.
5. 금액·비율·기한·제출서류는 원문 조문과 표에서 대조한다.
6. 확실히 확인된 현행 기준은 근거 출처와 함께 `action`·`userAction`에 반영한다.
7. `validate.py`, `build_docs.py`, `build_site.py`를 실행한다.

공개 산출물은 “현행 기준”, “산출물 반영”, “확인 출처”, “실무 확인” 순으로 보여준다. 내부 JSON의 `verification.discrepancies`와 `upstream` 필드는 기존 데이터 계약과 추적성을 위해 유지한다.

## 검증 상태

| 값 | 의미 |
|---|---|
| `source-document` | 기준자료 기재와 출처 범위를 확인 |
| `law-linked` | 공식 원문 URL 연결 완료 |
| `article-verified` | 관련 조문을 원문에서 확인 |
| `needs-review` | 현지어·비공개 자료 등 추가 확인 필요 |

`article-verified`는 조문의 존재와 문언을 확인했다는 뜻이다. 개별 입찰에 대한 법률 자문이나 해당국 정부·KOICA의 공식 해석을 대신하지 않는다. 실제 참여 전에는 발주처 공고문과 현행 법령을 다시 확인해야 한다.
