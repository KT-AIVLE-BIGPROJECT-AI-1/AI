# app/routers/report_interim.py

from fastapi import APIRouter, HTTPException
from app.models.report_interim_schema import (
    ReportInterimRequest,
    ReportInterimResponse
)
from app.services.report_interim_service import ReportInterimService

router = APIRouter(prefix="/reports/interim", tags=["Reports - Interim"])


@router.post("", response_model=ReportInterimResponse)
async def generate_interim_report(request: ReportInterimRequest):
    """
    수사보고 생성
    
    수사 활동 로그를 기반으로 수사보고를 생성합니다.
    
    **요청:**
    - case_detail: 사건 세부 정보
    - selected_activity_logs: 선택된 활동 로그 목록
    
    **응답:**
    ```json
    {
      "title": "수사보고",
      "content": {
        "case_overview": "사건 개요",
        "investigation_progress": "수사 경과",
        "current_status": {
          "collected_evidence": "확보 증거",
          "legal_review": "법리 검토",
          "progress_rate": "진행률"
        },
        "future_plan": "향후 계획"
      }
    }
    ```
    """
    try:
        response = ReportInterimService.generate_interim_report(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"수사보고 생성 실패: {str(e)}")