# 국가별 건축 법·제도 데이터 계약 v0.1

`data/construction-regulations/{country}.json`은 ODA 건축사업의 조사·설계·인허가·시공·준공·운영 단계에서 확인할 법과 제도를 국가별로 정규화한 단일 진실 원천이다. 원천 스키마와 검증은 기존 조달 3축(`bidding`, `governance`, `pipeline`)과 분리하지만, 공개 사이트에서는 같은 국가의 조달 1~3번 뒤에 `construction` 4번부터로 통합한다.

> 이 데이터는 사업기획과 현지조사를 돕는 검증 대장이다. 법률자문, 관할기관의 유권해석, 개별 사업의 인허가를 대신하지 않는다.

## 1. 설계 원칙

1. **법령 목록이 아니라 의사결정 자료로 만든다.** 모든 의무를 사업 생애주기와 Gate 질문에 연결한다.
2. **법적 효력·공식 안내의 운영상태·적용 관할을 섞지 않는다.** 법령의 `in_force`, 공식 서비스의 `current_official`, 폐지·개정예고·검증 예외와 국가·지방 적용범위를 구분한다.
3. **원문 확인 깊이를 드러낸다.** 링크만 연결한 근거와 조문까지 대조한 근거를 구분한다.
4. **국가 공통 규칙과 부지 특례를 분리한다.** 도시계획구역, 특구, 문화재·연안·재해구역 등은 `siteOverlays`에 둔다.
5. **미확정은 0이나 ‘해당 없음’으로 바꾸지 않는다.** `openQuestions`에 필요한 증빙, 확인기관, 보고서 영향을 남긴다.
6. **공식 서비스 페이지보다 최신 법령을 우선한다.** 안내 페이지가 개정 법령을 반영하지 않았으면 그 충돌을 명시한다.
7. **특정 법권의 용어를 국가 공통 개념으로 일반화하지 않는다.** PUD·ERP처럼 일부 국가에서만 쓰는 명칭은 해당 국가 원문과 상세판에만 두고, 공통 계약과 화면에서는 ‘필지별 개발규제’, ‘시설·용도·위험 분류’처럼 기능 중심의 중립 용어를 사용한다.

## 2. 파일 배치

| 경로 | 용도 | 생성 |
|---|---|---|
| `data/construction-regulations/manifest.json` | 스키마·대상국·진행 상태 | 수동 |
| `data/construction-regulations/{country}.json` | 국가별 원천 데이터 | 수동 |
| `data/construction-regulations/catalog/baselines.json` | 전체 국가 기본판의 공식 출처·기관·3축 판단 | 수동 |
| `tools/build_construction_baselines.py` | 기본판을 표준 국가 JSON으로 확장 | 수동 |
| `docs/construction-regulations-data-contract.md` | 이 데이터 계약 | 수동 |
| `docs/construction-regulations/{country}.md` | 전문가용 국가 브리프 | `build_construction_regulations.py` |
| `tools/validate_construction_regulations.py` | 구조·참조·근거 검증 | 수동 |
| `tools/build_construction_regulations.py` | Markdown 생성 | 수동 |
| `tools/build_construction_boards.mjs` | `processBoard`를 korea100studio SVG로 렌더 | 수동 |
| `tools/check_construction_site.py` | 통합 model·클릭 구조도·이전 URL·감사용 SVG 확인 | 수동 |

생성 문서는 직접 고치지 않는다. 원천 JSON을 수정한 뒤 다시 빌드한다.

## 3. 검증 상태

### 3.1 법령·공식자료 상태 `instruments[].status`

| 값 | 의미 |
|---|---|
| `in_force` | 법령·코드의 기준일 현재 법적 효력을 공식 근거로 확인 |
| `current_official` | 법령이 아닌 정부 서비스·업무안내가 기준일 현재 운영·게시 중임을 확인 |
| `superseded` | 폐지·대체 근거를 확인 |
| `pending` | 의회·정부에서 심의 중이나 아직 현행이 아님 |
| `continuity_unverified` | 사이트가 개정·폐지 추적을 아직 끝내지 못한 예외. 사용자에게 일괄 재확인을 요구하는 뜻이 아님 |

`statusCheckedOn`과 `statusBasis`는 현행·운영 판정일과 그 판단근거를 기록한다. `scope`와 `scopeLabel`은 `national`, `subnational`, `local`, `adoption-dependent`, `multi-level` 중 실제 관할·채택범위를 표시한다. 관할 한정이나 사업별 적용조건을 `continuity_unverified`로 바꾸지 않는다.

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

