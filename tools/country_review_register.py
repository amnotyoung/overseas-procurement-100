"""협력국별 원본 확보 및 조달 단계 근거 대조 작업을 Markdown으로 생성한다."""
from collections import Counter
import json
from datetime import date

from procurement_evidence import web_url
from procurement_summary import MANIFEST, ROOT

AXES = {"bidding": "입찰", "governance": "거버넌스", "pipeline": "사업형성"}
CONSTRUCTION = ROOT / "data" / "construction-regulations"


def cell(value):
    return " ".join(str(value).split()).replace("|", r"\|")


def model_link(model, label):
    return f"[{cell(label)}](../data/institutions/{model['slug']}.json)"


def source_requests(country, models):
    requests = []
    seen = set()
    document_scopes = set()
    for request in country.get("sourceRequests", []):
        key = request["id"]
        axes = request["axes"]
        if not key or key in seen or not axes or len(set(axes)) != len(axes) or set(axes) - models.keys():
            raise ValueError(f"{country['slug']}: 원본 요청 ID 또는 대상 제도 오류")
        seen.add(key)
        if request["status"] not in ("pending", "verified"):
            raise ValueError(f"{key}: 원본 요청 상태 오류")
        date.fromisoformat(request["checkedOn"])
        if not all(request.get(k) for k in ("document", "scope", "finding")) or not web_url(request.get("publisherUrl")):
            raise ValueError(f"{key}: 원본 서지·확인 범위·발행처 정보 누락")
        # 세 모델의 작업이나 상태 변경을 별도 요청으로 다시 등록하지 않도록 한다.
        document_scope = tuple(" ".join(request[k].split()).casefold() for k in ("document", "scope"))
        if document_scope in document_scopes:
            raise ValueError(f"{country['slug']}: 동일 문서·확인 범위의 원본 요청 중복")
        document_scopes.add(document_scope)
        if request["status"] == "verified":
            if not web_url(request.get("verifiedSourceUrl")) or not request.get("locator"):
                raise ValueError(f"{key}: 확인한 발행기관 원본 및 조항 위치 누락")
        elif not request.get("nextStep"):
            raise ValueError(f"{key}: 원본 대기 건의 다음 작업 누락")
        requests.append(request)
    return requests


