# app/criteria.py
from typing import List, Dict, Any
from app.llm_utils import call_llm_json

def extract_and_filter_criteria(reranked, case_summary, legal_issue, keywords):
    all_criteria=[]
    for p in reranked:
        prompt=f"""
판례에서 판단 요소 추출
JSON: {{"criteria":[]}}
본문:{p["body"]}
"""
        res=call_llm_json(prompt)
        for c in res.get("criteria",[]):
            all_criteria.append({
                "precedent_case_no": p["precedent_case_no"],
                "criterion_text": str(c)
            })
    return all_criteria

def derive_common_criteria(all_criteria):
    prompt=f"""
공통 기준 통합
JSON: {{"common_criteria":[]}}
목록:{all_criteria}
"""
    return call_llm_json(prompt)

def expand_criteria_from_anchor(common_criteria, case_summary, legal_issue):
    prompt=f"""
anchor 기준 확장
JSON: {{"expanded_criteria":[]}}
"""
    return call_llm_json(prompt).get("expanded_criteria",[])

def make_criteria_rows(common_criteria, precedent_bodies, expanded):
    rows=[]
    for c in common_criteria.get("common_criteria",[]):
        rows.append({
            "criterion_text": c.get("criterion_text"),
            "precedent_case_no": c.get("precedent_case_nos",[None])[0],
            "precedent_decision_date": None
        })
    for e in expanded:
        rows.append({
            "criterion_text": e,
            "precedent_case_no": None,
            "precedent_decision_date": None
        })
    return rows