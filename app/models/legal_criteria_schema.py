# app/models/legal_criteria_schema.py
# =========================
# 수정 필요
# =========================

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Literal

CaseType = Literal["ASSAULT", "THEFT", "FRAUD", "TRAFFIC", "OTHER"]
EvalStatus = Literal["SATISFIED", "NOT_SATISFIED", "INSUFFICIENT"]

class CaseSummary(BaseModel):
    action: str
    object: str
    interaction: str
    place: str
    time: str
    result: str


# class LegalCriteriaRequest(BaseModel):
#     description: str
#     summary: CaseSummary
#     type: str = Field(..., description="ASSAULT|THEFT|FRAUD|TRAFFIC|OTHER")
#     occurred_at: str
#     location: str

class LegalCriteriaRequest(BaseModel):
    description: str
    summary: Dict[str, Any]
    type: CaseType
    occurred_at: str
    location: str


# class CriteriaEvaluation(BaseModel):
#     status: str = Field(..., description="INSUFFICIENT, MET, NOT_MET")
#     reason: str
#     evidence_gap: str

# ========== 평가 ==========
class Evaluation(BaseModel):
    status: EvalStatus
    reason: str
    evidence_gap: Optional[str] = None

# ========== 기준 ==========
class LegalCriterion(BaseModel):
    criterion_text: str
    precedent_case_no: Optional[str] = None
    precedent_decision_date: Optional[str] = None
    # evaluation: CriteriaEvaluation
    evaluation: Evaluation

# ========== 쟁점 ==========
class LegalIssue(BaseModel):
    issue_name: str
    related_law: str
    legal_criteria: List[LegalCriterion]

# ========== 최종 응답 ==========
class LegalCriteriaResponse(BaseModel):
    legal_issues: List[LegalIssue]