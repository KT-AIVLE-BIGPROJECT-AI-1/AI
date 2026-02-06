"""
이미지 분석 API 엔드포인트
POST /analysis/img
"""
from fastapi import APIRouter, HTTPException, status

from app.models.analysis_image_schema import (
    ImageAnalysisRequest,
    ImageAnalysisResponse
)
from app.services.analysis_image_service import ImageAnalysisService

router = APIRouter(prefix="/analysis", tags=["Analysis - Image"])


@router.post(
    "/img",
    response_model=ImageAnalysisResponse,
    summary="이미지 분석",
    description="이미지 파일을 분석하여 사건과 관련된 시각적 정보를 추출합니다."
)
async def analyze_image(request: ImageAnalysisRequest) -> ImageAnalysisResponse:
    """
    이미지 분석 API
    
    - **file_id**: 분석할 이미지 파일의 고유 ID
    - **file_path**: 이미지 파일의 실제 경로
    - **case_context**: 사건 정보 (선택사항)
    
    Returns:
        ImageAnalysisResponse: 이미지 분석 결과
    """
    try:
        service = ImageAnalysisService()
        
        result = service.analyze(
            file_id=request.file_id,
            file_path=request.file_path,
            case_context=request.case_context
        )
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"이미지 분석 중 오류 발생: {str(e)}"
        )