`processBoard`는 확인된 국가·지방 관할의 실제 공식 건축 인허가·검사 절차를 행위주체와 순서로 구조화하고, `publicModels`는 그 절차를 공개 사이트의 독립 제도축으로 나누는 표시 계약이다. 모든 협력국은 조달 3종과 균형을 맞춰 `도시계획·부지규제`, `건축허가·환경심사`, `기술검사·보험·준공제도` 3종을 4~6번으로 공개한다. 법령·의무·질문을 복제하지 않고 전체 `processBoard`의 노드와 공통 대장을 참조한다. 현지자료 요청·사업별 적용판단·설계통합 같은 ODA 사업팀의 준비·확인업무는 절차 노드로 섞지 않고 `openQuestions`, `fieldworkChecklist`, `requirements[].evidenceToObtain`과 공개 화면의 **ODA 사업 적용 확인사항**에 별도로 둔다. 국가별 공식 결정은 `permitPath`에 확인된 범위만 기록한다.

국가 기본판(`generatedFrom` 존재)은 공식 법령·정부 서비스의 진입경로와 핵심 의사결정만 확인한 `law-linked` 또는 `source-linked` 자료다. 세네갈처럼 조문을 대조한 상세판과 같은 깊이로 오인하지 않도록 검증상태와 한계를 화면에 그대로 노출한다. 기본판의 생성 JSON은 직접 고치지 않고 catalog를 수정한다.

catalog의 각 제도축은 공식 원문으로 신청·심사·협의·결정 순서를 확인했을 때만 `officialProcedure`를 갖는다. `officialProcedure` 안에는 절차의 적용 범위(`scope`), 단계(`steps`), 연결(`edges`), 공식 결정(`permitGate`), 선택적 보완회귀(`loop`)와 결과분기(`decisionBranches`)를 근거 범위만큼 기록한다. `officialProcedure`가 없으면 생성기는 공통 절차를 추정하지 않고 `procedureStatus: "detail-unverified"`인 **공식 절차 상세 미확인** 1개 증거 진입 노드만 만든다. 별도 환경결정·착공통지·NOC·점유승인 같이 확인되지 않은 절차를 노드 수를 맞추기 위해 만들지 않는다.

## 5. 핵심 객체

### 5.1 법령·공식자료 `Instrument`

```ts
{
  id: string;                       // 국가 내 유일
  title: string;                    // 원문 정식명
  titleKo: string;
  kind: "act" | "code" | "decree" | "draft" | "local-regulation" |
        "official-guidance" | "order" | "ordinance" | "plan" |
        "regulation" | "standard";
  status: "in_force" | "current_official" | "superseded" | "pending" |
          "continuity_unverified";
  statusCheckedOn?: "YYYY-MM-DD";
  statusBasis?: string;             // 현행·운영 판단에 쓴 공식 대장·통합본·서비스
  scope?: "national" | "subnational" | "local" | "adoption-dependent" |
          "multi-level";
  scopeLabel?: string;              // 예: Islamabad Capital Territory (ICT)
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

폐지된 법령도 지우지 않는다. 공식 포털의 오래된 안내를 걸러내고 과거 보고서의 인용을 진단하기 위한 대조표로 남긴다. Gate와 절차 노드에는 관할·근거 깊이만 간결하게 표시하고, 현행·운영 상태와 확인일은 원문 검증대장에서 자료별로 한 번 표시한다.

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
- `conditional`: 층수·연면적·시설·용도·위험 분류·발주주체 등 사업 입력에 따라 적용됨.
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

`processBoard`는 [korea100studio board-v1](https://github.com/amnotyoung/korea100studio)의 `gov` 프로필 입력이다. 법령 목록을 단순 나열하지 않고, 확인된 국가·지방 관할의 신청인·현지전문가·허가기관·환경·소방·검사기관이 수행하는 실제 공식 절차를 행위주체 × 절차구간 × 업무로 구조화한다. 노드의 `kind`와 `basisScope`는 그 단계가 현행 조문에 직접 대응하는지, 공식 안내에 근거하는지, 지역 사례인지를 구분한다. 확인한 절차 범위와 관할은 `procedureScope`에 명시하며, 이를 전국 공통이나 모든 시설에 적용되는 완전한 순서로 확대 해석하지 않는다. ODA 사업팀의 준비·현지확인·설계통합 업무는 이 보드에 혼합하지 않는다.

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
    kind?: "statutory" | "official-guidance" | "local-example" |
           "field-verification" | "project-control";
    basisScope?: "node" | "axis";  // refs가 이 노드의 직접근거인지 제도축 공통근거인지
    note?: string;
    action?: string;                // 카드 상세의 노드별 수행내용
    outputs?: string[];             // 카드 상세의 노드별 산출물
    authorityIds?: string[];
    requirementIds?: string[];
    questionIds?: string[];         // openQuestions 참조
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
  procedureStatus?: "detail-unverified" | "source-linked" |
                    "official-source-linked" | "article-verified";
  procedureScope?: string;          // 관할·시설·절차 범위와 제한
  nodeIds: string[];                // 전체 processBoard.nodes 참조
  requirementIds: string[];         // requirements 참조, 축 간 내용 혼입 방지
  questionIds: string[];            // openQuestions 참조
  conclusionIds: string[];          // reportReadyConclusions 참조
  siteOverlayIds: string[];         // siteOverlays 참조, 없으면 빈 배열
  fieldworkChecklistIds: string[];  // fieldworkChecklist 참조
  edges: ConstructionProcessBoard["edges"];
  decisionBranches?: Array<{
    state: "success" | "rework" | "reject";
    label: string;
    action: string;
  }>;
}
```

