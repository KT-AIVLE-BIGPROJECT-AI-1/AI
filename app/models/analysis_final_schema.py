# app/models/analysis_final_schema.py

from pydantic import BaseModel, Field
from typing import List, Optional, Any, Union


# ============================================================
# 공통 스키마
# ============================================================

class CaseSummary(BaseModel):
    action: Optional[str] = None
    object: Optional[str] = None
    interaction: Optional[str] = None
    place: Optional[str] = None
    time: Optional[str] = None
    result: Optional[str] = None


class CaseDetail(BaseModel):
    title: str
    description: str
    summary: CaseSummary
    type: str = Field(..., description="ASSAULT|THEFT|FRAUD|MURDER|TRAFFIC|OTHER")
    status: str
    occurred_at: str
    location: str


class LegalIssueInfo(BaseModel):
    issue_name: str
    related_law: str


class CriteriaEvaluationInfo(BaseModel):
    analysis_id: Optional[str] = None
    status: str = Field(..., description="SATISFIED|NOT_SATISFIED|INSUFFICIENT")
    reason: str = ""
    evidence_gap: str = ""


class LegalCriterionWithEvaluation(BaseModel):
    criterion_text: str
    precedent_case_no: Optional[str] = None
    precedent_decision_date: Optional[str] = None
    legal_issue: LegalIssueInfo
    criteria_evaluation: Optional[CriteriaEvaluationInfo] = None


class AnalysisInfo(BaseModel):
    analysis_id: str
    file_type: str = Field(..., description="DOCUMENT|IMAGE|VIDEO|AUDIO")
    status: str = Field(..., description="COMPLETED|PENDING|FAILED")
    result_data: Any = Field(
        default=None,
        description="""
        파일 유형별 result_data 구조:
        - DOCUMENT: string (분석 요약 텍스트)
        - IMAGE: string (이미지 분석 텍스트)
        - VIDEO: List[{"stage": "VIDEO_EVENT", "payload": [...]}]
        - AUDIO: string (JSON 문자열) 또는 List[{"stage": "TRANSCRIPT|KEY_STATEMENT|CONTRADICTION|QUESTION", "payload": ...}]
        """
    )


class UsedContext(BaseModel):
    analysis_ids: Optional[List[str]] = Field(default_factory=list)
    type: Optional[str] = None


class ChatLog(BaseModel):
    role: str = Field(..., description="USER|AI")
    message: str
    used_context: Optional[UsedContext] = None
    created_at: str


# ============================================================
# 요청 스키마
# ============================================================

class AnalysisFinalRequest(BaseModel):
    case_detail: CaseDetail
    legal_criteria: List[LegalCriterionWithEvaluation]
    analyses: List[AnalysisInfo]
    chat_logs: Optional[List[ChatLog]] = Field(default_factory=list)


# ============================================================
# 응답 스키마
# ============================================================

class AnalysisFinalResponse(BaseModel):
    recommended_decision: str = Field(..., description="TRANSFER|NON_TRANSFER|SUSPENSION")
    decision_summary: str
    legal_issues_summary: str
    evidence_sufficiency_summary: str
    remaining_risk_summary: str