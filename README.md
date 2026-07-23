# overseas-procurement-100

협력국 조달제도를 **국가당 3축**으로 정규화하고, 그 서술을 **각국 법령 원문과 대조해 검증**하는 데이터셋.

[how-did-they-do-all-that-procurement](https://github.com/Milkbuttercheese2/how-did-they-do-all-that-procurement)(국내 조달제도 100)의
방법론 — 제도별 JSON 정규화(Canvas 9칸 + Process) → 조문 근거 표기 → 검증 배지 — 을 해외 조달제도에 적용했다.

| | 원본 | 본 프로젝트 |
|---|---|---|
| 대상 | 대한민국 1개국 × 제도 66개 | 협력국 33개국 내외 × 국가당 3개 |
| 1차 출처 | 국가법령정보센터 | KOICA 국가별 개발협력사업 참여전략 자료집(2025) |
| 검증 | 국가법령정보센터 Open API 기계 대조 | 각국 조달법·규칙 영문 원문 조문 단위 대조 |
| 산출 | 제도 한 장 요약 | 제도 한 장 요약 **+ 자료집↔원문 불일치 대장** |

---

## 지금 상태

**네팔 파일럿 완료** — 3개 제도, 검증 통과, **불일치 10건 발견(high 3 / medium 4 / low 3)**

| 제도 | 축 | 검증 상태 | 불일치 |
|---|---|---|---|
| [네팔 공공조달 입찰제도](data/institutions/nepal-bidding-system.json) | bidding | `article-verified` | 3 |
| [네팔 조달 거버넌스·감독체계](data/institutions/nepal-procurement-governance.json) | governance | `article-verified` | 2 |
| [네팔 ODA 사업 발굴·형성 절차](data/institutions/nepal-oda-project-pipeline.json) | pipeline | `article-verified` | 5 |

발견한 것 중 실무에서 바로 문제가 되는 세 건:

- **대리인 제출서류** — 자료집은 "주민등록 등본"이라 하지만 원문(PPR r.39(1)(d))은
  **PAN(영구계좌번호) 등록증명서 인증등본 + 대리인 수락서**다. 세무등록번호와 주민등록은 다른 서류이고, 누락 시 입찰서가 심사에서 빠질 수 있다.
- **ODA 사업 착수 지점** — 자료집은 "공여기관이 수원기관 부처와 협의해 발굴"이라 하지만,
  네팔 정책은 그 접촉 자체에 **재무부 사전 승인**을 요구한다(FAMP §3.3.2(k)). 공여기관도 승인 대상이다(§3.3.5(b)).
- **근거 정책이 폐지됨** — 자료집이 전제한 국제개발협력정책 2019는 **대외원조동원정책 2025**(2025-04-21 승인)
  §3.7.1로 폐지됐다. 자료집 발행 2개월 뒤다. 차관 1천만 달러 문턱과 국가계획위원회 동의 요건이 사라졌고
  조세면제가 좁아졌다 — 자료집을 현행 기준으로 그대로 쓰면 없어진 요건을 준비하거나
  면제받을 수 없는 세금을 사업비에서 누락하게 된다.

전체는 [검증 대장](docs/verification-log.md) 참조.

**발견에서 끝내지 않는다.** 불일치 8건마다 세 가지를 붙였다.

| 필드 | 수신자 | 답하는 질문 |
|---|---|---|
| `action` | 이 데이터셋 | 우리 데이터는 어느 쪽을 따랐나 |
| `userAction` | 입찰 준비자 | 내가 지금 무엇을 다르게 해야 하나 |
| `upstream` | 자료집 발행처 | 다음 판에서 무엇을 고쳐야 하나 |

`upstream`이 있는 항목은 [정오표](docs/errata.md)에 `현재 서술 → 수정 제안 → 근거 조문` 형태로 모여
그대로 옮겨 전달할 수 있다. 현재 **정정 요망 4건 / 보완 권고 4건, 전부 미제보** 상태다.
전달 후 `upstream.state`를 갱신하면 문서와 화면이 따라온다. 자동 발송은 하지 않는다.

---

## 왜 3축인가

자료집 11개국을 전수 조사한 결과다.

| 섹션 | 존재 국가 | 축 채택 |
|---|---|---|
| 입찰제도 | 11/11 | ✅ `bidding` |
| 조달 관련 조직체계 | 11/11 | ✅ `governance` |
| 수원체계 · 사업 발굴·반영절차 | 11/11 | ✅ `pipeline` |
| 진출 유의사항 | 7/11 | ❌ → `canvas.entryBarriers`로 흡수 |
| 인허가 제도 | 6/11 | ❌ → `submittedDocuments`·`bottlenecks`로 흡수 |
| 건축 관련 입찰제도 | 1/11 (네팔) | ❌ → `fieldVerification`으로 흡수 |

결측이 있는 섹션을 축으로 삼으면 아프리카·중남미·중동CIS로 확장할 때 빈 레코드가 생긴다.
11/11인 것만 축으로 두고 나머지는 있는 국가에 한해 하위 필드로 넣는다.

---

## 구조

```
├── data/
│   ├── institutions/*.json      제도별 정규화 데이터
│   └── manifest.json            국가·제도 진행 대장 (11개국 × 3축)
├── docs/
│   ├── data-contract.md         스키마 정의 — 작성 전 반드시 읽을 것
│   ├── verification-log.md      검증 대장 (자동 생성)
│   └── errata.md                자료집 정오표 (자동 생성)
├── sources/
│   ├── koica-2025-asia-pacific/
│   │   ├── extract.sh           자료집 PDF → 국가별 텍스트
│   │   └── pages/               추출된 원문 (117장 × 좌우 2면)
│   └── laws/nepal/              대조에 쓴 법령 원문 PDF
├── tools/
│   ├── validate.py              스키마 검증
│   ├── check_links.py           외부 링크 생존 확인
│   ├── build_docs.py            검증 대장·정오표 생성
│   ├── build_site.py            정적 사이트 생성
│   ├── board_adapter.mjs        process → korea100studio board-v1 변환
│   ├── check_boards.mjs         프로세스 보드 품질 게이트 (audit)
│   └── board-baseline.json      보드 품질 기준선
├── package.json                 Node 도구(게이트)의 devDependency
└── site/                        생성된 화면 (빌드 산출물)
```

`docs/verification-log.md`와 `docs/errata.md`는 **손으로 고치지 않는다.**
불일치는 JSON이 단일 출처이고 두 문서는 그것을 읽는 형식으로 옮긴 것이다.
실제로 손으로 관리하던 동안 데이터와 어긋났고(문서 8건 vs 데이터 10건), 그래서 생성으로 바꿨다.

---

## 쓰는 법

### 화면 만들기

```bash
python3 tools/build_site.py
```

`data/institutions/*.json`에서 정적 HTML을 생성한다. 의존성 없음.

| 경로 | 화면 |
|---|---|
| `site/index.html` | 제도 대장 — 검색, 국가·축 필터, 검증 배지, 불일치 건수 |
| `site/model/{slug}/index.html` | 한 장 요약 — 업무구조도 + 캔버스 + 불일치 + 검증 |
| `site/verification/index.html` | 검증 대장 — 불일치 전체와 미확인 항목 |
| `site/errata/index.html` | 정오표 — 발행처에 전달할 수정 제안과 그 상태 |

**업무구조도**는 레인 × 게이트 그리드에 노드를 놓고 엣지를 SVG로 잇는다.
원본 UI 규칙을 승계해 `current`(핵심)·`risk`(유의)·`loop`(회귀)만 강조하고 `done`·`waiting`은 중립으로 둔다.
노드를 누르면 담당·기한·산출문서·병목·근거조문·확신도가 열리고, 마우스를 올리면 연결된 노드만 남는다.

미리보기는 아무 정적 서버로나 띄운다.

```bash
python3 -m http.server 8765 --directory site
```

### 검증

```bash
python3 tools/validate.py
```

스키마 계약(`docs/data-contract.md`)의 체크리스트를 기계적으로 확인한다.
slug↔axis 규칙, `LegalBasisKind` 8종, `sourceRefs` 존재, 프로세스 노드/엣지 참조 무결성,
`article-verified`인데 `articlesChecked`가 없는 경우, 선언만 하고 노드가 없는 빈 레인·게이트 등을 잡는다.

### 링크 점검

```bash
python3 tools/check_links.py
```

법령 원문·기관 사이트 URL이 살아 있는지 확인한다. 근거를 검증하는 프로젝트에서
근거 링크가 깨져 있으면 곤란하므로 주기적으로 돌린다.

판정은 **정상 / 보류 / 죽음** 셋이다. 네팔 정부 사이트는 중간 인증서를 빠뜨려 보내는 곳이 많아
파이썬 기본 검증으로는 실패하지만 브라우저에서는 열린다. 그런 경우를 죽었다고 단정하지 않고
`curl`로 2차 확인한 뒤, 그래도 판정이 안 서면 **보류**로 남겨 사람이 보게 한다.
죽었다고 단정하는 것은 서버가 4xx/5xx로 명확히 없다고 답했을 때뿐이다.

### 프로세스 보드 품질 게이트 (선택)

```bash
npm install          # 최초 1회 — korea100studio(audit)를 설치
npm run check:boards
```

[korea100studio](https://github.com/hosungseo/korea100studio)의 `audit`으로 업무구조도의
구성 품질을 점검한다. 우리 `process`와 korea100studio의 board-v1 스키마는 거의 1:1이라
([board_adapter.mjs](tools/board_adapter.mjs) 30줄로 변환) 우리 데이터를 그대로 채점할 수 있다.
둘 다 korea100의 프로세스 렌더러에서 나왔기 때문이다.

**절대 판정이 아니라 회귀 감지다.** audit은 korea100studio의 세로 스윔레인 레이아웃 기준으로
채점하는데, 우리 화면([build_site.py](tools/build_site.py))은 가로 그리드라 배치가 다르다.
그래서 `stretch`·`crossings` 같은 레이아웃 의존 지표를 절대 기준으로 강제하면 거짓 실패가 난다.
대신 [baseline](tools/board-baseline.json)과 비교해 **이번 변경이 더 나쁘게 만들었는지**를 본다.

- **hard fail** — 노드 관통(`nodePiercings`)이 늘거나, 새 렌더 실패(엣지 과밀 `collinear`)가 생김.
  이 둘은 그래프 구조가 특정 지점에서 과밀하다는 렌더러 반중립 신호다.
- **경고** — `score` 악화, 레이아웃 의존 예산 초과. 우리 렌더에는 무해할 수 있어 확인만 권한다.

구조가 실제 제도 모습이라 불가피하면(예: 네팔 입찰의 P08은 4개 첨부요건 합류점) `npm run check:boards:update`로
baseline을 갱신한다. **이 게이트는 개발용 선택 도구다** — 데이터 검증은 `validate.py`가 담당하고,
배포 산출물에 Node는 들어가지 않는다.

> audit이 실제로 잡은 것: 우리가 스크린샷으로 "괜찮다"고 넘긴 보드 3개 중,
> 입찰제도는 P08 4중 합류로 board-v1 렌더 불가, ODA는 회귀 엣지 `E17`이 `P04`를 관통(우리 눈은 놓침)했다.
> board-v1과 우리 렌더는 배치가 달라 우리 화면에는 그대로 나타나지 않지만,
> "한 지점에 엣지가 몰린다"는 신호는 어느 렌더러에서든 유효하다.

### 자료집에서 원문 뽑기

```bash
./sources/koica-2025-asia-pacific/extract.sh "자료집.pdf" pages
```

자료집은 좌우 2면 스프레드로 조판돼 있어 그냥 `pdftotext`를 돌리면 좌우 텍스트가 한 줄에 섞인다.
이 스크립트는 페이지를 좌/우로 잘라 따로 추출한다. 국가별 페이지 범위는 `data/manifest.json`에 있다.

표가 섞인 면은 연속 공백을 구분자로 바꾸면 열 구조가 보인다.

```bash
sed -e 's/[[:space:]]\{3,\}/ | /g' sources/koica-2025-asia-pacific/pages/p007_R.txt
```

---

## 다음 국가를 추가할 때

1. `data/manifest.json`에서 해당 국가의 `pdfPages` 범위를 확인하고 `sources/.../pages/`의 해당 텍스트를 읽는다.
2. **자료집이 인용한 조문을 전부 뽑는다.**
3. 해당국 조달법·규칙 **영문 원문을 확보**한다. 먼저 조문 목록을 뽑아 **총 조문 수를 확인**한다.
   — 네팔 건은 이 단계에서 "법은 76조뿐"이 나왔고, 덕분에 자료집의 "141 조항"이 규칙 조항임을 특정할 수 있었다.

   ```bash
   pdftotext -layout law.pdf law.txt
   grep -nE "^[[:space:]]*[0-9]+\.[[:space:]]+[A-Z]" law.txt
   ```
4. 인용 조문을 하나씩 대조하고, 금액·비율·기한은 원문 표와 맞춘다.
5. **자료집이 말하지 않은 것도 본다.** 근거 문서를 읽다 보면 자료집에 없는 의무가 나온다.
   네팔 `high` 2건 중 1건이 여기서 나왔다.
6. **근거 문서가 아직 살아 있는지 확인한다.** 폐지·개정됐으면 대조 자체가 무의미해진다.
   네팔 건은 자료집이 전제한 정책이 발행 2개월 뒤 폐지된 것이 이 단계에서 드러났다.
7. `docs/data-contract.md`에 맞춰 3개 JSON을 쓰고 `python3 tools/validate.py`를 통과시킨다.
8. 불일치는 `verification.discrepancies`에 `action`·`userAction`·`upstream`까지 채워 넣는다.
9. `python3 tools/build_docs.py && python3 tools/build_site.py`로 문서와 화면을 다시 만든다.
   국가·제도가 늘면 목록·필터·통계·정오표가 자동으로 따라온다.
10. (선택) `npm run check:boards`로 새 프로세스 보드의 구성 품질이 회귀하지 않았는지 본다.
    한 지점에 엣지가 몰리면(합류·전역 회귀) 여기서 잡힌다.

작성 원칙은 [데이터 계약 §5](docs/data-contract.md)에 있다. 핵심은 하나다 —
**불일치를 적을 때 자료집이 틀렸다고 쓰지 말고, 무엇이 어떻게 다르며 실무에 어떤 영향인지 쓴다.**
"141 조항" 건처럼 자료집이 옳은데 표기만 부족한 경우가 있다.

---

## 확장 계획

| 지역 | 국가 수 | 자료집 | 상태 |
|---|---|---|---|
| 아시아·태평양 | 11 | 확보 | 네팔 완료, 10개국 대기 |
| 아프리카 | ? | 미확보 | — |
| 중남미 | ? | 미확보 | — |
| 중동·CIS | ? | 미확보 | — |

국가당 3개 기준으로 아시아·태평양만 33개다. 4개 지역을 합치면 100개 규모가 된다.

---

## 검증 상태 배지

| 값 | 의미 |
|---|---|
| `source-document` | 자료집 기재만 확인. 법령 원문 미연결 |
| `law-linked` | 근거 법령 원문 URL 연결 완료. 조문 대조는 미실시 |
| `article-verified` | 인용 조문을 원문에서 실제 확인 |
| `needs-review` | 불일치 발견 또는 근거 확인 불가 |

`article-verified`는 **조문의 존재와 문언 일치**만 뜻한다.
법적 해석·적용 타당성·현행 유효성(개정 반영 여부)은 별도 검토 대상이다.

---

## 면책

협력국 조달제도 이해를 위한 참고 자료다.
개별 입찰 건의 법률 자문이나 해당국 정부·KOICA의 공식 해석을 대신하지 않는다.
조달법은 개정이 잦다 — 실제 입찰 전 발주처 공고문과 현행 법령을 반드시 확인해야 한다.

확인된 개정 감시 대상은 [검증 대장](docs/verification-log.md#개정-감시-대상)에 있다.
