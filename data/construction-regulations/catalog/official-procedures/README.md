# 국가별 건축 법정절차 오버레이

`<country-slug>.json` 한 파일에 해당 국가의 세 제도축을 기록한다.

- `site-urban`: 도시계획·부지규제
- `permit-environment`: 건축허가·환경심사
- `control-completion`: 기술검사·보험·준공제도

기본 형식:

```json
{
  "schemaVersion": "0.1",
  "slug": "country-slug",
  "authorities": [],
  "instruments": [],
  "systems": {
    "site-urban": {"officialProcedure": {"publicationScope": "national"}},
    "permit-environment": {"officialProcedure": {"publicationScope": "national"}},
    "control-completion": {"officialProcedure": {"publicationScope": "subnational-example"}}
  }
}
```

`authorities`와 `instruments`는 `id` 기준으로 기본 대장을 보완·교체한다. 각 system은
기본 system의 얕은 패치이며, 보통 `verificationScope`와 `officialProcedure`를 넣는다.

## 공개 절차 작성 기준

- 법령·관할기관·정부 서비스 안내 등 1차 공식자료만 근거로 사용한다.
- 모든 축에 `publicationScope`를 명시한다. 전국 공통 절차만 `national`, 특정 주·도시·지방 사례나 혼합 절차는 `subnational-example`로 분류한다.
- `subnational-example` 축은 조사 대장에만 남고 공개 데이터·목록·페이지·구조도·출처에서 제외된다. 전국 공통 근거로 절차 전체를 다시 작성하기 전에는 공개하지 않는다.
- 공개 workflow에는 신청·접수·완비심사·전문심사·보완·공식결정·검사·준공 등 실제 법정절차만 둔다.
- ODA 조사, 현장확인, 보고서 작성, 사업통제 노드는 넣지 않는다.
- 각 step은 `refs`로 근거 instrument와 조문·공식 절차 항목을 직접 연결한다.
- 조문 직접 대조는 `statutory`, 기관 절차 안내는 `official-guidance`로 표시한다.
- 수수료·기간·제출부수는 공식자료에서 확인된 경우에만 적고, 불명확하면 추정하지 않는다.
- 각 축은 최소 5개 절차 단계, 1개 공식결정 Gate, `success/rework/reject` 3개 결과 분기를 둔다.
- 보완 회귀선은 실제 보완요구 근거가 있을 때만 `loop`로 표시한다.

생성·검증:

```bash
python3 tools/build_construction_baselines.py
python3 tools/validate_construction_regulations.py
python3 tools/check_construction_procedure_coverage.py
python3 tools/build_site.py
npm run build:construction-boards
python3 tools/check_construction_site.py
```
