# overseas-procurement-100 데이터 계약 v0.1

`how-did-they-do-all-that-procurement`(국내 조달제도 100)의 Institution 스키마를
**협력국 조달제도**용으로 변형한 단일 진실 원천(Single Source of Truth)이다.

- 원본: 대한민국 1개국 × 제도 66개, 근거 = 국가법령정보센터
- 본 프로젝트: 협력국 33개국 내외 × 국가당 제도 3개, 근거 = KOICA 자료집 + 각국 조달법 원문

---

## 1. 원본 대비 변경점

| 항목 | 원본(korea100/procurement) | 본 프로젝트 | 변경 이유 |
|---|---|---|---|
| 레코드 단위 | 제도 | **국가 × 제도 3축** | 국가 간 비교가 목적. 4개 대륙 확장 시 결측 없는 축만 채택 |
| `country` | 없음(전부 한국) | **신규 필수 블록** | 국가 비교·필터의 기준키 |
| `LegalBasisKind` | 법률/대통령령/부령… | **법계 중립 8종** | 각국 법령 위계가 상이(Act/Rules/Ordinance/Directive…) |
| `verification.status` | source-linked / article-verified / needs-review | **4단계로 확장** | 자료집만 있는 상태와 원문 링크 상태를 구분해야 함 |
| `verification.discrepancies` | 없음 | **신규** | 자료집↔원문 불일치가 본 프로젝트의 핵심 산출물 |
| `sourceRefs` | 없음 | **신규 필수** | 모든 서술이 자료집 몇 쪽에서 왔는지 역추적 |

> 원본의 `canvas` 9칸 구조와 `process`(lanes/stages/nodes/edges)는 **그대로 승계**한다.

---

## 2. 제도 3축 (모든 국가 공통)

11개국 전수 조사 결과 아래 3축만 11/11로 존재한다. 인허가(6/11)·건축입찰(1/11)·
진출유의사항(7/11)은 축으로 쓰면 다른 대륙 확장 시 결측이 생기므로,
**존재하는 국가에 한해 해당 제도의 하위 필드로 흡수**한다.

| axis | slug 접미사 | 담는 내용 |
|---|---|---|
| `bidding` | `-bidding-system` | 입찰 방식 체계(공개/제한/지명/직접구매), 근거법, 입찰 자격·보증금·유효기간·서류비용 |
| `governance` | `-procurement-governance` | 조달 총괄기관, 전자조달 포털, 공고 채널, 이의제기·블랙리스트 |
| `pipeline` | `-oda-project-pipeline` | 수원 총괄기관, 사업 발굴·반영 절차(PCP→예비조사→PD→RoD→MoU) |

---

## 3. 파일 배치

| 경로 | 용도 | 생성 |
|---|---|---|
| `data/institutions/{slug}.json` | 제도별 원본 | 수동 |
| `data/manifest.json` | 국가·제도 진행 대장 | 수동 |
| `docs/data-contract.md` | 본 문서 | 수동 |
| `docs/verification-log.md` | 검증 대장(불일치 공개) | 수동 |
| `sources/koica-2025-asia-pacific/` | 자료집 원문 추출 텍스트 | `extract.sh` |

---

## 4. Institution 스키마

### 4.1 기본 메타데이터

```ts
slug: string;        // 필수. "{country-slug}-{axis-suffix}" 예: "nepal-bidding-system"
name: string;        // 필수. "네팔 공공조달 입찰제도"
oneLiner: string;    // 필수. 한 줄 요약
axis: "bidding" | "governance" | "pipeline";   // 필수. 3축 중 하나
type: string;        // 필수. 제도 성격. "경쟁조달형" / "감독·집행형" / "사업형성형"
priority: number;    // 필수. 매니페스트 순번
asOfDate: string;    // 필수. 근거 자료 기준일 "YYYY-MM-DD"
status: "full" | "canvas";   // full = canvas + process, canvas = 9칸만
```

### 4.2 country 블록 (신규)

```ts
country: {
  name: string;       // 필수. "네팔"
  nameEn: string;     // 필수. "Nepal"
  iso3: string;       // 필수. "NPL"
  region: string;     // 필수. "아시아·태평양"
  incomeGroup?: string;        // 선택. "LDC" 등
  koicaOffice?: boolean;       // 선택. KOICA 현지사무소 유무
};
```

