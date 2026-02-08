# app/models/report_schema.py
# =========================
# 수정 필요
# =========================

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime


class ReportListItem(BaseModel):
    report_id: str
    case_id: Optional[str] = None
    report_type: str = Field(..., description="INTERIM|FINAL|DECISION")
    title: str
    created_at: str


class ReportDetail(BaseModel):
    report_id: str
    case_id: Optional[str] = None
    report_type: str = Field(..., description="INTERIM|FINAL|DECISION")
    title: str
    content: Dict[str, Any]
    created_at: str


class ReportListResponse(BaseModel):
    total: int
    reports: List[ReportListItem]

# =======

DecisionType = Literal["TRANSFER", "NON_TRANSFER", "SUSPENSION"]

class CaseDetail(BaseModel):
    title: str
    description: str
    summary: Dict[str, Any]   # 👉 통째로 받기
    type: Literal["ASSAULT","THEFT","FRAUD","TRAFFIC","OTHER"]
    status: Literal["OPEN","ONGOING","DONE"]
    occurred_at: datetime
    location: str
    created_at: datetime
    updated_at: datetime

class FinalAnalysis(BaseModel):
    final_id: str
    case_id: str
    recommended_decision: DecisionType
    decision_summary: str
    legal_issue_summary: str
    evidence_sufficiency_summary: str
    remaining_risk_summary: str
    created_at: datetime

class ReportDraftRequest(BaseModel):
    case_detail: CaseDetail
    decision_type: DecisionType
    final_analysis: FinalAnalysis

# 공통 응답 형식
class ReportDraftResponse(BaseModel):
    title: str
    content: Dict[str, Any]


