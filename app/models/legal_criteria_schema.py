from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Literal

CaseType = Literal["ASSAULT", "THEFT", "FRAUD", "TRAFFIC", "OTHER"]
EvalStatus = Literal["SATISFIED", "NOT_SATISFIED", "INSUFFICIENT"]

# ========== 요청 ==========
class LegalCriteriaRequest(BaseModel):
    description: str
    summary: Dict[str, Any]
    type: CaseType
    occurred_at: str
    location: str

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
    evaluation: Evaluation

# ========== 쟁점 ==========
class LegalIssue(BaseModel):
    issue_name: str
    related_law: str
    legal_criteria: List[LegalCriterion]

# ========== 최종 응답 ==========
class LegalCriteriaResponse(BaseModel):
    legal_issues: List[LegalIssue]