### 4.3 canvas 9칸 (원본 승계)

```ts
canvas: {
  purpose: string;              // 1. 제도의 목적
  stakeholders: string;         // 2. 이해관계자
  legalBasis: LegalBasis[];     // 3. 법적 근거
  authorities: Authority[];     // 4. 권한 관계자
  procedure: string[];          // 5. 대표 절차 6~10단계
  applicability: string;        // 6. 적용 대상(금액구간·요건)
  submittedDocuments: DocSet[]; // 7. 제출서류
  bottlenecks: string[];        // 8. 병목 지점
  entryBarriers?: string[];     // 9. (해외판 신규) 우리 기업 진입장벽
};
```

`entryBarriers`는 원본에 없던 칸이다. 자료집의 `진출 장애요인`·`진출 유의사항`이
축으로 삼기엔 결측이 많아(7/11) 여기로 흡수한다. 없으면 필드 자체를 생략한다.

```ts
interface LegalBasis {
  law: string;        // 필수. "Public Procurement Act, 2063 (2007)"
  lawKo?: string;     // 선택. "공공조달법"
  articles?: string;  // 선택. "§9, §11, §12"
  kind: LegalBasisKind;  // 필수
  url?: string;       // 선택. 원문 주소를 직접 지정할 때만
}

interface Authority {
  name: string;
  role: string;
  url?: string;       // 선택. 기관 공식 사이트
}

interface DocSet { actor: string; documents: string[]; }
```

### 링크 규칙

화면의 법령명·기관명은 원문과 공식 사이트로 연결된다. 연결에는 두 가지 원칙이 있다.

**1. 법령 링크는 `verification.sources`가 단일 출처다.**
`legalBasis[].law`가 `verification.sources[].law`(또는 `officialName`)와 일치하면
빌더가 그 `officialUrl`을 자동으로 건다. 같은 주소를 두 곳에 적지 않는다.
프로세스 노드의 `legal_basis[].law`도 같은 방식으로 연결된다.
`sources`에 없는 문서(RoD·MoU처럼 비공개인 것)는 링크 없이 평문으로 남는다 —
**이것이 정상 동작이다.** 링크가 없다는 사실 자체가 "공개 원문이 없다"는 정보다.

**2. 확인한 URL만 적는다.**
`authorities[].url`은 실제로 접속해 확인한 주소만 넣는다. 도메인 추정(`ird.gov.np`처럼
그럴듯한 패턴)으로 채우지 않는다. 확인하지 못했으면 필드를 비운다.
근거를 검증하는 프로젝트가 링크에서 추정을 하면 신뢰가 무너진다.

특정 기관이 아닌 일반 개념(`발주 공공기관`, `주·지방정부`, `네팔 상업은행`)에는
`url`을 넣지 않는다.

### 4.4 LegalBasisKind (법계 중립 8종)

각국 법령 위계 명칭이 제각각이라 기능 기준으로 통일한다.

| 값 | 의미 | 예 |
|---|---|---|
| `act` | 의회 제정 법률 | Public Procurement Act 2007 |
| `regulation` | 시행규칙·시행령 | Public Procurement Rules 2007 |
| `ordinance` | 명령·조례·긴급입법 | Public Procurement (Second Amendment) Ordinance |
| `directive` | 지침·가이드라인 | PPMO Standard Bidding Document |
| `standard-document` | 표준 입찰·계약 양식 | SBD, RFP 양식 |
| `treaty-agreement` | 양자·다자 협정 | RoD, MoU, 차관협정 |
| `donor-rule` | 공여기관 조달규정 | KOICA·ADB·World Bank Procurement Guidelines |
| `practice` | 법령 근거 없는 현장 관행 | — 반드시 `fieldVerification` 동시 등재 |

### 4.5 sourceRefs (신규 필수)

모든 레코드는 자료집 어느 쪽에서 왔는지 역추적 가능해야 한다.

```ts
sourceRefs: Array<{
  document: string;   // 필수. "KOICA 2025 국가별 개발협력사업 참여전략 자료집(아시아·태평양)"
  pages: string;      // 필수. 자료집 인쇄 쪽 번호. "10-13"
  pdfPages?: string;  // 선택. PDF 물리 페이지. "7-8"
  section: string;    // 필수. "Ⅲ-1. 협력국 입찰 제도"
}>;
```

