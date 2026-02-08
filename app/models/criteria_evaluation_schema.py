# app/models/criteria_evaluation_schema.py
# =========================
# 수정 필요
# =========================

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any


# ============================================================
# 공통 스키마
# ============================================================

class CaseSummary(BaseModel):
    action: str
    object: str
    interaction: str
    place: str
    time: str
    result: str


class CaseDetail(BaseModel):
    case_id: str
    title: str
    description: str
    summary: CaseSummary
    type: str
    status: str
    occurred_at: str
    location: str


class LegalIssueInfo(BaseModel):
# class LegalIssue(BaseModel):
    issue_name: str
    related_law: str


# =======

# ==================================================
# 🔹 요청 스키마 (Request)
# ==================================================

class AnalysisResult(BaseModel):
    analysis_type: str
    status: str
    result_data: Dict[str, Any]   # 👉 "단일 증거 분석 결과 JSON"

class AnalysisWrapper(BaseModel):
    analysis: AnalysisResult


    



class CriteriaEvaluationInfo(BaseModel):
    analysis_id: Optional[str] = None
    status: str
    reason: str
    evidence_gap: str


class LegalCriterionWithEvaluation(BaseModel):
    criterion_text: str
    precedent_case_no: Optional[str] = None
    precedent_decision_date: Optional[str] = None
    legal_issue: LegalIssueInfo
    criteria_evaluation: Optional[CriteriaEvaluationInfo] = None


class LegalCriterionBasic(BaseModel):
    criterion_text: str
    precedent_case_no: Optional[str] = None
    precedent_decision_date: Optional[str] = None
    legal_issue: LegalIssueInfo


class AnalysisInfo(BaseModel):
    analysis_type: str = Field(..., description="DOC|IMG|VDO|STT")
    status: str
    result_data: Any


# ============================================================
# 요청 스키마
# ============================================================

class CriteriaEvaluationRequest(BaseModel):
    case_detail: Optional[CaseDetail] = None
    analysis: Optional[AnalysisInfo] = None
    legal_criteria: List[Any]  # LegalCriterionBasic 또는 LegalCriterionWithEvaluation
    
    @field_validator('legal_criteria', mode='before')
    def validate_legal_criteria(cls, v):
        """legal_criteria가 비어있지 않은지 확인"""
        if not v or len(v) == 0:
            raise ValueError("legal_criteria는 최소 1개 이상이어야 합니다")
        return v
    
    def model_post_init(self, __context):
        """case_detail과 analysis 중 하나는 있어야 함"""
        if not self.case_detail and not self.analysis:
            raise ValueError("case_detail 또는 analysis 중 하나는 필수입니다")


# ============================================================
# 응답 스키마
# ============================================================

class CriteriaEvaluationResponse(BaseModel):
    status: str = Field(..., description="INSUFFICIENT|MET|NOT_MET")
    reason: str
    evidence_gap: str


# =======
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

