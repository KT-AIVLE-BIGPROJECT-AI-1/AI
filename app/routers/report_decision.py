# app/routers/report_decision.py

from fastapi import APIRouter, HTTPException
from app.models.report_decision_schema import (
    ReportDecisionRequest,
    ReportDecisionResponse
)
from app.services.report_decision_service import ReportDecisionService

router = APIRouter(prefix="/reports/decision", tags=["Reports - Decision"])


@router.post("", response_model=ReportDecisionResponse)
async def generate_decision_report(request: ReportDecisionRequest):
    """
    수사 결정서 생성 (송치/불송치/수사중지)
    
    사용자가 선택한 최종 판단을 기준으로 결정서를 생성합니다.
    
    **요청:**
    - case_detail: 사건 세부 정보
    - decision_type: 사용자 최종 판단 (TRANSFER|NON_TRANSFER|SUSPENSION)
    - final_analysis: AI 분석 결과 (참고용)
    
    **응답:**
    ```json
    {
      "title": "송치 결정서",
      "content": {
        "case_name": "사건명",
        "suspect": "피의자",
        "ruling": "주문",
        "case_overview": {
          "occurred_at": "발생일시",
          "location": "발생장소",
          "case_details": "사건경위"
        },
        "judgment_reason": {
          "key_judgment": "핵심 판단",
          "detailed_reason": "세부 사유",
          "change_reason": "판단 변경 사유 (AI 추천과 다를 경우)"
        },
        "evidence_evaluation": {
          "collected_evidence": "확보 증거",
          "evidence_value": "증거 가치",
          "overall_evaluation": "종합 평가"
        },
        "legal_review": {
          "applicable_law": "적용 법조",
          "elements": "구성요건",
          "legal_judgment": "법리 판단"
        },
        "conclusion": {
          "final_opinion": "최종 의견 (한글: 송치/불송치/수사중지)",
          "follow_up": "조치사항",
          "remarks": "비고"
        }
      }
    }
    ```
    
    **특징:**
    - 사용자 판단(decision_type)을 우선으로 작성
    - AI 추천과 다를 경우 judgment_reason.change_reason에 변경 사유 포함
    - 결정 유형은 한글로 출력 (SUSPENSION → 수사중지)
    """
    try:
        response = ReportDecisionService.generate_decision_report(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"수사 결정서 생성 실패: {str(e)}")