### 4.5a sourceQuotes (현장 대응용 원문 인용)

한국어 서술만으로는 현지에서 발주처와 다툴 때 근거가 되지 못한다. 우리 요약이 아니라
**법령 조문 원문 그 자체**를 제시할 수 있어야 한다. `sourceQuotes`는 대조에 실제로 쓴
핵심 조문의 영문 verbatim을 담는다 — 그대로 복사해 현장에서 인용할 수 있는 형태다.

```ts
sourceQuotes?: Array<{
  law: string;        // 필수. verification.sources[].law와 일치 (URL 자동 연결)
  article: string;    // 필수. "reg.23(6)", "§131(1)"
  quote: string;      // 필수. 영문 원문 verbatim. 의역·축약 금지 — 원문 그대로
  gist: string;       // 필수. 이 조문이 실무에 뜻하는 바(한국어 한 줄)
  ko?: string;        // 선택. 원문의 한국어 직역(참고용). 공식 번역이 아님을 전제
}>;
```

규칙
- `quote`는 **원문 그대로**다. 우리가 읽기 쉽게 고치지 않는다. 줄바꿈·조판 잔재는 공백으로 정리하되
  단어·어순은 손대지 않는다. 원문에 오탈자가 있으면 그대로 두고 `gist`에서 설명한다.
- 한 제도가 인용한 핵심 조문은 모두 담는다. 최소한 discrepancy·process의 `legal_basis`에서
  근거로 든 조문은 원문이 있어야 한다.
- 원문을 확보하지 못한 근거(정책·관행, RD·MoU 같은 비공개 문서)는 `sourceQuotes`에 넣지 않는다.
  그런 항목이 근거의 다수면 `verification.status`가 `source-document`에 머무는 것이 정상이다.
- `law`는 `verification.sources[].law`와 문자열이 같아야 원문 URL이 자동 연결된다.

### 4.6 verification 블록

```ts
verification: {
  status: VerificationStatus;   // 필수
  verifiedAt: string;           // 필수. YYYY-MM-DD
  method: string;               // 필수. 검증 방법 서술
  scope: string;                // 필수. 검증한 범위와 남은 항목
  notes?: string[];             // 선택. 개정 예정 등

  sources: Array<{
    law: string;            // 필수
    kind: LegalBasisKind;   // 필수
    officialName?: string;  // 선택. 원문 정식 명칭
    publisher?: string;     // 선택. "Nepal Law Commission" / "PPMO"
    officialUrl: string;    // 필수. 원문 URL
    retrievedOn: string;    // 필수. 원문 확인일 YYYY-MM-DD
    articlesChecked?: string;  // 선택. 실제 대조한 조문
  }>;

  discrepancies?: Discrepancy[];  // 선택. 자료집↔원문 불일치
  unresolved?: Unresolved[];      // 선택. 확인 못 한 항목
};
```

#### VerificationStatus (4단계)

| 값 | 의미 | 배지 |
|---|---|---|
| `source-document` | 자료집 기재만 확인. 법령 원문 미연결 | 회색 |
| `law-linked` | 근거 법령 원문 URL 연결 완료. 조문 대조는 미실시 | 파랑 |
| `article-verified` | 인용 조문을 원문에서 실제 확인 | 초록 |
| `needs-review` | 불일치 발견 또는 근거 확인 불가 | 빨강 |

> `article-verified`는 **조문의 존재와 문언 일치**만 뜻한다.
> 법적 해석·적용 타당성·현행 유효성(개정 반영 여부)은 별도 검토 대상이다.

#### Discrepancy (본 프로젝트의 핵심 산출물)

