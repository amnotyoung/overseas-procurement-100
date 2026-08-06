# 국가별 건축 법·제도 데이터 계약 v0.1

`data/construction-regulations/{country}.json`은 ODA 건축사업의 조사·설계·인허가·시공·준공·운영 단계에서 확인할 법과 제도를 국가별로 정규화한 단일 진실 원천이다. 원천 스키마와 검증은 기존 조달 3축(`bidding`, `governance`, `pipeline`)과 분리하지만, 공개 사이트에서는 같은 국가의 조달 1~3번 뒤에 `construction` 4번부터로 통합한다.

> 이 데이터는 사업기획과 현지조사를 돕는 검증 대장이다. 법률자문, 관할기관의 유권해석, 개별 사업의 인허가를 대신하지 않는다.

## 1. 설계 원칙

1. **법령 목록이 아니라 의사결정 자료로 만든다.** 모든 의무를 사업 생애주기와 Gate 질문에 연결한다.
2. **현행·폐지·개정예고를 섞지 않는다.** `in_force`, `superseded`, `pending`, `continuity_unverified`를 구분한다.
3. **원문 확인 깊이를 드러낸다.** 링크만 연결한 근거와 조문까지 대조한 근거를 구분한다.
4. **국가 공통 규칙과 부지 특례를 분리한다.** 도시계획구역, 특구, 문화재·연안·재해구역 등은 `siteOverlays`에 둔다.
5. **미확정은 0이나 ‘해당 없음’으로 바꾸지 않는다.** `openQuestions`에 필요한 증빙, 확인기관, 보고서 영향을 남긴다.
6. **공식 서비스 페이지보다 최신 법령을 우선한다.** 안내 페이지가 개정 법령을 반영하지 않았으면 그 충돌을 명시한다.

## 2. 파일 배치

| 경로 | 용도 | 생성 |
|---|---|---|
| `data/construction-regulations/manifest.json` | 스키마·대상국·진행 상태 | 수동 |
| `data/construction-regulations/{country}.json` | 국가별 원천 데이터 | 수동 |
| `docs/construction-regulations-data-contract.md` | 이 데이터 계약 | 수동 |
| `docs/construction-regulations/{country}.md` | 전문가용 국가 브리프 | `build_construction_regulations.py` |
| `tools/validate_construction_regulations.py` | 구조·참조·근거 검증 | 수동 |
| `tools/build_construction_regulations.py` | Markdown 생성 | 수동 |
| `tools/build_construction_boards.mjs` | `processBoard`를 korea100studio SVG로 렌더 | 수동 |
| `tools/check_construction_site.py` | 통합 model·클릭 구조도·이전 URL·감사용 SVG 확인 | 수동 |

생성 문서는 직접 고치지 않는다. 원천 JSON을 수정한 뒤 다시 빌드한다.

## 3. 검증 상태

### 3.1 법령 상태 `instruments[].status`

| 값 | 의미 |
|---|---|
| `in_force` | 기준일 현재 현행으로 확인 |
| `superseded` | 폐지·대체 근거를 확인 |
| `pending` | 의회·정부에서 심의 중이나 아직 현행이 아님 |
| `continuity_unverified` | 구법 시행령 등 존속 범위를 원문만으로 확정하지 못함 |

### 3.2 근거 확인 `verificationLevel`

| 값 | 의미 |
|---|---|
| `article-verified` | 공식 원문에서 관련 조문을 직접 확인 |
| `law-linked` | 공식 원문 링크와 문서 식별정보를 확인했으나 관련 조문 전수 대조 전 |
| `source-linked` | 공식 기관 안내·조직·절차 페이지에 연결 |
| `needs-review` | 원문 또는 현지 확인이 더 필요 |

`article-verified`는 조문의 존재와 문언을 확인했다는 뜻이다. 특정 사업에 적용된다는 최종 판단은 `requirements[].applicability`와 `openQuestions`에서 별도로 관리한다.

## 4. 최상위 구조

```ts
{
  schemaVersion: "0.1";
  slug: string;
  asOfDate: "YYYY-MM-DD";
  country: {
    name: string;
    nameEn: string;
    iso3: string;
    region: string;
  };
  purpose: string;
  pilotContext?: ProjectContext;
  verification: VerificationSummary;
  processBoard: ConstructionProcessBoard;
  publicModels?: PublicConstructionModel[];
  authorities: Authority[];
  instruments: Instrument[];
  requirements: Requirement[];
  permitPath: PermitGate[];
  siteOverlays: SiteOverlay[];
  openQuestions: OpenQuestion[];
  fieldworkChecklist: ChecklistItem[];
  reportReadyConclusions: Conclusion[];
}
```

`pilotContext`는 특정 사업에 맞춘 적용 가설이다. 국가 공통 사실과 혼동하지 않도록 확인된 입력(`known`)과 미확정 입력(`unknown`)을 나눠 적는다.

