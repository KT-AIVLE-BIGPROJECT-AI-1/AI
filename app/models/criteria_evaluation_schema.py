from typing import Optional, List, Dict, Any
from pydantic import BaseModel

# ==================================================
# 🔹 요청 스키마 (Request)
# ==================================================

class AnalysisResult(BaseModel):
    analysis_type: str
    status: str
    result_data: Dict[str, Any]   # 👉 "단일 증거 분석 결과 JSON"

class AnalysisWrapper(BaseModel):
    analysis: AnalysisResult


class LegalIssue(BaseModel):
    issue_name: str
    related_law: str


class CriteriaEvaluationInput(BaseModel):
    analysis_id: Optional[str] = None
    status: str
    reason: str
    evidence_gap: Optional[str] = None


class LegalCriteriaItem(BaseModel):
    criterion_text: str
    precedent_case_no: str
    precedent_decision_date: str
    legal_issue: LegalIssue
    criteria_evaluation: CriteriaEvaluationInput


class EvaluateCriteriaRequest(BaseModel):
    """
    POST /legal-criteria/evaluate 요청 바디 최종 형태
    """
    analysis: AnalysisWrapper          # 👉 단일 증거
    legal_criteria: List[LegalCriteriaItem]  # 👉 평가할 기준(들)


# ==================================================
# 🔹 응답 스키마 (Response)
# ==================================================

class CriteriaEvaluationResponse(BaseModel):
    status: str
    reason: str
    evidence_gap: Optional[str]

