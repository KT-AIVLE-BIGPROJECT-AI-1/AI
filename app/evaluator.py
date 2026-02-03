# app/evaluator.py
from typing import List, Dict, Any
from app.llm_utils import call_llm_json

def evaluate_criteria(case_summary, legal_criteria):
    evaluations = []

    for c in legal_criteria:

        # 🔥 핵심: dict / Pydantic 객체 모두 대응
        if isinstance(c, dict):
            criterion_text = c.get("criterion_text")
        else:
            # Pydantic 객체일 가능성
            criterion_text = getattr(c, "criterion_text", str(c))

        prompt = f"""
현재 사건 기준 평가

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

        evaluations.append({
            "criterion_text": criterion_text,
            "status": res.get("status", "UNCERTAIN"),
            "reason": res.get("reason", ""),
            "evidence_gap": res.get("evidence_gap", "")
        })

    return evaluations