`publicModels`는 하나의 국가 원천을 공개 사이트의 독립 제도축으로 나누는 표시 계약이다. 세네갈 파일럿은 조달 3종과 균형을 맞춰 `도시계획·부지규제`, `건축허가·환경심사`, `기술검사·보험·준공제도` 3종을 4~6번으로 공개한다. 법령·의무·질문을 복제하지 않고 전체 `processBoard`의 노드와 공통 대장을 참조한다.

## 5. 핵심 객체

### 5.1 법령·공식자료 `Instrument`

```ts
{
  id: string;                       // 국가 내 유일
  title: string;                    // 원문 정식명
  titleKo: string;
  kind: "act" | "decree" | "order" | "plan" | "official-guidance" | "draft";
  status: "in_force" | "superseded" | "pending" | "continuity_unverified";
  issuedOn?: "YYYY-MM-DD";
  publishedOn?: "YYYY-MM-DD";
  officialUrl: string;
  officialPdfUrl?: string;
  verificationLevel: "article-verified" | "law-linked" | "source-linked" | "needs-review";
  articlesChecked?: string[];
  replaces?: string[];              // 다른 instrument id
  replacedBy?: string[];            // 다른 instrument id
  note?: string;
}
```

폐지된 법령도 지우지 않는다. 공식 포털의 오래된 안내를 걸러내고 과거 보고서의 인용을 진단하기 위한 대조표로 남긴다.

### 5.2 생애주기 의무 `Requirement`

```ts
{
  id: string;
  stage: "site-and-land" | "programming" | "design" | "environment" |
         "permit" | "pre-construction" | "construction" | "completion" | "operation";
  topic: string;
  status: "confirmed" | "conditional" | "unresolved";
  applicability: string;
  requirement: string;
  authorityIds: string[];
  legalBasis: Array<{ instrumentId: string; provisions: string[] }>;
  evidenceToObtain: string[];
  reportUse: string;
}
```

- `confirmed`: 법적 의무와 적용범위를 현재 입력으로 확인함.
- `conditional`: 층수·연면적·ERP 분류·발주주체 등 사업 입력에 따라 적용됨.
- `unresolved`: 법령·시행규칙·현지 관행을 추가 확인해야 함.

### 5.3 부지 특례 `SiteOverlay`

```ts
{
  id: string;
  area: string;
  status: "confirmed" | "conditional" | "unresolved";
  rule: string;
  legalBasis: Array<{ instrumentId: string; provisions: string[] }>;
  missingEvidence: string[];
  consequence: string;
}
```

계획을 승인한 법령이 있어도 도면·조례·필지별 용도지역표가 공개되지 않았다면 `confirmed`로 단정하지 않는다. 승인 사실은 확인하되 필지 적용은 `unresolved`로 둔다.

### 5.4 미확정 질문 `OpenQuestion`

```ts
{
  id: string;
  blocking: boolean;
  stage: string;
  question: string;
  whyItMatters: string;
  evidenceNeeded: string[];
  confirmWith: string[];             // authority id 또는 사업 당사자
  owner: string;
}
```

`blocking: true`는 답이 없으면 부지 적법성, 공간·구조·설비 개념, 비용, 일정 또는 조달전략을 확정할 수 없다는 뜻이다.

### 5.5 제도 구조도 `ConstructionProcessBoard`

