# overseas-procurement-100

**공개 페이지:** [https://amnotyoung.github.io/overseas-procurement-100/](https://amnotyoung.github.io/overseas-procurement-100/)

협력국 공공조달과 ODA 사업형성 절차, ODA 건축사업의 법·제도를 구조화하고 공식 원문과 출처를 연결하는 데이터셋이다.

- `bidding`: 입찰제도
- `governance`: 조달 거버넌스·감독체계
- `pipeline`: ODA 사업 발굴·형성 절차
- `construction`: ODA 건축 인허가·검사·개장 제도(국가별 4번부터)

기준자료는 **KOICA 2026 국가별 개발협력사업 참여전략 자료집 4개 지역판**이다. 법령·기관 공식 자료로 현행 기준을 확인할 수 있는 항목은 그 기준을 산출물에 반영하고 출처를 함께 표시한다.

## 현재 범위

- 2026 참여전략 자료집 수록 43개국 전수: 아시아·태평양 12, 아프리카 15, 중남미 8, 중동·CIS 8
- 자료집 미수록 보강국 미얀마 3개 제도
- 발주자(KOICA) 규정 3개 제도
- 협력국 44개국·KOICA 발주자, 조달 135개 + 건축 132개 제도 다이어그램
- 현행 기준 확인사항 16건
- 4개 지역판 43개국의 원문 추출본·페이지 범위 등록

조달 다이어그램은 자료집 전수 국가를 `source-document` 단계로 1차 구조화하고 일부
국가는 공식 원문으로 심화검증했다. 건축 다이어그램은 44개 협력국 모두 공식 법령·정부
자료를 연결한 `law-linked` 기본판이며, 세네갈은 조문 대조 상세판이다.

| 범위 | 국가 수 | 제도 수 | 검증 수준 |
|---|---:|---:|---|
| 자료집 수록국 | 43 | 조달 129 + 건축 129 | 조달 `source-document` 중심, 건축 `law-linked` 중심 |
| 미얀마 보강 | 1 | 조달 3 + 건축 3 | 공식 법령·정부자료 연결, 일부 추가검증 필요 |
| KOICA(발주자) | 1 | 조달 3 | `article-verified` |

자세한 현행 기준과 출처는 [현행 기준 확인 대장](docs/verification-log.md), [반영 출처](docs/errata.md), [영어 현장 확인 시트](docs/review-sheet.en.md)에서 확인한다.

### ODA 건축 법·제도

원천 데이터와 검증 계약은 조달 3축과 분리하되, 공개 사이트에서는 같은 국가의 1~3번 조달 제도 뒤에 4번부터 이어서 보여준다. ODA 건축 전문가가 사업기획·현지조사·설계·인허가·시공·준공·운영 단계에서 사용할 국가별 법·제도 데이터팩이다.

- 공개 화면: [통합 제도 대장](https://amnotyoung.github.io/overseas-procurement-100/?axis=construction) → [세네갈 04 도시계획·부지규제](https://amnotyoung.github.io/overseas-procurement-100/model/senegal-site-urban-construction-regulations/)
- 생성 문서: [세네갈 건축 법·제도 브리프](docs/construction-regulations/senegal.md)
- 범위: 법령·공식자료 14종·관할기관 14개·생애주기 의무 20건·미확정 질문 12건·제도 구조도 18노드
- 구조도: [`korea100studio`](https://github.com/amnotyoung/korea100studio) `gov` 프로필로 구성 품질을 검사하고, 공개 화면은 기존 model 템플릿의 선명한 HTML 카드·동적 연결선·클릭 상세 패널로 렌더링한다.
- 사업 적용: Diamniadio AI Transition Center의 Gate 1 자료요청, 인허가 경로, 현지 책임건축사, ERP·소방, 환경평가, 기술검사·보험, 준공·개장 조건
- 원칙: 법령의 현행·폐지·개정예고를 구분하고, 조문 확인과 사업 적용판단을 분리하며, 필지·면적·용도처럼 받지 못한 정보는 ‘해당 없음’으로 처리하지 않는다.
- 국가 공통 확인사항: 필지별 개발규제(건폐율·용적률·높이·이격·주차), 시설·용도·위험 분류, 지반·침수, 실제 수수료·처리기간, 현지 설계·검사·보험기관은 국가·사업별 현지조사 항목으로 분리한다. PUD·ERP 같은 특정 법권의 용어는 해당 국가에서만 사용한다.

데이터 구조와 확장 규칙은 [국가별 건축 법·제도 데이터 계약](docs/construction-regulations-data-contract.md)에 정리돼 있다. 국가 파일 하나를 추가하면 검증기와 생성기가 같은 형식의 전문가 브리프를 만든다.

공개 화면의 **업무구조도**는 `processBoard`와 `publicModels`에 정리한 해당 국가·지방 관할의 실제 공식 건축 인허가·검사 절차를 보여준다. catalog에 공식 원문으로 확인한 `officialProcedure`가 없으면 공통 ODA 업무를 국가 절차처럼 채우지 않고, `공식 절차 상세 미확인` 1개 증거 진입 노드만 표시한다. 현지자료 요청·사업별 적용판단·설계통합 같은 ODA 사업팀의 업무는 **ODA 사업 적용 확인사항** 카드에 별도로 둔다. `permitPath`의 **공식 결정 Gate**는 신청·심사 단계와 분리해 관할기관의 결정·산출물·선행조건을 보여준다. 단계·Gate·결과분기·보완회귀 수는 국가별 확인 근거에 따라 달라지며, 분기와 회귀는 근거가 있는 경우에만 표시한다. 화면의 노드 번호는 각 제도축에서 `B01`부터 다시 시작하며, 원천 ID는 참조 추적을 위해 별도로 유지한다.

## 원작

이 저장소의 사이트 구조·빌드 도구·저작 방식은 [korea100](https://github.com/hosungseo/korea100)과
[korea100studio](https://github.com/hosungseo/korea100studio)에서 가져왔다.

조달 도메인을 제도 구조도로 다루는 틀은 [how-did-they-do-all-that-procurement](https://github.com/Milkbuttercheese2/how-did-they-do-all-that-procurement)를
따랐다. korea100을 공공조달로 옮긴 작업이며, 이 저장소는 그 접근을 국내 조달에서 협력국 조달로 확장한 것이다.

세 저장소 모두 MIT 라이선스이며, 원저작권 표시는 [LICENSE](LICENSE)에 그대로 남겨 두었다.

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
│   ├── institutions/*.json              조달 제도별 정규화 데이터
│   ├── construction-regulations/        국가별 ODA 건축 법·제도 원천 데이터
│   └── manifest.json                    조달 출처·국가·진행 대장
├── docs/
│   ├── data-contract.md                 조달 데이터 계약
│   ├── construction-regulations-data-contract.md
│   ├── construction-regulations/        국가별 건축 법·제도 브리프
│   ├── verification-log.md              현행 기준 확인 대장
│   ├── errata.md                        현행 기준 반영 출처
│   └── review-sheet.en.md               영어 현장 확인 시트
├── sources/
│   ├── koica-2026/              2026 자료집 텍스트 추출본
│   └── laws/{country}/          법령·정책 원문
├── tools/
│   ├── validate.py              스키마·참조 무결성 검증
│   ├── generate_all_countries.py  4개 지역판 전수 추출·1차 다이어그램 생성
│   ├── check_links.py           외부 링크 확인
│   ├── build_docs.py            문서 생성
│   ├── validate_construction_regulations.py  건축 법·제도 검증
│   ├── build_construction_regulations.py     건축 법·제도 브리프 생성
│   └── build_site.py            정적 사이트·국가별 배포 파일 생성
├── site/                        정적 사이트
└── dist/                        국가별 단일 HTML
```

`docs/verification-log.md`, `docs/errata.md`, `docs/review-sheet.en.md`, `docs/construction-regulations/`, `site/`, `dist/`는 생성 산출물이다. 직접 수정하지 않고 해당 원천 JSON을 고친 뒤 다시 빌드한다.

## 빌드와 검증

```bash
npm ci
python3 tools/generate_all_countries.py  # PDF 전수 추출·미검증 국가 1차 다이어그램 생성
python3 tools/validate.py
python3 tools/build_docs.py
python3 tools/build_site.py
```

건축 법·제도 원천 데이터와 통합 model:

```bash
python3 tools/build_construction_baselines.py --check
python3 tools/validate_construction_regulations.py
python3 tools/build_construction_regulations.py
python3 tools/build_site.py
npm run build:construction-boards
python3 tools/check_construction_site.py
```

선택 점검:

```bash
python3 tools/check_links.py
npm run check:boards
```

## PR 미리보기와 운영 배포

1. 모든 변경은 `main` 대상 Pull Request로 올린다.
2. `Build PR Preview`는 쓰기 권한 없이 PR을 검증·빌드하고 정적 artifact만 만든다.
3. `main`에 고정된 `Publish PR Preview`가 artifact를 실행하지 않고 검사한 뒤 전용 공개 저장소 `amnotyoung/overseas-procurement-100-preview`의 `/pr-{번호}/`에 게시한다.
4. 게시 URL에서 정확한 커밋 SHA를 확인한 뒤 PR에 미리보기 댓글, **View deployment**, `Preview Published` 상태가 표시된다.
5. 사람이 미리보기를 확인하고 승인하기 전에는 병합하지 않는다. 승인·병합 후에만 기존 `Deploy GitHub Pages`가 운영 사이트를 배포한다.
6. `Reconcile PR Previews`가 15분마다 열린 PR과 대조해 종료된 PR의 미리보기와 deployment를 정리한다.

저장소 정책이 Actions bot의 PR 댓글 작성을 제한할 수 있으므로 댓글은 보조 기능이다. **View deployment**와 `Preview Published`의 실제 URL이 미리보기의 권위 있는 진입점이며, 댓글 실패가 게시·상태·정리를 막지 않는다.

미리보기 게시 권한은 전용 저장소 한 곳에만 유효한 deploy key로 제한하고, 키는 `main`만 접근 가능한 `preview-publisher` Environment secret에 둔다. PR 빌드는 읽기 권한만 가지며, 게시기는 PR artifact를 정적 데이터로만 취급한다. 다운로드한 ZIP은 SHA-256, 경로, 파일형식, 개수, 압축·해제 용량을 검사한 뒤 신뢰된 게시기로만 푼다. 자동 미리보기는 같은 저장소에서 만든 PR만 대상으로 한다. 루트 상대 URL 검사는 `/pr-{번호}/` 하위경로 호환성을 위한 보조 검사이며 실행 코드의 완전한 보안 격리를 뜻하지 않는다.

`main` 보호 규칙은 직접 push를 막고 `validate`와 `Preview Published`를 필수 상태로 요구한다. 승인 리뷰 수는 0이며, 화면 검토 완료 여부는 PR 체크리스트를 사람이 확인한 뒤 병합으로 확정한다.

전용 저장소와 배포 경로는 운영 배포와 분리되지만 두 GitHub Pages URL은 모두 `amnotyoung.github.io` 아래라 웹 origin 자체는 같다. 따라서 이 미리보기는 로그인·쿠키·민감정보를 다루지 않는 공개 정적 사이트 검토용으로만 사용한다. origin 격리가 필요한 서비스에는 별도 도메인이나 별도 호스트를 사용해야 한다.

최초 도입 PR에서는 `workflow_run` 게시기가 아직 `main`에 없으므로 자동 게시가 시작되지 않는다. 이 PR만 검증된 로컬 빌드를 전용 Preview Pages에 수동 게시하고 실제 URL 확인 뒤 `Preview Published` 상태를 1회 기록한다. 병합 후에는 별도 canary PR에서 자동 build → publish → 상태 갱신 → 정리 전 과정을 확인하며, 이후에는 수동 상태 기록을 사용하지 않는다.

canary가 통과하면 branch protection의 `Preview Published` required check를 GitHub Actions App에서 생성된 상태로 고정해 같은 이름의 수동 상태가 gate를 대신하지 못하게 한다. 아래 명령은 이미 GitHub Actions App에 묶인 `validate` check의 App ID를 재사용하면서 기존 required check 목록을 보존한다. `canary_pr`만 실제 PR 번호로 바꿔 실행한다.

```bash
repo_slug=amnotyoung/overseas-procurement-100
branch_name=main
canary_pr=123

required_checks="$(gh api "repos/$repo_slug/branches/$branch_name/protection/required_status_checks")"
actions_app_id="$(jq -er '
  [.checks[] | select(.context == "validate" and .app_id != null) | .app_id]
  | unique
  | if length == 1 then .[0] else error("validate App ID is not unique") end
' <<< "$required_checks")"
test "$(jq '[.checks[] | select(.context == "Preview Published")] | length' <<< "$required_checks")" = 1

jq --argjson actions_app_id "$actions_app_id" '
  {
    strict: .strict,
    checks: [
      .checks[]
      | if .context == "Preview Published"
        then .app_id = $actions_app_id
        else .
        end
    ]
  }
' <<< "$required_checks" \
  | gh api --method PATCH \
      "repos/$repo_slug/branches/$branch_name/protection/required_status_checks" \
      --input -

test "$(gh api "repos/$repo_slug/branches/$branch_name/protection/required_status_checks" \
  --jq '.checks[] | select(.context == "Preview Published") | .app_id')" = "$actions_app_id"
gh pr checks "$canary_pr" --repo "$repo_slug"
```

마지막 두 명령에서 App ID 비교가 성공하고 canary의 `Preview Published`가 통과해야 고정이 완료된 것이다. 이후 수동 상태 기록은 사용하지 않는다.

주요 화면:

| 경로 | 내용 |
|---|---|
| `site/index.html` | 국가·축 검색과 제도 대장 |
| `site/model/{country}-{site-urban\|permit-environment\|control-completion}-construction-regulations/index.html` | 국가별 04~06 건축 제도축: HTML 업무구조도, 클릭 상세, 법령·증빙·현장검증 |
| `site/construction/…` | 기존 공개 주소를 통합 model로 보내는 호환 리디렉션 |
| `site/model/{slug}/index.html` | 국가별 01~ 제도 업무구조도, 캔버스, 원문, 현행 기준, 검증 |
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

## 다음 건축 법·제도 국가 추가

1. `data/construction-regulations/manifest.json`에 국가와 기준일을 등록한다.
2. 도시계획, 건설, 건축사, 환경, 소방·시설안전, 노동·HSE, 장애·접근성, 토지·특구의 현행 법령과 시행령을 공식 원문에서 찾는다.
3. 폐지조항과 최근 개정일을 먼저 확인하고, 오래된 공식 민원안내와 충돌하면 법령을 우선한다.
4. 국가 공통 의무는 `requirements`, 부지별 계획·특구는 `siteOverlays`, 받지 못한 사업 입력은 `openQuestions`에 적고, 공개 제도축은 `publicModels`에서 같은 원천을 참조해 나눈다.
5. 법정 처리기간은 완비서류 접수 후 기간으로 기록하고 전체 인허가기간과 구분한다.
6. `python3 tools/validate_construction_regulations.py`와 `python3 tools/build_construction_regulations.py`를 실행한다.
7. `build_site.py`가 같은 국가의 조달 1~3번 뒤에 도시계획·부지, 건축허가·환경, 기술검사·보험·준공 3종을 4~6번으로 자동 배치한다.

조문까지 대조한 상세판은 국가 JSON을 직접 관리한다. 전체 국가 기본판은
`data/construction-regulations/catalog/baselines.json`에 국가별 공식 출처·기관·판단만 기록하고
`python3 tools/build_construction_baselines.py`로 같은 3축 계약의 국가 JSON을 생성한다. 공식 원문에서 절차 순서를 확인한 축은 catalog의 `officialProcedure`에 실제 단계·Gate·분기·보완회귀를 기록한다. 확인하지 못한 축은 노드 수를 맞추지 않고 `공식 절차 상세 미확인` 1노드로 남기며, ODA 준비·현지확인 항목은 별도 카드로 분리한다.

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
