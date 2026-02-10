# app/models/report_final_schema.py

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class CaseSummary(BaseModel):
    action: Optional[str] = Field(None)
    object: Optional[str] = Field(None)
    place: Optional[str] = Field(None)
    time: Optional[str] = Field(None)
    result: Optional[str] = Field(None)


class CaseDetail(BaseModel):
    case_id: str
    assignee_user_id: str
    title: str
    description: str
    summary: CaseSummary
    type: str = Field(..., description="ASSAULT|THEFT|FRAUD|MURDER|TRAFFIC|OTHER")
    status: str
    occurred_at: str
    location: str
    created_at: str
    updated_at: str


class FinalAnalysis(BaseModel):
    final_id: str
    case_id: str
    recommended_decision: str = Field(..., description="TRANSFER|NON_TRANSFER|SUSPENSION")
    decision_summary: str
    legal_issue_summary: str
    evidence_sufficiency_summary: str
    remaining_risk_summary: str
    created_at: str


class ReportFinalRequest(BaseModel):
    case_detail: CaseDetail
    final_analysis: FinalAnalysis


class ReportFinalResponse(BaseModel):
    title: str = Field(..., description="문서 최상단에 들어갈 제목")
    content: Dict[str, Any] = Field(
        ...,
        description="""
        수사결과보고 양식 content keys:
        - case_name: 사건명
        - suspect: 피의자
        - charge: 죄명
        - case_overview: 사건 개요 (object)
            - occurred_at: 발생일시
            - location: 발생장소
            - case_details: 사건경위
        - investigation_result: 수사 결과 (object)
            - collected_evidence: 확보 증거
            - analysis_details: 분석 내용
        - legal_review: 법리 검토 (object)
            - applicable_law: 적용 법조
            - elements: 구성요건
            - overall_judgment: 종합 판단
        - transfer_opinion: 송치 의견 (object)
            - opinion: 의견
            - judgment_basis: 판단 근거
            - remaining_risk: 잔여 리스크
        - special_notes: 특이사항
        """
    )