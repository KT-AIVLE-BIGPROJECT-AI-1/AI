import json, re
from typing import Any, Dict, List, Optional

from openai import OpenAI

from app.models.legal_criteria_schema import LegalCriteriaRequest
from app.core.criminal_law_rag import CriminalLawRAG
from app.core.precedent_embedding import PrecedentIndex


# ---------- 유틸 ----------
def _clean_json(text: str) -> dict:
    text = re.sub(r"```json|```", "", text).strip()
    try:
        return json.loads(text)
    except:
        start = text.find("{")
        end = text.rfind("}")
        return json.loads(text[start:end+1])


# ---------- ① 법리 쟁점 ----------
def infer_legal_issues_with_criminal_law_api(
    client: OpenAI,
    case_json: dict,
    criminal_law_rag: CriminalLawRAG,
    top_k: int = 10,
):
    law_results = criminal_law_rag.search(case_json["description"], top_k=top_k)

    articles_text = "\n\n".join(
        [f"[{a['article']}]\n{a['text'][:600]}..." for a in law_results]
    )

    prompt = f"""
당신은 형법 전문 검토 AI입니다.

사건 사실:
{case_json["description"]}

구조화 요약:
{json.dumps(case_json["summary"], ensure_ascii=False, indent=2)}

사건 유형:
{case_json["type"]}

검색된 형법 조문:
{articles_text}

규칙:
- 각 쟁점은 반드시 "~죄 성립 여부"
- 2~4개 생성
- 각 쟁점마다 하나의 related_law 필수

JSON만 출력:
{{
  "issues": [
    {{"issue_name": "", "related_law": ""}}
  ]
}}
"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    parsed = _clean_json(resp.choices[0].message.content)
    return parsed.get("issues", [])


# ---------- ② 법리 기준 ----------
def derive_legal_criteria_with_criminal_law_api(
    client: OpenAI,
    legal_issue: Dict[str, Any],
    criminal_law_rag: CriminalLawRAG,
    precedent_index: PrecedentIndex,
    case_json: dict,
):
    law_details = criminal_law_rag.search(legal_issue["related_law"], top_k=3)
    law_context = "\n\n".join([f"[{a['article']}]\n{a['text']}" for a in law_details])

    prompt = f"""
법리 쟁점: {legal_issue['issue_name']}
관련 법률: {legal_issue['related_law']}

형법 조문:
{law_context}

사건 요약:
{json.dumps(case_json['summary'], ensure_ascii=False)}

규칙:
- 각 항목 "~ 여부"
- 5~8개
- criterion_text에 조문 번호 포함

JSON만 출력:
{{
  "criteria": ["항목1", "항목2"]
}}
"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    parsed = _clean_json(resp.choices[0].message.content)
    items = parsed.get("criteria", [])

    # 판례 연결
    precedents = precedent_index.search_similar(legal_issue["issue_name"], top_k=3)

    results = []
    for i, text in enumerate(items):
        p = precedents[i % len(precedents)] if precedents else {}
        results.append({
            "criterion_text": text,
            "precedent_case_no": p.get("precedent_id"),
            "precedent_decision_date": p.get("decision_date"),
        })
    return results


# ---------- ③ 사건 정보 기준 평가 ----------
def evaluate_criterion_with_case_info(
    client: OpenAI,
    criterion: dict,
    case_json: dict,
):
    prompt = f"""
법리 기준:
{criterion['criterion_text']}

사건 사실:
{case_json['description']}

구조화 요약:
{json.dumps(case_json['summary'], ensure_ascii=False)}

아래 JSON만 출력:
{{
  "status": "SATISFIED | NOT_SATISFIED | INSUFFICIENT",
  "reason": "2~3문장",
  "evidence_gap": "필요 증거 또는 null"
}}
"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    parsed = _clean_json(resp.choices[0].message.content)
    return parsed


# ---------- ④ 전체 파이프라인 ----------
def analyze_legal_criteria_pipeline(
    client: OpenAI,
    criminal_law_rag: CriminalLawRAG,
    precedent_index: PrecedentIndex,
    case: LegalCriteriaRequest,
):
    case_json = case.model_dump()

    issues = infer_legal_issues_with_criminal_law_api(
        client, case_json, criminal_law_rag
    )

    response_issues = []

    for issue in issues:
        criteria = derive_legal_criteria_with_criminal_law_api(
            client, issue, criminal_law_rag, precedent_index, case_json
        )

        evaluated = []
        for c in criteria:
            evaluation = evaluate_criterion_with_case_info(
                client, c, case_json
            )
            evaluated.append({
                "criterion_text": c["criterion_text"],
                "precedent_case_no": c.get("precedent_case_no"),
                "precedent_decision_date": c.get("precedent_decision_date"),
                "evaluation": evaluation,
            })

        response_issues.append({
            "issue_name": issue["issue_name"],
            "related_law": issue["related_law"],
            "legal_criteria": evaluated,
        })

    return {"legal_issues": response_issues}
