# app/routers/report_final.py

from fastapi import APIRouter, HTTPException
from app.models.report_final_schema import (
    ReportFinalRequest,
    ReportFinalResponse
)
from app.services.report_final_service import ReportFinalService

router = APIRouter(prefix="/reports/final", tags=["Reports - Final"])


@router.post("", response_model=ReportFinalResponse)
async def generate_final_report(request: ReportFinalRequest):
    """
    수사결과보고 생성
    
    최종 분석 결과를 바탕으로 수사결과보고를 생성합니다.
    
    **요청:**
    - case_detail: 사건 세부 정보
    - final_analysis: 최종 분석 결과
    
    **응답:**
    ```json
    {
      "title": "수사결과보고",
      "content": {
        "case_name": "사건명",
        "suspect": "피의자",
        "charge": "죄명",
        "case_overview": {
          "occurred_at": "발생일시",
          "location": "발생장소",
          "case_details": "사건경위"
        },
        "investigation_result": {
          "collected_evidence": "확보 증거",
          "analysis_details": "분석 내용"
        },
        "legal_review": {
          "applicable_law": "적용 법조",
          "elements": "구성요건",
          "overall_judgment": "종합 판단"
        },
        "transfer_opinion": {
          "opinion": "의견",
          "judgment_basis": "판단 근거",
          "remaining_risk": "잔여 리스크"
        },
        "special_notes": "특이사항"
      }
    }
    ```
    
    **송치의견:** TRANSFER(송치) | NON_TRANSFER(불송치) | SUSPENSION(수사중지)
    """
    print(request)
    try:
        response = ReportFinalService.generate_final_report(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"수사결과보고 생성 실패: {str(e)}")