```ts
interface Discrepancy {
  id: string;         // 필수. "{slug}-D01"
  severity: "high" | "medium" | "low";   // 필수
  field: string;      // 필수. 불일치가 있는 canvas 경로
  sourceText: string; // 필수. 자료집의 서술 (원문 인용)
  actualText: string; // 필수. 법령 원문의 실제 내용
  citation: string;   // 필수. 확인한 조문
  impact: string;     // 필수. 실무자에게 미치는 영향

  // ── 조치 3종. 발견에서 끝내지 않기 위한 필수 세트 ──
  action: string;     // 필수. 본 데이터에 무엇을 반영했나
  userAction: string; // 필수. 실무자가 당장 할 일
  upstream?: Upstream; // 선택. 자료집 발행처의 정정이 필요할 때만

  // 이 불일치가 자료집의 어느 대목인지. 제도 전체의 sourceRefs[0]과 다를 때만 적는다.
  // 정오표는 발행처가 해당 쪽을 펴 봐야 하는 문서라 쪽수가 정확해야 한다.
  sourcePage?: string;     // 예: "17"
  sourceSection?: string;  // 예: "Ⅲ. 통관 등 관련 사항(시공/기자재)"

  // 현지 직원(영어) 검증용. 이 불일치를 실제로 확인하는 사람이 한국어를 못 읽을 수 있다.
  review?: DiscrepancyReview;
}

interface DiscrepancyReview {
  topic: string;      // 영어 주제 (짧게). "Agent's required documents"
  guideSays: string;  // 자료집이 뭐라 했는지 영어. 현지 직원은 한국어 자료집을 못 읽는다.
  lawSays: string;    // 법령이 실제로 뭐라 하는지 영어 (원문 요지 + 조문)
  impact: string;     // 왜 문제인지 영어
  verify: string;     // 현장에서 확인할 것 — 영어 행동 지시. "Confirm with the procuring entity that..."
}

interface Upstream {
  priority: "정정 요망" | "보완 권고";  // 필수
  state: UpstreamState;                 // 필수
  suggestedText: string;                // 필수. 자료집을 이렇게 고치면 된다는 대안 문안
  note?: string;                        // 선택. 제보 경위·회신 내용
}

type UpstreamState =
  | "not-reported"   // 아직 발행처에 알리지 않음
  | "reported"       // 제보함, 회신 대기
  | "acknowledged"   // 발행처가 확인함
  | "fixed"          // 개정판에 반영됨
  | "declined";      // 발행처가 정정 불요로 판단
```

severity 기준
- `high` — 그대로 따르면 **입찰 자격 상실·서류 반려**로 이어짐
- `medium` — 근거 조문·출처 오표기. 내용은 맞으나 역추적이 막힘
- `low` — 표기·번역 흔들림. 실무 영향 미미

upstream priority 기준
- `정정 요망` — 자료집 서술이 실무 손해로 이어지거나 자료집 안에서 서로 모순됨
- `보완 권고` — 서술은 맞으나 출처 표기·누락 보완이 필요

**`upstream`을 생략한다는 것은 발행처가 고칠 것이 없다는 뜻**이다. 판단을 미루는 용도로 비워 두지 않는다.

### 조치를 왜 3종으로 나누나

불일치를 찾아 놓고 배지만 띄우면 읽는 사람은 무엇을 해야 할지 알 수 없다. 셋은 수신자가 다르다.

| 필드 | 수신자 | 답하는 질문 |
|---|---|---|
| `action` | 이 데이터셋 | 우리 데이터는 어느 쪽을 따랐나 |
| `userAction` | 입찰 준비자 | 내가 지금 무엇을 다르게 해야 하나 |
| `upstream` | 자료집 발행처 | 다음 판에서 무엇을 고쳐야 하나 |

`upstream`이 있는 항목은 `docs/errata.md`에 정오표로 모여 발행처에 전달할 수 있는 형태가 된다.
전달 후에는 `state`를 갱신해 후속을 추적한다.

### review — 현지 직원이 검증하는 사람이다

이 데이터의 최종 검증자는 KOICA 해외사무소 직원이고, 현지 직원이면 한국어를 못 읽는다.
불일치의 법령 원문(`actualText`)·조문(`citation`)은 이미 영어지만, 자료집 서술(`sourceText`)과
영향·행동(`impact`·`userAction`)은 한국어라 정작 확인할 사람이 못 읽는다. `review`는 그 간극을 메운다.

- `guideSays` — 자료집이 뭐라 했는지 영어로. 현지 직원은 한국어 자료집을 펴 볼 수 없으니 여기서 읽는다.
- `verify` — **현장에서 무엇을 확인할지** 영어 행동 지시. 이게 검토 시트의 핵심이다.
  "발주처 입찰서류에서 보증 금액을 확인하라", "현행 규정 reg.X와 대조하라"처럼 실행 가능해야 한다.

`review`가 있는 불일치는 `tools/build_docs.py`가 `docs/review-sheet.en.md`(영어 검토 시트)로 모은다.
현지 직원이 이 시트를 들고 원문·발주처와 대조한다. **`high`·`medium` 불일치는 `review`를 채우는 것을 원칙으로 한다** —
실무 손해로 이어지는 것일수록 현지에서 확인돼야 하기 때문이다.