- 각 공개 제도축은 선택한 노드만으로 독립적으로 연결된 클릭형 구조도를 만든다.
- 공개 제도축의 edge는 통합 `processBoard.edges`에 같은 source·target·type·label로 존재하는 경로만 투영한다.
- `officialProcedure`가 있는 공개 제도축의 노드·레인·절차구간·Gate 수는 공식 근거에서 확인한 범위를 따른다. 일정한 노드 수나 레인 수를 맞추기 위해 절차를 추가하지 않는다.
- `officialProcedure`가 없는 공개 제도축은 `detail-unverified` 1노드와 빈 `edges`를 허용한다. 이 노드는 관할기관의 현행 절차도·신청서·체크리스트를 추가 확인해야 한다는 상태를 뜻하며, 실제 절차로 해석하지 않는다.
- 모든 건축 국가 파일은 정확히 3개 공개 제도축과 연속 우선순위 4·5·6을 가져야 한다.
- 한 국가의 공개 제도축 전체를 합치면 원천 노드, 의무, Gate, 질문, 결론, 부지 특례와 현지조사 체크리스트가 빠짐없이 포괄돼야 한다. `requirementIds`는 각 의무를 한 축에만 배정해 선택 노드의 다른 주제가 섞이지 않게 한다.
- 여러 제도에 공통인 법령·Gate·결론은 중복 표시할 수 있지만 원천 객체를 복제하지 않는다.
- 원천 `processBoard.nodes[].id`는 국가 파일 안의 참조 무결성을 위해 유지한다. 공개 화면은 각 제도축의 `nodeIds` 순서를 기준으로 노드 번호를 `B01`부터, 절차구간을 `G1`부터 다시 매긴다. 카드와 상세 패널은 이 화면 로컬 번호를 표시하되, 연결·근거 추적은 원천 ID를 사용한다.

