#!/usr/bin/env python3
"""KOICA 2026 지역별 자료집의 모든 국가를 3축 제도 JSON으로 변환한다.

이 스크립트가 만드는 레코드는 자료집 기재사항을 구조화한 1차 다이어그램이다.
각국 법령의 현행성·조문은 확인하지 않으므로 verification.status는
``source-document``로 고정한다. 이미 수작업 검증된 JSON은 덮어쓰지 않는다.
"""
from __future__ import annotations

import json
import re
import subprocess
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = next(p for p in ROOT.iterdir() if p.is_dir() and "자료집" in unicodedata.normalize("NFC", p.name))
OUT = ROOT / "data" / "institutions"
EXTRACTED = ROOT / "sources" / "koica-2026"
TODAY = date.today().isoformat()
KOICA_URL = "https://www.koica.go.kr/"


@dataclass(frozen=True)
class Country:
    slug: str
    name: str
    name_en: str
    iso3: str
    start: int
    end: int


REGIONS: dict[str, dict] = {
    "asia-pacific": {
        "label": "아시아·태평양",
        "file_key": "아시아 및 태평양",
        "source_id": "koica-2026-asia-pacific",
        "document": "KOICA 2026 국가별 개발협력사업 참여전략 자료집(아시아 및 태평양)",
        "countries": [
            Country("nepal", "네팔", "Nepal", "NPL", 5, 18),
            Country("timor-leste", "동티모르", "Timor-Leste", "TLS", 21, 29),
            Country("laos", "라오스", "Lao People's Democratic Republic", "LAO", 31, 45),
            Country("bangladesh", "방글라데시", "Bangladesh", "BGD", 47, 59),
            Country("vietnam", "베트남", "Viet Nam", "VNM", 61, 79),
            Country("sri-lanka", "스리랑카", "Sri Lanka", "LKA", 81, 91),
            Country("indonesia", "인도네시아", "Indonesia", "IDN", 93, 107),
            Country("cambodia", "캄보디아", "Cambodia", "KHM", 109, 127),
            Country("thailand", "태국", "Thailand", "THA", 129, 147),
            Country("pakistan", "파키스탄", "Pakistan", "PAK", 149, 163),
            Country("fiji", "피지", "Fiji", "FJI", 165, 175),
            Country("philippines", "필리핀", "Philippines", "PHL", 177, 191),
        ],
    },
    "africa": {
        "label": "아프리카",
        "file_key": "아프리카",
        "source_id": "koica-2026-africa",
        "document": "KOICA 2026 국가별 개발협력사업 참여전략 자료집(아프리카)",
        "countries": [
            Country("dr-congo", "DR콩고", "Democratic Republic of the Congo", "COD", 5, 15),
            Country("ghana", "가나", "Ghana", "GHA", 17, 29),
            Country("nigeria", "나이지리아", "Nigeria", "NGA", 31, 41),
            Country("rwanda", "르완다", "Rwanda", "RWA", 43, 57),
            Country("morocco", "모로코", "Morocco", "MAR", 59, 71),
            Country("mozambique", "모잠비크", "Mozambique", "MOZ", 73, 83),
            Country("senegal", "세네갈", "Senegal", "SEN", 85, 93),
            Country("ethiopia", "에티오피아", "Ethiopia", "ETH", 95, 115),
            Country("uganda", "우간다", "Uganda", "UGA", 117, 131),
            Country("egypt", "이집트", "Egypt", "EGY", 133, 147),
            Country("cameroon", "카메룬", "Cameroon", "CMR", 149, 159),
            Country("kenya", "케냐", "Kenya", "KEN", 161, 173),
            Country("cote-divoire", "코트디부아르", "Côte d'Ivoire", "CIV", 175, 185),
            Country("tanzania", "탄자니아", "Tanzania", "TZA", 187, 202),
            Country("tunisia", "튀니지", "Tunisia", "TUN", 205, 213),
        ],
    },
    "latin-america": {
        "label": "중남미",
        "file_key": "중남미",
        "source_id": "koica-2026-latin-america",
        "document": "KOICA 2026 국가별 개발협력사업 참여전략 자료집(중남미)",
        "countries": [
            Country("guatemala", "과테말라", "Guatemala", "GTM", 5, 17),
            Country("dominican-republic", "도미니카공화국", "Dominican Republic", "DOM", 19, 39),
            Country("bolivia", "볼리비아", "Bolivia", "BOL", 41, 55),
            Country("ecuador", "에콰도르", "Ecuador", "ECU", 57, 69),
            Country("el-salvador", "엘살바도르", "El Salvador", "SLV", 71, 79),
            Country("colombia", "콜롬비아", "Colombia", "COL", 81, 97),
            Country("paraguay", "파라과이", "Paraguay", "PRY", 99, 113),
            Country("peru", "페루", "Peru", "PER", 115, 127),
        ],
    },
    "middle-east-cis": {
        "label": "중동·CIS",
        "file_key": "중동,CIS",
        "source_id": "koica-2026-middle-east-cis",
        "document": "KOICA 2026 국가별 개발협력사업 참여전략 자료집(중동·CIS)",
        "countries": [
            Country("mongolia", "몽골", "Mongolia", "MNG", 5, 23),
            Country("azerbaijan", "아제르바이잔", "Azerbaijan", "AZE", 25, 39),
            Country("jordan", "요르단", "Jordan", "JOR", 41, 55),
            Country("uzbekistan", "우즈베키스탄", "Uzbekistan", "UZB", 57, 71),
            Country("ukraine", "우크라이나", "Ukraine", "UKR", 73, 83),
            Country("kyrgyzstan", "키르기스스탄", "Kyrgyzstan", "KGZ", 85, 97),
            Country("tajikistan", "타지키스탄", "Tajikistan", "TJK", 99, 117),
            Country("palestine", "팔레스타인", "Palestine", "PSE", 119, 127),
        ],
    },
}