`processBoard`는 [korea100studio board-v1](https://github.com/amnotyoung/korea100studio)의 `gov` 프로필 입력이다. 법령 목록을 단순 나열하지 않고 행위주체 × 단계 × 업무와 보완 회귀를 구조도로 만든다.

```ts
{
  schema_version: 1;
  profile: "gov";
  title: string;
  subtitle: string;
  lanes: string[];                  // 행위주체
  stages: string[];                 // G0, G1 … 순차 단계
  nodes: Array<{
    id: string;
    lane: string;
    stage: string;
    label: string;
    emphasis: "lead" | "key" | "bottleneck" | "loop" | "normal";
    note?: string;
    authorityIds?: string[];
    requirementIds?: string[];
    gateOrders?: number[];          // permitPath[].order
    refs: Array<{
      source: string;               // 구조도에 표시할 짧은 근거명
      instrumentId: string;
      provisions: string[];
    }>;
  }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
    type: "sequence" | "message" | "loop";
    label?: string;
  }>;
}
```

### 5.6 공개 제도축 `PublicConstructionModel`

```ts
{
  id: string;
  slug: string;                     // ...-construction-regulations
  priority: number;                 // 조달 1~3 뒤의 4 이상
  name: string;
  oneLiner: string;
  purpose: string;
  verificationScope: string;        // 이 공개축에서 실제로 노출하는 대조 범위
  nodeIds: string[];                // 전체 processBoard.nodes 참조
  requirementIds: string[];         // requirements 참조, 축 간 내용 혼입 방지
  questionIds: string[];            // openQuestions 참조
  conclusionIds: string[];          // reportReadyConclusions 참조
  siteOverlayIds: string[];         // siteOverlays 참조, 없으면 빈 배열
  fieldworkChecklistIds: string[];  // fieldworkChecklist 참조
  edges: ConstructionProcessBoard["edges"];
}
```

- 각 공개 제도축은 선택한 노드만으로 독립적으로 연결된 클릭형 구조도를 만든다.
- 한 국가의 공개 제도축 전체를 합치면 원천 노드, 의무, Gate, 질문, 결론, 부지 특례와 현지조사 체크리스트가 빠짐없이 포괄돼야 한다. `requirementIds`는 각 의무를 한 축에만 배정해 선택 노드의 다른 주제가 섞이지 않게 한다.
- 여러 제도에 공통인 법령·Gate·결론은 중복 표시할 수 있지만 원천 객체를 복제하지 않는다.
- 공개 보드의 생애주기 단계는 `S0…`, 법정 인허가 절차는 `P1…`로 표시해 서로 다른 순번 체계를 구분한다.

- `permitPath`는 일정·산출물 중심의 법정 Gate 대장이고, `processBoard`는 기관 간 인계·병렬협의·보완회귀를 보여주는 시각 모델이다. 서로 대체하지 않는다.
- 모든 Gate 순번은 최소 한 개의 보드 노드 `gateOrders`에 연결한다.
- 모든 노드는 근거 `refs`를 갖고 기존 법령 ID·요구사항·기관으로 역추적할 수 있어야 한다.
- 공개 화면은 `build_site.py`가 `processBoard` 또는 `publicModels` 투영을 기존 model 템플릿의 HTML 버튼·동적 연결선·상세 패널로 변환한다. 국가별 조달 3축 뒤에 `priority: 4`부터 배치하며, 기존 `/construction/{country}/`와 단일 건축 model 주소는 첫 건축 model로 이동한다.
- 카드의 `담당`은 lane의 책임주체이고 `authorityIds`는 `협의·관할기관`으로 따로 표시한다. 카드 근거는 `processBoard.refs`와 연결된 모든 `requirements[].legalBasis`를 합쳐야 한다.
- 법령·자료의 원래 `kind`, `status`, `verificationLevel`, `note`를 보존한다. `pending` 법안과 `continuity_unverified` 안내자료는 현행 법적 근거 목록에 섞지 않고 검증 대장에서 상태 배지와 함께 표시한다.
- `reportReadyConclusions`, `siteOverlays`, `openQuestions`, `permitPath.dependsOn`은 통합 model에서도 생략하지 않는다. 국가별 표시 보정과 법정기한은 다른 국가에 재사용하지 않는다.
- `npm run build:construction-boards`의 SVG는 공개 본문 이미지가 아니라 `korea100studio validate --strict`, `render`, `check`를 위한 구성 감사 산출물이다.

## 6. 참조 무결성 규칙

- 모든 `authorityIds`, `instrumentId`, `replaces`, `replacedBy`는 같은 파일 안의 ID를 가리켜야 한다.
- 현행 법령은 공식 URL과 `issuedOn`을 가져야 한다.
- `article-verified` 근거는 비어 있지 않은 `articlesChecked`를 가져야 한다.
- `confirmed`·`conditional` 의무는 최소 한 개의 법적 근거와 증빙목록을 가져야 한다.
- `superseded` 법령은 `replacedBy`를, 대체 법령은 가능한 경우 `replaces`를 적는다.
- 모든 차단 질문은 증빙과 확인 상대를 지정해야 한다.
- 기준일보다 뒤 날짜의 법령은 `in_force`로 둘 수 없다.
- `processBoard`의 lane·stage·node·edge ID는 유일해야 하고 모든 참조 대상이 존재해야 한다.
- `processBoard`의 모든 노드는 연결돼 있어야 하며 모든 `permitPath` 순번을 포괄해야 한다.
- 새 구조도는 korea100studio 감사에서 노드 관통 0건과 strict 구성예산을 충족해야 한다.

## 7. ODA 건축보고서 적용 순서

1. `pilotContext.unknown`과 `openQuestions[blocking=true]`를 Gate 1 자료요청 목록에 붙인다.
2. 부지권원·도시계획·환경 스크리닝을 먼저 닫은 뒤 공간·구조·MEP 대안을 만든다.
3. `permitPath`의 법정 선행관계를 일정표에 반영한다. 법정 처리기간은 최소값이 아니라 **완비 서류 접수 후의 규정상 기간**으로 취급한다.
4. `requirements`에서 설계용역, 기술검사, 보험, 시공계약, 준공·개장 조건을 뽑아 예산·조달·RD 분담표에 연결한다.
5. 기준일 이후에는 개정·폐지 여부, 관할기관 명칭, 수수료·제출방식, 현지 실행관행을 다시 확인한다.
