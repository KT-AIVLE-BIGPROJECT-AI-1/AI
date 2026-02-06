"""
분석 콜백 API 엔드포인트
POST /cases/{caseId}/analysis/{analysisId}/callback
"""
from fastapi import APIRouter, HTTPException, status, Path

from app.models.analysis_callback_schema import (
    AnalysisCallbackRequest,
    AnalysisCallbackResponse,
    CallbackStage
)
from app.services.analysis_callback_service import AnalysisCallbackService

router = APIRouter(prefix="/cases", tags=["Analysis Callback"])


@router.post(
    "/{case_id}/analysis/{analysis_id}/callback",
    response_model=AnalysisCallbackResponse,
    summary="분석 콜백 처리",
    description="분석 프로세스의 각 단계별 콜백을 처리합니다 (TRANSCRIPT, KEY_STATEMENT, CONTRADICTION, QUESTION, VIDEO_EVENT, SUMMARY)."
)
async def handle_analysis_callback(
    case_id: str = Path(..., description="사건 ID"),
    analysis_id: str = Path(..., description="분석 ID"),
    request: AnalysisCallbackRequest = None
) -> AnalysisCallbackResponse:
    """
    분석 콜백 처리 API
    
    이 엔드포인트는 다음 단계들의 콜백을 통합 처리합니다:
    - **TRANSCRIPT**: 음성 전사 결과
    - **KEY_STATEMENT**: 핵심 진술 추출 결과
    - **CONTRADICTION**: 모순 탐지 결과
    - **QUESTION**: 추가 질문 생성 결과
    - **VIDEO_EVENT**: 비디오 이벤트 분석 결과
    - **SUMMARY**: 최종 요약 결과
    
    Args:
        case_id: 사건 ID (URL 경로)
        analysis_id: 분석 ID (URL 경로)
        request: 콜백 요청 데이터
    
    Returns:
        AnalysisCallbackResponse: 콜백 처리 결과
    """
    try:
        service = AnalysisCallbackService()
        
        # payload를 dict로 변환
        if hasattr(request.payload, 'model_dump'):
            payload_dict = request.payload.model_dump()
        elif isinstance(request.payload, dict):
            payload_dict = request.payload
        else:
            payload_dict = dict(request.payload)
        
        response = service.process_callback(
            case_id=case_id,
            analysis_id=analysis_id,
            stage=request.stage,
            payload=payload_dict
        )
        
        return response
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"콜백 처리 중 오류 발생: {str(e)}"
        )


@router.get(
    "/{case_id}/analysis/{analysis_id}/callback/{stage}",
    summary="콜백 데이터 조회",
    description="저장된 콜백 데이터를 조회합니다."
)
async def get_callback_data(
    case_id: str = Path(..., description="사건 ID"),
    analysis_id: str = Path(..., description="분석 ID"),
    stage: CallbackStage = Path(..., description="콜백 단계")
):
    """
    콜백 데이터 조회 API
    
    Args:
        case_id: 사건 ID
        analysis_id: 분석 ID
        stage: 조회할 콜백 단계
    
    Returns:
        저장된 콜백 데이터
    """
    try:
        service = AnalysisCallbackService()
        
        data = service.get_callback_data(case_id, analysis_id, stage)
        
        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"해당 콜백 데이터를 찾을 수 없습니다: {case_id}/{analysis_id}/{stage}"
            )
        
        return data
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"데이터 조회 중 오류 발생: {str(e)}"
        )