def build_country_review_register(items):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    registry = {}
    for item in items:
        iso = item["country"]["iso3"]
        if iso != "KOR":
            models = registry.setdefault(iso, {})
            if item["axis"] in models:
                raise ValueError(f"{iso}: 중복 제도축 {item['axis']}")
            models[item["axis"]] = item

    countries = sorted((c for c in manifest["countries"] if c["iso3"] != "KOR"), key=lambda c: c["name"])
    if sorted(c["iso3"] for c in countries) != sorted(registry):
        raise ValueError("국가 매니페스트와 협력국 모델 집합 불일치")

    overview = []
    pending_requests = []
    history = []
    sections = []
    totals = Counter()
    total_waiting = 0
    for country in countries:
        iso, name, slug = country["iso3"], country["name"], country["slug"]
        models = registry[iso]
        if set(models) != set(AXES):
            raise ValueError(f"{iso}: 조달 3축 누락")
        construction = json.loads((CONSTRUCTION / f"{slug}.json").read_text(encoding="utf-8"))
        if construction["country"]["iso3"] != iso:
            raise ValueError(f"{iso}: 건축 국가 불일치")
        requests = source_requests(country, models)
        wait_count = 0
        for r in requests:
            scope = ", ".join(model_link(models[k], AXES[k]) for k in r["axes"])
            doc = f"[{cell(r['document'])}](<{r['publisherUrl']}>)"
            title = f"**{name}** · {doc} · {cell(r['scope'])}"
            if r["status"] == "pending":
                wait_count += 1
                pending_requests.extend([f"- {title} ({r['id']})",
                                         f"  - {r['checkedOn']} 확인 · {cell(r['finding'])}",
                                         f"  - 다음 작업 · {cell(r['nextStep'])}",
                                         f"  - 영향 제도 · {scope}", ""])
            else:
                history.append(f"- {title} ({r['id']}) · {r['checkedOn']} · [{cell(r['locator'])}](<{r['verifiedSourceUrl']}>) · {cell(r['finding'])} · {scope}")

        counts = Counter()
        rows = []
        review_notes = []
        for axis, label in AXES.items():
            model = models[axis]
            if model.get("status") != "full" or not model.get("canvas") or not (model.get("process") or {}).get("nodes"):
                raise ValueError(f"{iso} {label}: 공개 모델에는 캔버스와 절차도가 모두 필요합니다")
            for node in model["process"]["nodes"]:
                if node.get("basisStatus") != "pending":
                    continue
                rows.append(f"| {model_link(model, label)} | {node['id']} | {cell(node['name'])} | {cell(node['actor'])} |")
                if review := node.get("basisReview"):
                    reviewed_on = date.fromisoformat(review["checkedOn"])
                    review_notes.append(f"- {label} {node['id']} · {reviewed_on} · {cell(review['finding'])}")
                counts[axis] += 1
        total_waiting += wait_count
        totals.update(counts)
        country_label = f"[{name}](#pending-{slug})" if rows else name
        cv = construction["verification"]
        model_dates = " / ".join(model_link(models[k], models[k]["verification"]["verifiedAt"]) for k in AXES)
        overview.append(f"| {country_label} | {wait_count} | {counts['bidding']} | {counts['governance']} | {counts['pipeline']} | {model_dates} | [{cv['status']} · {cv['verifiedAt']}](../data/construction-regulations/{slug}.json) |")
        if rows:
            sections.extend([f'<a id="pending-{slug}"></a>', "", f"### {name} · {len(rows)}단계", "",
                             "| 조달 원천 | 단계 ID | 확인할 절차 | 원천에 기재된 담당 |", "|---|---|---|---|", *rows, ""])
            if review_notes:
                sections.extend(["검수 후 대기 사유", "", *review_notes, ""])

    lines = ["# 협력국 검수 대장", "",
             f"협력국 {len(countries)}개국 · 발행기관 원본 대기 {total_waiting}건 · 조달 근거 미연결 {sum(totals.values())}단계",
             "", f"조달 데이터 스키마 v{manifest['schemaVersion']} · {len(countries)}개국 × {len(AXES)}축 · 전체 {sum(len(models) for models in registry.values())}개 모델에 캔버스와 절차도 적용",
             "", "## 발행기관 원본 대기", "",
             *(pending_requests or ["현재 등록된 원본 대기 건이 없습니다.", ""]),
             "## 국가별 검수 현황", "",
             "국가명을 누르면 근거 미연결 단계가 열린다. 날짜는 원천 모델에 기록된 검증일이며 대장 생성일이나 국가 전체의 재검수일을 뜻하지 않는다. 건축 자료는 기존 국가 등급과 확인일을 표시한다.", "",
             "| 국가 | 원본 대기 | 입찰 | 거버넌스 | 사업형성 | 조달 모델 확인일 (입찰 / 거버넌스 / 사업형성) | 건축 등급 · 확인일 |",
             "|---|---:|---:|---:|---:|---|---|", *overview,
             f"| **합계** | **{total_waiting}** | **{totals['bidding']}** | **{totals['governance']}** | **{totals['pipeline']}** | | |",
             "", "## 근거 미연결 단계", "",
             "각 행의 원천 JSON에서 단계 ID를 찾는다. 담당과 행동을 뒷받침하는 조문 또는 자료집 발췌 위치를 확인해 연결하고 검증을 실행한다. 근거가 아직 없는 단계는 다음 검수에 남는다.", "",
             *sections]
    if history:
        lines.extend(["## 원본 확인 기록", "", *history, ""])
    return "\n".join(lines).rstrip() + "\n"