AXES = {
    "bidding": ("bidding-system", "공공조달 입찰제도", "경쟁조달형"),
    "governance": ("procurement-governance", "조달 거버넌스·감독체계", "감독·집행형"),
    "pipeline": ("oda-project-pipeline", "ODA 사업 발굴·형성 절차", "사업형성형"),
}


def pdf_for(file_key: str) -> Path:
    for path in PDF_DIR.glob("*.pdf"):
        if file_key in unicodedata.normalize("NFC", path.name):
            return path
    raise FileNotFoundError(file_key)


def extract(pdf: Path, country: Country, region_key: str) -> str:
    target_dir = EXTRACTED / region_key
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{country.slug}.txt"
    run = subprocess.run(
        ["pdftotext", "-f", str(country.start), "-l", str(country.end), "-layout", str(pdf), "-"],
        check=True, capture_output=True, text=True,
    )
    text = clean(run.stdout)
    target.write_text(text + "\n", encoding="utf-8")
    return text


def clean(text: str) -> str:
    text = text.replace("\f", "\n")
    text = re.sub(r"2026 국가별 개발협력사업 참여전략 자료집[^\n]*", "", text)
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.M)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def sentences(text: str) -> list[str]:
    out: list[str] = []
    for raw in re.split(r"\n+|(?<=[다함됨임음요])\.\s+|(?<=[.!?])\s+(?=[A-Z가-힣])", text):
        line = re.sub(r"^[\s\-∙▫◦※*·l]+", "", raw).strip()
        line = re.sub(r"\s+", " ", line)
        if 24 <= len(line) <= 360 and not re.fullmatch(r"[ⅠⅡⅢⅣⅤ\d.\s]+", line):
            out.append(line)
    return out


def pick(text: str, keywords: tuple[str, ...], fallback: str, *, limit: int = 2) -> str:
    found = [s for s in sentences(text) if any(k.lower() in s.lower() for k in keywords)]
    if not found:
        return fallback
    value = " ".join(found[:limit])
    return value[:700].rstrip(" ,")


