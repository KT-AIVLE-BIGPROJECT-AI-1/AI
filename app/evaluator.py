# app/evaluator.py
from typing import List, Dict, Any
from app.llm_utils import call_llm_json

def evaluate_criteria(case_summary, legal_criteria):
    evaluations=[]
    for c in legal_criteria:
        prompt=f"""
현재 사건 기준 평가
JSON: {{"status":"", "reason":"", "evidence_gap":""}}
사건:{case_summary}
기준:{c["criterion_text"]}
"""
        res=call_llm_json(prompt)

        criterion_text = (
            c.get("criterion_text") 
            if isinstance(c, dict) 
            else c
        )
        evaluations.append({
            "criterion_text": c["criterion_text"],
            "status": res.get("status","UNCERTAIN"),
            "reason": res.get("reason",""),
            "evidence_gap": res.get("evidence_gap","")
        })
    return evaluations