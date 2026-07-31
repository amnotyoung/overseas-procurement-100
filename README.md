# overseas-procurement-100

**공개 페이지:** [https://amnotyoung.github.io/overseas-procurement-100/](https://amnotyoung.github.io/overseas-procurement-100/)

협력국 공공조달과 ODA 사업형성 절차를 국가당 3축으로 정규화하고, 공식 원문과 출처를 연결하는 데이터셋이다.

- `bidding`: 입찰제도
- `governance`: 조달 거버넌스·감독체계
- `pipeline`: ODA 사업 발굴·형성 절차

기준자료는 **KOICA 2026 국가별 개발협력사업 참여전략 자료집 4개 지역판**이다. 법령·기관 공식 자료로 현행 기준을 확인할 수 있는 항목은 그 기준을 산출물에 반영하고 출처를 함께 표시한다.

## 현재 범위

- 2026 참여전략 자료집 수록 43개국 전수: 아시아·태평양 12, 아프리카 15, 중남미 8, 중동·CIS 8
- 자료집 미수록 보강국 미얀마 3개 제도
- 발주자(KOICA) 규정 3개 제도
- 총 45개국·발주자, 135개 제도 다이어그램
- 현행 기준 확인사항 16건
- 4개 지역판 43개국의 원문 추출본·페이지 범위 등록

자료집 전수 국가의 신규 다이어그램은 `source-document` 단계의 1차 구조화다. 기존
네팔·캄보디아·탄자니아와 미얀마·KOICA 레코드는 공식 원문 확인 깊이에 따라
`law-linked`·`article-verified` 상태를 유지한다.

| 범위 | 국가 수 | 제도 수 | 검증 수준 |
|---|---:|---:|---|
| 자료집 수록국 | 43 | 129 | `source-document` 중심, 3개국 심화검증 |
| 미얀마 보강 | 1 | 3 | `article-verified` 2, `needs-review` 1 |
| KOICA(발주자) | 1 | 3 | `article-verified` |

자세한 현행 기준과 출처는 [현행 기준 확인 대장](docs/verification-log.md), [반영 출처](docs/errata.md), [영어 현장 확인 시트](docs/review-sheet.en.md)에서 확인한다.

## 원작

이 저장소의 사이트 구조·빌드 도구·저작 방식은 [korea100](https://github.com/hosungseo/korea100)과
[korea100studio](https://github.com/hosungseo/korea100studio)에서 가져왔다. 두 저장소 모두 MIT 라이선스이며,
원저작권 표시는 [LICENSE](LICENSE)에 그대로 남겨 두었다.

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
└── {region}/{country}.txt
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
│   ├── generate_all_countries.py  4개 지역판 전수 추출·1차 다이어그램 생성
│   ├── check_links.py           외부 링크 확인
│   ├── build_docs.py            문서 생성
│   └── build_site.py            정적 사이트·국가별 배포 파일 생성
├── site/                        정적 사이트
└── dist/                        국가별 단일 HTML
```

`docs/verification-log.md`, `docs/errata.md`, `docs/review-sheet.en.md`, `site/`, `dist/`는 생성 산출물이다. 직접 수정하지 않고 `data/institutions/*.json`을 고친 뒤 다시 빌드한다.

## 빌드와 검증

```bash
python3 tools/generate_all_countries.py  # PDF 전수 추출·미검증 국가 1차 다이어그램 생성
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

## 소비자 저장소 업데이트 알림

`main`의 검증·보드 검사·사이트 빌드가 모두 성공하면 불변 커밋 SHA를
`country-report-skill`에 `dependency-updated` 이벤트로 전달한다. 소비자
저장소는 파이프라인·조달 거버넌스 데이터 계약을 다시 검증한 뒤 잠금파일
갱신 PR을 만든다.

저장소 관리자는 `country-report-skill`의 **Contents: write**만 허용한
fine-grained personal access token을 Actions secret
`DEPENDENCY_DISPATCH_TOKEN`으로 등록해야 한다.

## 라이선스

소스 코드·템플릿·도구는 [MIT 라이선스](LICENSE)를 따른다.

**데이터는 별개다.** KOICA 참여전략 자료집, 각국 법령, 정부 간행물, 그 밖의 원문은 각 출처의
조건을 그대로 유지한다. 이 저장소가 그 조건을 바꾸지 않는다. 재배포하거나 인용하기 전에
`verification.sources`의 원출처와 그 이용 조건을 확인해야 한다.