def split_sections(text: str) -> tuple[str, str]:
    procurement_markers = [
        text.find("협력국 개발협력 조달시장 참여방안"),
        text.find("협력국 입찰 제도"),
        text.find("협력국 조달관련 조직체계"),
    ]
    positions = [p for p in procurement_markers if p >= 0]
    cut = min(positions) if positions else max(1, len(text) // 2)
    return text[:cut], text[cut:]


def legal_basis(text: str, axis: str, document: str) -> list[dict]:
    candidates: list[str] = []
    # 명칭 경계가 명확한 괄호·인용부호 안의 법령만 채택한다. 일반 서술에
    # '법'이라는 글자가 포함됐다는 이유로 법령명으로 오인하지 않는다.
    patterns = [
        r"「([^」]{4,120}(?:법|법률|법령|규정|조례|지침)[^」]{0,30})」",
        r"((?:Public |Government |National |State |Foreign |External )"
        r"[A-Z][A-Za-z0-9 ,.'’()/-]{2,100}?(?:Law|Act|Code|Decree|Regulations?|Directive)"
        r"(?:\s*(?:No\.?|Number)?\s*[\w./-]+)?)",
        r"([가-힣A-Za-z· ]{2,55}(?:법률|조달법|계약법|원조정책|조달규정|시행규정))"
        r"(?:\s*\([^)\n]{3,100}\))?",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            name = re.sub(r"\s+", " ", match.group(1)).strip(" -:.,")
            if 4 <= len(name) <= 140 and name not in candidates:
                candidates.append(name)
            if len(candidates) == 3:
                break
        if len(candidates) == 3:
            break
    result = [{"law": document, "lawKo": "KOICA 참여전략 자료집", "kind": "donor-rule"}]
    kind = "act" if axis != "pipeline" else "directive"
    result.extend({"law": x, "kind": kind} for x in candidates)
    return result


def urls(text: str) -> list[str]:
    found = re.findall(r"https?://[^\s<>()]+", text)
    return list(dict.fromkeys(x.rstrip(".,") for x in found))[:4]


def authority_names(text: str, axis: str, country: Country) -> list[dict]:
    keys = ("조달", "재무", "기획", "원조", "Ministry", "Authority", "위원회", "Agency")
    names: list[str] = []
    org_patterns = [
        r"정부 조직도\s*:\s*([^\n]{3,100})",
        r"([가-힣· ]{2,35}\s*\([A-Z][A-Za-z0-9& ,.'’/-]{2,85}\))",
    ]
    for pattern in org_patterns:
        for match in re.finditer(pattern, text):
            short = re.sub(r"\s+", " ", match.group(1)).strip(" -:,")
            if any(k.lower() in short.lower() for k in keys) and short not in names:
                names.append(short)
            if len(names) == 3:
                break
        if len(names) == 3:
            break
    if not names:
        fallback = "수원총괄기관" if axis == "pipeline" else "조달 총괄기관 및 발주기관"
        names = [f"{country.name} {fallback}"]
    role = {
        "bidding": "자료집에 기재된 입찰 공고·평가·낙찰·계약 절차를 수행한다.",
        "governance": "자료집에 기재된 조달 정책·공고·감독 또는 집행 기능을 담당한다.",
        "pipeline": "자료집에 기재된 사업수요 취합·우선순위 검토·공식 요청 절차를 담당한다.",
    }[axis]
    return [{"name": n, "role": role} for n in names]


def canvas(axis: str, country: Country, pipeline_text: str, procurement_text: str, document: str) -> dict:
    scope = pipeline_text if axis == "pipeline" else procurement_text
    proc_keys = {
        "bidding": ("공고", "제출", "개찰", "평가", "낙찰", "계약", "입찰"),
        "governance": ("총괄", "조직", "감독", "공고", "전자조달", "이의", "분쟁"),
        "pipeline": ("발굴", "PCP", "제출", "검토", "예비조사", "기획조사", "협약", "RD", "MOU"),
    }[axis]
    purpose = {
        "bidding": f"{country.name} 자료집에 기재된 공개·제한·지명·직접구매 등 조달방식과 입찰 참여요건을 한 흐름으로 정리한다.",
        "governance": f"{country.name}의 조달 총괄기관, 발주기관, 전자조달·공고 채널, 감독·분쟁 기능의 역할 관계를 정리한다.",
        "pipeline": f"{country.name} 수원부처의 사업수요가 수원총괄기관 검토, KOICA 조사·심사, 정부 간 공식화로 이어지는 흐름을 정리한다.",
    }[axis]
    applicable_detail = pick(scope, ("적용 대상", "외국인의 입찰", "국제입찰", "금액 이상", "금액 이하"), "", limit=1)
    applicable = (
        f"자료집에 기재된 {country.name}의 공공조달 또는 개발협력 사업을 대상으로 한다."
        + (f" 자료집 발췌: {applicable_detail}" if applicable_detail else "")
    )
    selected = [s for s in sentences(scope) if any(k.lower() in s.lower() for k in proc_keys)]
    procedure = selected[:8]
    generic = {
        "bidding": ["조달계획 및 방식 결정", "입찰공고 게시", "입찰서류 교부", "입찰서 제출", "개찰", "평가 및 낙찰", "계약 체결"],
        "governance": ["조달계획 수립", "공고·전자조달 등록", "입찰 집행", "감독·모니터링", "이의·분쟁 처리", "계약관리"],
        "pipeline": ["사업수요 발굴", "PCP 작성", "수원기관 검토", "수원총괄기관 공식 제출", "KOICA 예비조사", "기획조사·사업 확정", "RD·MOU 등 공식화"],
    }[axis]
    for item in generic:
        if len(procedure) >= 7:
            break
        procedure.append(item)
    docs = {
        "bidding": ["입찰공고", "입찰서 및 자격증빙", "가격·기술 제안", "낙찰통지서", "계약서"],
        "governance": ["조달계획", "입찰공고", "평가보고서", "이의·분쟁 관련 문서", "계약관리 기록"],
        "pipeline": ["사업요청서 또는 PCP", "검토·우선순위 문서", "예비조사 보고서", "사업기획 문서", "RD 또는 MOU"],
    }[axis]
    bottleneck = [
        "자료집 기반 1차 구조화이므로 실제 참여 전 발주기관 공고와 현행 규정을 다시 확인해야 한다.",
        "금액·기한·제출서류와 외국기업 참여요건은 개별 공고에서 재확인해야 한다.",
    ]
    authorities = authority_names(scope, axis, country)
    return {
        "purpose": purpose,
        "stakeholders": f"{country.name} 정부, {', '.join(a['name'] for a in authorities)}, 발주·수원부처, 국내외 입찰자, KOICA",
        "legalBasis": legal_basis(scope, axis, document),
        "authorities": authorities,
        "procedure": [f"{i}. {x}" for i, x in enumerate(procedure[:8], 1)],
        "applicability": applicable,
        "submittedDocuments": [{"actor": "참여기관·입찰자", "documents": docs}],
        "bottlenecks": bottleneck,
        "entryBarriers": ["외국 기업의 등록·인허가·현지어·현지대리인 요건은 개별 공고와 담당 기관에서 확인해야 한다."],
    }


def process(axis: str, country: Country, scope: str, authorities: list[dict]) -> dict:
    authority = authorities[0]["name"][:60]
    if axis == "pipeline":
        lanes = ["수원부처", "수원총괄기관", "KOICA"]
        stages = ["G1 발굴", "G2 공식요청", "G3 조사·심사", "G4 공식화"]
        spec = [
            ("수요 발굴", "수원부처", stages[0], "task", "current", ("발굴", "수요")),
            ("PCP·요청서 작성", "수원부처", stages[0], "task", "current", ("PCP", "사업제안서", "요청서")),
            ("국가 우선순위 검토", "수원총괄기관", stages[1], "gateway", "risk", ("우선순위", "검토")),
            ("공식 사업요청", "수원총괄기관", stages[1], "notice", "waiting", ("공문", "제출", "요청")),
            ("예비조사·타당성 검토", "KOICA", stages[2], "task", "waiting", ("예비조사", "타당성")),
            ("기획·사업 확정", "KOICA", stages[2], "gateway", "waiting", ("기획조사", "확정", "심사")),
            ("RD·MOU 공식화", "수원총괄기관", stages[3], "notice", "waiting", ("RD", "R/D", "MOU", "협약")),
        ]
    elif axis == "governance":
        lanes = ["발주기관", "조달 총괄·전자조달", "감독·분쟁기관"]
        stages = ["G1 계획", "G2 공고·집행", "G3 감독", "G4 구제·관리"]
        spec = [
            ("조달계획 수립", lanes[0], stages[0], "task", "current", ("조달 계획", "계획")),
            ("조달방식·서류 검토", lanes[1], stages[0], "gateway", "waiting", ("규정", "법")),
            ("공고·전자조달 게시", lanes[1], stages[1], "system", "current", ("공고", "전자조달", "포털")),
            ("입찰 집행·기록", lanes[0], stages[1], "task", "waiting", ("입찰", "개찰")),
            ("절차 감독·감사", lanes[2], stages[2], "task", "risk", ("감독", "감사", "모니터링")),
            ("이의·분쟁 처리", lanes[2], stages[3], "gateway", "risk", ("이의", "분쟁", "불만")),
            ("계약관리·공개", lanes[0], stages[3], "task", "waiting", ("계약", "관리")),
        ]
    else:
        lanes = ["발주기관", "입찰자", "평가·계약기관"]
        stages = ["G1 준비·공고", "G2 제출", "G3 평가", "G4 계약"]
        spec = [
            ("조달계획·방식 결정", lanes[0], stages[0], "gateway", "current", ("방식", "공개입찰", "조달")),
            ("입찰공고·서류 발행", lanes[0], stages[0], "notice", "current", ("공고", "입찰서류")),
            ("자격·제안서 준비", lanes[1], stages[1], "task", "risk", ("자격", "제출 서류")),
            ("입찰서 제출", lanes[1], stages[1], "task", "waiting", ("입찰서", "제출")),
            ("개찰·적격심사", lanes[2], stages[2], "task", "waiting", ("개찰", "적격")),
            ("평가·낙찰", lanes[2], stages[2], "gateway", "waiting", ("평가", "낙찰")),
            ("계약 체결·이행", lanes[0], stages[3], "task", "waiting", ("계약", "이행")),
        ]
    nodes = []
    for i, (name, lane, stage, typ, status, keys) in enumerate(spec, 1):
        action = {
            "bidding": {
                "조달계획·방식 결정": "발주기관이 적용 규정과 사업 규모에 맞는 조달방식을 결정한다.",
                "입찰공고·서류 발행": "발주기관이 지정 채널에 공고하고 입찰조건·평가기준·계약조건을 공개한다.",
                "자격·제안서 준비": "입찰자가 공고별 자격, 등록, 보증, 기술·가격 서류를 준비한다.",
                "입찰서 제출": "입찰자가 공고에 정한 방식과 기한에 맞춰 입찰서를 제출한다.",
                "개찰·적격심사": "담당 기관이 입찰서를 개찰하고 필수요건과 적격 여부를 확인한다.",
                "평가·낙찰": "공고된 평가기준으로 기술·가격을 평가하고 낙찰자를 결정·통지한다.",
                "계약 체결·이행": "낙찰자가 요구 보증·등록을 완료하고 발주기관과 계약을 체결·이행한다.",
            },
            "governance": {
                "조달계획 수립": "발주기관이 예산과 사업수요를 조달계획으로 구체화한다.",
                "조달방식·서류 검토": "조달 총괄 또는 내부 승인기관이 방식과 입찰서류의 규정 적합성을 확인한다.",
                "공고·전자조달 게시": "지정된 전자조달·공고 채널에 입찰정보를 등록·공개한다.",
                "입찰 집행·기록": "발주기관이 제출·개찰·평가·낙찰 과정을 집행하고 기록을 남긴다.",
                "절차 감독·감사": "감독·감사기관이 법규 준수, 투명성, 부정행위 여부를 점검한다.",
                "이의·분쟁 처리": "입찰자의 이의·불만을 정해진 기관과 절차에 따라 심사한다.",
                "계약관리·공개": "발주기관이 계약 이행·변경·검수·지급 기록을 관리한다.",
            },
            "pipeline": {
                "수요 발굴": "수원부처가 국가계획과 분야 우선순위에 맞는 개발협력 수요를 발굴한다.",
                "PCP·요청서 작성": "수원부처가 사업목표·범위·예산·수행체계를 사업요청서로 구체화한다.",
                "국가 우선순위 검토": "수원총괄기관이 국가전략 부합성, 중복, 재정·운영 지속가능성을 검토한다.",
                "공식 사업요청": "수원총괄기관이 우선순위 사업을 공식 문서로 KOICA에 요청한다.",
                "예비조사·타당성 검토": "KOICA와 수원기관이 현지조사와 협의를 통해 사업 타당성을 검토한다.",
                "기획·사업 확정": "조사 결과를 사업계획으로 고도화하고 심사·예산 절차를 거쳐 확정한다.",
                "RD·MOU 공식화": "KOICA와 수원국 관계기관이 RD·MOU 등 합의문으로 역할과 조건을 공식화한다.",
            },
        }[axis][name]
        actor = authority if lane not in ("입찰자", "KOICA", "수원부처", "발주기관") else lane
        nodes.append({
            "id": f"P{i:02d}", "name": name, "lane": lane, "stage": stage,
            "type": typ, "status": status, "actor": actor, "action": action,
            "confidence": 0.65,
        })
    edges = [
        {"id": f"E{i:02d}", "source": f"P{i:02d}", "target": f"P{i+1:02d}", "type": "sequence"}
        for i in range(1, len(nodes))
    ]
    return {
        "lanes": lanes,
        "stages": stages,
        "nodes": nodes,
        "edges": edges,
        "warnings": [
            "자료집 기재사항을 구조화한 1차 다이어그램이며 현행 법령 조문 대조 전이다.",
            "개별 입찰·사업 착수 전 담당 기관에 절차, 서류, 기한을 재확인해야 한다.",
        ],
    }


def institution(axis: str, country: Country, region: dict, pipeline_text: str, procurement_text: str) -> dict:
    suffix, label, inst_type = AXES[axis]
    slug = f"{country.slug}-{suffix}"
    scope = pipeline_text if axis == "pipeline" else procurement_text
    cv = canvas(axis, country, pipeline_text, procurement_text, region["document"])
    related = [f"{country.slug}-{v[0]}" for key, v in AXES.items() if key != axis]
    source_section = {
        "bidding": "Ⅲ. 협력국 개발협력 조달시장 참여방안 - 협력국 입찰 제도",
        "governance": "Ⅲ. 협력국 개발협력 조달시장 참여방안 - 조달관련 조직체계",
        "pipeline": "Ⅱ. 협력국 개발협력 추진 체계 - 수원체계·사업 발굴 절차",
    }[axis]
    return {
        "slug": slug,
        "name": f"{country.name} {label}",
        "oneLiner": f"{country.name} 자료집에 기재된 {label}를 기관·단계·문서 기준으로 구조화한 1차 다이어그램",
        "axis": axis,
        "type": inst_type,
        "priority": {"bidding": 1, "governance": 2, "pipeline": 3}[axis],
        "asOfDate": "2026-01-01",
        "status": "full",
        "country": {
            "name": country.name, "nameEn": country.name_en, "iso3": country.iso3,
            "region": region["label"],
        },
        "canvas": cv,
        "sourceRefs": [{
            "document": region["document"],
            "pages": f"{country.start}-{country.end}",
            "pdfPages": f"{country.start}-{country.end}",
            "section": source_section,
        }],
        "related": related,
        "fieldVerification": [{
            "item": "현행 절차·기관·금액·제출서류",
            "question": "자료집 기재사항이 현재도 유효하며 실제 공고에 동일하게 적용되는가?",
            "status": "pending",
        }],
        "verification": {
            "status": "source-document",
            "verifiedAt": TODAY,
            "method": "KOICA 2026 지역별 참여전략 자료집의 해당 국가 페이지를 텍스트 추출하고, 수원체계·조달조직·입찰제도 섹션을 3축으로 구조화했다.",
            "scope": "자료집 기재사항과 국가별 페이지 범위를 확인했다. 현행 법령 원문·조문 및 개별 발주기관의 실제 적용은 아직 대조하지 않았다.",
            "notes": ["자료집 기반 1차 다이어그램이다. 현행성 검증 전에는 금액·기한·서류를 확정 기준으로 사용하지 않는다."],
            "sources": [{
                "law": region["document"], "kind": "donor-rule", "publisher": "한국국제협력단(KOICA)",
                "officialUrl": KOICA_URL, "retrievedOn": TODAY,
            }],
            "discrepancies": [],
            "unresolved": [{
                "law": "해당 국가 현행 조달·개발협력 법령 및 시행규정",
                "kind": "act",
                "reasonCode": "title-needs-confirmation",
                "reason": "이번 전수 작업은 자료집 전체 국가의 다이어그램 구축을 우선했으며 현행 법령 조문 대조는 수행하지 않았다.",
                "nextStep": "공식 법령 원문을 확보해 기관명·금액·기한·제출서류와 절차를 조문 단위로 대조한다.",
            }],
        },
        "process": process(axis, country, scope, cv["authorities"]),
    }


def update_manifest() -> None:
    path = ROOT / "data" / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    existing = {c["slug"]: c for c in manifest["countries"]}
    ordered = []
    for region in REGIONS.values():
        for country in region["countries"]:
            item = existing.get(country.slug, {
                "slug": country.slug,
                "name": country.name,
                "nameEn": country.name_en,
                "iso3": country.iso3,
            })
            item.update({
                "region": region["label"],
                "sourceDocument": region["source_id"],
                "pdfPages": f"{country.start}-{country.end}",
                "docPages": f"{country.start}-{country.end}",
            })
            item["institutions"] = {
                axis: {
                    "slug": f"{country.slug}-{spec[0]}",
                    "status": "done",
                    **(
                        item.get("institutions", {}).get(axis, {})
                        if item.get("institutions", {}).get(axis, {}).get("verification") != "source-document"
                        else {}
                    ),
                    "verification": item.get("institutions", {}).get(axis, {}).get("verification", "source-document"),
                    "discrepancies": item.get("institutions", {}).get(axis, {}).get("discrepancies", 0),
                }
                for axis, spec in AXES.items()
            }
            ordered.append(item)
    # 자료집 미수록 보강국과 KOICA 발주자 레코드는 기존 순서대로 보존한다.
    ordered.extend(c for c in manifest["countries"] if c["slug"] not in {x["slug"] for x in ordered})
    manifest["countries"] = ordered
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    made = 0
    skipped = 0
    for region_key, region in REGIONS.items():
        pdf = pdf_for(region["file_key"])
        for country in region["countries"]:
            text = extract(pdf, country, region_key)
            pipeline_text, procurement_text = split_sections(text)
            for axis in AXES:
                target = OUT / f"{country.slug}-{AXES[axis][0]}.json"
                if target.exists():
                    old = json.loads(target.read_text(encoding="utf-8"))
                    method = old.get("verification", {}).get("method", "")
                    if not method.startswith("KOICA 2026 지역별 참여전략 자료집의 해당 국가 페이지"):
                        skipped += 1
                        continue
                data = institution(axis, country, region, pipeline_text, procurement_text)
                target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                made += 1
    update_manifest()
    print(f"생성 {made}개, 기존 보존 {skipped}개, 전체 국가 {sum(len(r['countries']) for r in REGIONS.values())}개")


if __name__ == "__main__":
    main()
