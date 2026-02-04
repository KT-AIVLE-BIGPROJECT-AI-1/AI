# app/evaluator.py
from typing import List, Dict, Any
from app.llm_utils import call_llm_json

def evaluate_criteria(case_summary, legal_criteria):
    evaluations = []

    for c in legal_criteria:

        # dict / Pydantic 객체 모두 대응
        if isinstance(c, dict):
            criterion_text = c.get("criterion_text")
        else:
            criterion_text = getattr(c, "criterion_text", str(c))

        prompt = f"""
현재 사건 기준 평가

⚠️ 응답 규칙:
- status가 **SATISFIED(충족)** 이면  
  → reason만 작성하고 evidence_gap은 빈 문자열로 둘 것.

- status가 **NOT_SATISFIED(불충족)** 또는 **INSUFFICIENT(미확인)** 이면  
  → reason + evidence_gap을 모두 작성할 것.

허용 status 값:
SATISFIED | NOT_SATISFIED | INSUFFICIENT | UNCERTAIN

JSON:
{{
  "status": "",
  "reason": "",
  "evidence_gap": ""
}}

사건:
{case_summary}

기준:
{criterion_text}
"""

        res = call_llm_json(prompt)

        status = res.get("status", "UNCERTAIN")
        reason = res.get("reason", "")
        evidence_gap = res.get("evidence_gap", "")

        # 🔥 핵심 로직 — 당신 요구사항 반영
        if status == "SATISFIED":
            evidence_gap = ""   # 강제 비우기

        evaluations.append({
            "criterion_text": criterion_text,
            "status": status,
            "reason": reason,
            "evidence_gap": evidence_gap
        })

    return evaluations
