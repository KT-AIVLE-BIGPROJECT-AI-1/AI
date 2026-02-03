# app/pipeline.py
from typing import Dict, List, Any

from app.precedent import (
    derive_precedent_search_keywords,
    search_precedents_by_title,
    fetch_precedent_bodies,
    bm25_rerank,
)
from app.criteria import (
    extract_and_filter_criteria,
    derive_common_criteria,
    expand_criteria_from_anchor,
    make_criteria_rows,
)
from app.law_rag import build_criminal_law_vectordb
from app.evaluator import evaluate_criteria as eval_criteria

from app.llm_utils import call_llm_json   # 아래에 따로 만들 것


# ==============================
# ① CASE 구조화
# ==============================
def structure_case(case: Dict[str, Any]) -> Dict[str, Any]:
    prompt = f"""
다음 사건을 사실 중심으로 구조화하라.
JSON:
{{
  "행위": "",
  "객체": "",
  "장소": "",
  "시간": "",
  "결과": ""
}}
사건:
{case.get("description","")}
"""
    return call_llm_json(prompt)


# ==============================
# ② 법리 쟁점 추론
# ==============================
def infer_legal_issue(case_summary: Dict[str, Any]) -> Dict[str, str]:
    prompt = f"""
다음 사건에 대해 **형법 중심의 형사 쟁점만** 도출하라.

반드시 지켜야 할 규칙:
- 민법, 손해배상, 불법행위, 배상책임 등 **민사 개념 사용 금지**
- issue_name은 반드시 "**~죄 성립 여부**" 형식
- 결론을 내리지 말 것

related_law에는:
- 반드시 **형법 조문**을 명시할 것
- 예: "형법 제366조(재물손괴죄)"


JSON:
{{
  "issue_name": "",
  "related_law": ""
}}

사건 요약:
{case_summary}
"""
    return call_llm_json(prompt)


# ==============================
# ③ LEGAL CRITERIA 전체 파이프라인
# ==============================
def build_legal_criteria(case_summary: Dict[str, Any], legal_issue: Dict[str, Any]) -> List[Dict[str, Any]]:

    # 1) 키워드 생성
    keywords = derive_precedent_search_keywords(case_summary, legal_issue)

    # 2) 제목 기반 후보 검색
    title_candidates = search_precedents_by_title(case_summary, legal_issue, keywords)

    # 3) 판례 본문 수집
    precedent_bodies = fetch_precedent_bodies(title_candidates)

    if not precedent_bodies:
        return []

    # 4) BM25 + rerank
    reranked = bm25_rerank(precedent_bodies, case_summary, legal_issue)

    # 5) 판례별 기준 추출 + 필터
    all_criteria = extract_and_filter_criteria(
        reranked, case_summary, legal_issue, keywords
    )

    # 6) anchor 통합
    common_criteria = derive_common_criteria(all_criteria)

    if not common_criteria.get("common_criteria"):
        return []

    # 7) anchor 기반 확장
    expanded = expand_criteria_from_anchor(
        common_criteria, case_summary, legal_issue
    )

    # 8) 최종 LEGAL_CRITERIA 행 생성
    final_rows = make_criteria_rows(common_criteria, precedent_bodies, expanded)

    return final_rows