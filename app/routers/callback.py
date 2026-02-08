from fastapi import APIRouter, Path, Body

from app.models.callback_schema import (
    AnalysisCallbackRequest,
    AnalysisCallbackResponse,
)

router = APIRouter(tags=["Callback"])


@router.post(
    "/cases/{caseId}/analysis/{analysisId}/callback",
    response_model=AnalysisCallbackResponse
)
def receive_analysis_callback(
    caseId: str = Path(..., description="사건 ID"),
    analysisId: str = Path(..., description="분석 작업 ID"),
    body: AnalysisCallbackRequest = Body(...)
):
    """
    AI 서버 → BE 콜백을 '테스트용'으로 수신하는 엔드포인트

    실제 운영 환경에서는:
    - 이 엔드포인트는 BE가 구현
    - AI 서버는 이 엔드포인트를 호출만 함
    """

    print("========== CALLBACK RECEIVED ==========")
    print(f"caseId     : {caseId}")
    print(f"analysisId : {analysisId}")
    print(f"stage      : {body.stage}")
    print(f"payload    : {body.payload}")
    print("=======================================")

    # (테스트용) 단순 확인 응답
    return {"message": "Callback received"}
