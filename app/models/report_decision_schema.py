# app/models/report_decision_schema.py

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class CaseSummary(BaseModel):
    action: Optional[str] = Field(None)
    object: Optional[str] = Field(None)
    interaction: Optional[str] = Field(None)
    place: Optional[str] = Field(None)
    time: Optional[str] = Field(None)
    result: Optional[str] = Field(None)


class CaseDetail(BaseModel):
    title: str
    description: str
    summary: CaseSummary
    type: str = Field(..., description="ASSAULT|THEFT|FRAUD|MURDER|TRAFFIC|OTHER")
    status: str
    occurred_at: str
    location: str


class FinalAnalysis(BaseModel):
    final_id: str
    case_id: str
    recommended_decision: str = Field(..., description="TRANSFER|NON_TRANSFER|SUSPENSION")
    decision_summary: str
    legal_issues_summary: str
    evidence_sufficiency_summary: str
    remaining_risk_summary: str
    created_at: str


class ReportDecisionRequest(BaseModel):
    case_detail: CaseDetail
    decision_type: str = Field(..., description="TRANSFER|NON_TRANSFER|SUSPENSION (사용자 판단)")
    final_analysis: FinalAnalysis


class ReportDecisionResponse(BaseModel):
    title: str = Field(..., description="문서 최상단에 들어갈 제목")
    content: Dict[str, Any] = Field(
        ...,
        description="""
        수사 결정서 양식 content keys:
        - case_name: 사건명
        - suspect: 피의자
        - ruling: 주문
        - case_overview: 사건 개요 (object)
            - occurred_at: 발생일시
            - location: 발생장소
            - case_details: 사건경위
        - judgement_reason: 판단 이유 (object)
            - key_judgement: 핵심 판단
            - detailed_reason: 세부 사유
            - change_reason: 판단 변경 사유 (AI 추천과 다를 경우)
        - evidence_evaluation: 증거 평가 (object)
            - collected_evidence: 확보 증거
            - evidence_value: 증거 가치
            - overall_evaluation: 종합 평가
        - legal_review: 법리 검토 (object)
            - applicable_law: 적용 법조
            - elements: 구성요건
            - overall_judgement: 법리 판단
        - conclusion: 결론 (object)
            - final_opinion: 최종 의견
            - follow_up: 조치사항
            - remarks: 비고
        """
    )