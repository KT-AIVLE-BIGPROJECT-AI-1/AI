# app/models/report_interim_schema.py

from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict


class CaseSummary(BaseModel):
    action: Optional[str] = Field(None)
    object: Optional[str] = Field(None)
    interaction: Optional[str] = Field(None)
    place: Optional[str] = Field(None)
    time: Optional[str] = Field(None)
    result: Optional[str] = Field(None)


class CaseDetail(BaseModel):
    case_id: str
    title: str
    description: str
    summary: CaseSummary
    type: str = Field(..., description="ASSAULT|THEFT|FRAUD|MURDER|TRAFFIC|OTHER")
    status: str
    occurred_at: str
    location: str


class ActivityLog(BaseModel):
    log_id: str
    field: str = Field(..., description="CASE|ANALYSIS|LEGAL_ISSUE|LEGAL_CRITERIA|CRITERIA_EVALUATION|CHAT_LOG|REPORT")
    activity_type: str = Field(..., description="CREATE|UPDATE|DELETE")
    payload: str
    created_at: str


class ReportInterimRequest(BaseModel):
    case_detail: CaseDetail
    selected_activity_logs: List[ActivityLog]


class ReportInterimResponse(BaseModel):
    title: str = Field(..., description="문서 최상단에 들어갈 제목")
    content: Dict[str, Any] = Field(
        ...,
        description="""
        수사보고 양식 content keys:
        - case_overview: 사건 개요 (string)
        - investigation_progress: 수사 경과 (string)
        - current_status: 현재 상황 (object)
            - collected_evidence: 확보 증거
            - legal_review: 법리 검토
            - progress_rate: 진행률
        - future_plan: 향후 계획 (string)
        """
    )