#### Unresolved

```ts
interface Unresolved {
  law: string;
  kind: LegalBasisKind;
  reasonCode: "no-public-text" | "local-language-only" | "paywalled"
            | "donor-internal" | "site-unreachable" | "title-needs-confirmation";
  reason: string;
  nextStep: string;
}
```

### 4.7 related / fieldVerification

```ts
related: string[];            // 필수. 관련 제도 slug
fieldVerification: string[];  // 필수. 현장 검증 필요 항목. 없으면 []
```

### 4.8 process (status="full"일 때 필수)

원본 `ProcessModel`을 그대로 승계한다.

```ts
process?: {
  lanes: string[];    // 행위주체 레인
  stages: string[];   // 게이트 단계
  nodes: ProcessNode[];
  edges: ProcessEdge[];
  warnings?: string[];
};

interface ProcessNode {
  id: string;         // "P01"
  name: string;
  lane: string;       // lanes 중 하나
  stage: string;      // stages 중 하나
  type: "task" | "gateway" | "notice" | "system";
  status: "done" | "current" | "waiting" | "risk" | "loop";
  actor: string;
  action?: string;
  output_documents?: string[];
  deadline?: string;
  blocker?: string | null;
  confidence?: number;   // 0~1. <0.8이면 UI에 "현장 검증 필요"
  legal_basis?: Array<{ law: string; article: string }>;
}

interface ProcessEdge {
  id: string;
  source: string;
  target: string;
  type: "sequence" | "message" | "loop";
  label?: string | null;
}
```

원본 UI 규칙 승계: `current`·`risk`·`loop`만 강조하고 `done`·`waiting`은 중립 표시.
진행률 어휘("완료/현재/대기")로 읽히게 하지 않는다.

---

## 5. 작성 규칙

1. **원문 우선** — 자료집 서술을 옮기기 전에 근거 법령 원문을 먼저 확보한다.
2. **인용은 원문 표기로** — `제41(a)조`처럼 자료집이 축약한 인용은
   원문 체계(`§41(1)(a)`)로 교정하고, 교정 사실을 `discrepancies`에 남긴다.
3. **수치는 3종 세트** — 금액·비율·기한은 `값 + 근거조문 + 확인일`을 함께 기록한다.
4. **법정과 관행을 구분** — 자료집의 "일반적으로", "통상"은 `kind: "practice"`로
   분류하고 `fieldVerification`에 등재한다.
5. **번역 왜곡 감시** — 자료집은 한국어 의역본이다. 서류명·기관명은
   원문 영문 명칭을 병기한다. (실제로 네팔 건에서 `high` 1건이 여기서 나왔다.)
6. **개정 감시** — 조달법은 개정이 잦다. 원문 사이트에 자료집 기준일 이후
   개정본이 있으면 `verification.notes`에 반드시 기록한다.

---

## 6. 데이터 검증 체크리스트

- [ ] `slug`가 `{country-slug}-{axis-suffix}` 규칙을 따르는가
- [ ] `axis` 값이 3축 중 하나인가
- [ ] 모든 `legalBasis[].kind`가 `LegalBasisKind` 8종 안에 있는가
- [ ] `sourceRefs`가 비어 있지 않은가 (자료집 역추적 가능)
- [ ] `canvas.procedure` 길이가 6~10인가
- [ ] `status: "full"`이면 `process`가 있는가
- [ ] `process.nodes[].lane`/`stage`가 선언된 목록에 존재하는가
- [ ] 모든 `edges[].source`/`target`이 유효한 노드 ID인가
- [ ] `confidence`가 0~1 범위인가
- [ ] `verification.sources[].retrievedOn`이 기재됐는가
- [ ] `discrepancies[].severity`가 3종 중 하나인가
- [ ] `practice`로 분류한 항목이 `fieldVerification`에도 있는가

---

## 7. 면책

본 데이터는 협력국 조달제도 이해를 위한 참고 자료다.
개별 입찰 건의 법률 자문이나 해당국 정부·KOICA의 공식 해석을 대신하지 않는다.
조달법은 개정이 잦으므로 실제 입찰 전 반드시 발주처 공고문과 현행 법령을 확인해야 한다.