- `permitPath`는 관할기관의 계획·환경·건축·준공·점유 등 **외부 법정·공식 결정 Gate**만 담는 일정·산출물 대장이다. 신청·완비성·기술심사 등의 업무 노드와 관할기관의 최종 공식 결정 Gate를 분리하며, Gate 수는 국가·제도축별로 다를 수 있다. 자료수집, 현장조사, 설계통합, ODA 내부 Go/No-Go 같은 운영업무는 `permitPath`나 절차 노드에 복제하지 않는다. 국가별 공식 선후관계를 확인하기 전에는 `dependsOn`을 비워 둔다.
- 공개 화면의 **업무구조도/절차 단계**는 선택한 `processBoard`/`publicModels` 노드를 빠짐없이 보여주고, **공식 결정 Gate**는 해당 `permitPath`의 결정기관·적용조건·산출물·선행조건을 별도로 보여준다. 화면 Gate 번호는 선택축 안의 `Gate i/N` 로컬 번호이며, 원천 `permitPath.order`과 `dependsOn`이 확인된 선후관계를 보존한다. 절차 단계 수와 Gate 수는 같을 필요가 없다.
- `decisionBranches`는 관할 절차에서 근거를 확인한 경우에만 `success`·`rework`·`reject` 세 상태와 후속 조치를 표시한다. 보완회귀도 조건·돌아갈 단계·재접수 경로를 확인한 `loop` edge가 있을 때만 표시하며, 공식 근거가 없는 이의신청·재신청·불복절차나 기한을 추정하지 않는다.
- 공식 Gate가 있는 경우 각 `permitPath.order`는 최소 한 개의 보드 노드 `gateOrders`에 연결한다. `detail-unverified` 제도축은 Gate 없이 1노드만 가질 수 있다.
- 모든 노드는 근거 `refs`를 갖고 기존 법령 ID·요구사항·기관으로 역추적할 수 있어야 한다. 단계별 조문 대응을 검증하지 않은 국가 기본판은 `basisScope: "axis"`로 표시하고 해당 제도축의 전체 관련 근거를 연결한다. 이를 개별 노드의 직접 조문 근거로 표현하지 않는다.
- `evidenceToObtain`은 법정 순서가 아니라 ODA 사업에 적용할 때 확인할 증빙이다. 노드 수를 맞추려고 이를 가상의 법정 단계로 쪼개지 않는다. `kind`로 법정절차·공식경로·지역사례·현지확인을 구분하며, 근거가 없는 착공통지·NOC·점유승인·보험 의무는 절차 노드로 추정하지 않고 `fieldworkChecklist`와 `openQuestions`의 적용 여부 확인으로 표현한다. 특히 `basisScope: "axis"`이거나 연결 근거의 현행성이 `continuity_unverified`인 노드는 `statutory`로 표시하지 않는다. `statutory`는 현행 조문과 해당 노드의 직접 대응을 확인한 경우에만 쓴다.
- `action`·`outputs`가 있으면 공개 카드 상세는 이를 우선 사용한다. `requirementIds`는 상태·적용조건·근거 추적을 유지하되 같은 축의 긴 요구사항과 증빙목록을 모든 카드에 반복하지 않는다.
- 공개 화면은 `build_site.py`가 `processBoard` 또는 `publicModels` 투영을 기존 model 템플릿의 HTML 버튼·동적 연결선·상세 패널로 변환한다. 국가별 조달 3축 뒤에 `priority: 4`부터 배치하며, 기존 `/construction/{country}/`와 단일 건축 model 주소는 첫 건축 model로 이동한다.
- 카드의 `담당`은 lane의 책임주체이고 `authorityIds`는 `협의·관할기관`으로 따로 표시한다. 카드의 노드별 근거는 `processBoard.refs`를 우선하고, refs가 없는 구 계약에서만 연결된 `requirements[].legalBasis`를 대체 근거로 쓴다. 축 전체 근거는 캔버스 법적 근거에 별도로 유지한다.
- 법령·자료의 원래 `kind`, `status`, `verificationLevel`, `scope`, `note`를 보존한다. `current_official`은 법적 근거가 아니라 운영 중 공식자료로 분리하고, `pending`·`superseded`·`continuity_unverified`는 사이트 검증 예외로 원문 대장에서 구체적 사유와 함께 표시한다.
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
- `officialProcedure`가 있는 공개 모델의 non-loop 흐름은 정의된 진입 노드에서 절차 노드에 도달해야 하고, 연결된 모든 `permitPath` 순번을 포괄해야 한다. `detail-unverified` 1노드 모델은 빈 edge와 Gate 0개를 허용한다.
- 보완회귀는 선택 요소이며, 존재하는 경우 비어 있지 않은 조건 라벨을 갖고 `nodeIds`상 앞선 신청·심사 단계로 돌아가야 한다. `decisionBranches`를 제공하면 `success`·`rework`·`reject` 세 상태를 모두 정의한다.
- 새 구조도는 korea100studio 감사에서 노드 관통 0건을 충족해야 한다. 실제 법정 보완회귀 때문에 교차·경로길이 같은 soft 구성예산을 넘으면 빌드 결과에 경고로 남기고, 공개 HTML 보드에서 카드·라벨 충돌을 별도로 확인한다.

## 7. ODA 건축보고서 적용 순서

1. `pilotContext.unknown`과 `openQuestions[blocking=true]`를 Gate 1 자료요청 목록에 붙인다.
2. 부지권원·도시계획·환경 스크리닝을 먼저 닫은 뒤 공간·구조·MEP 대안을 만든다.
3. `permitPath`의 법정 선행관계를 일정표에 반영한다. 법정 처리기간은 최소값이 아니라 **완비 서류 접수 후의 규정상 기간**으로 취급한다.
4. `requirements`에서 설계용역, 기술검사, 보험, 시공계약, 준공·개장 조건을 뽑아 예산·조달·RD 분담표에 연결한다.
5. 기준일 이후에는 개정·폐지 여부, 관할기관 명칭, 수수료·제출방식, 현지 실행관행을 다시 확인한다.
