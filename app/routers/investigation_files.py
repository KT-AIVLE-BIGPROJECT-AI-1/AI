# app/routers/investigation_files.py

from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.models.investigation_file_schema import (
    InvestigationFilesRequest,
    InvestigationFilesResponse
)
from app.services.investigation_file_service import InvestigationFileService

router = APIRouter(prefix="/analysis", tags=["Investigation Files"])


@router.post("/upload", response_model=InvestigationFilesResponse)
async def schedule_investigation_analysis(
    request: InvestigationFilesRequest,
    background_tasks: BackgroundTasks
):
    """
    수사자료 업로드 + 즉시 분석 시작

    **흐름:**
    1. 요청 수신 → 즉시 PENDING 응답 반환
    2. 백그라운드에서 file_type별 분석 자동 실행
    3. 분석 완료 시 콜백으로 결과 전송

    **분석 분기:**
    - DOCUMENT → 문서 분석 → SUMMARY 콜백
    - IMAGE → 이미지 분석 → SUMMARY 콜백
    - VIDEO → 영상 분석 → VIDEO_EVENT 콜백
    - AUDIO → 음성 분석 → TRANSCRIPT → KEY_STATEMENT → CONTRADICTION → QUESTION 콜백
    """
    try:
        # 1. 파일 등록 + 즉시 PENDING 응답
        response = InvestigationFileService.schedule_analysis(request)

        # 2. 백그라운드에서 분석 파이프라인 실행
        background_tasks.add_task(
            InvestigationFileService.run_analysis_pipeline,
            request
        )

        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"분석 작업 등록 실패: {str(e)}")