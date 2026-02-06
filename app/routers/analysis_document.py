"""
문서 분석 API 엔드포인트
POST /analysis/doc
"""
from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any

from app.models.analysis_document_schema import (
    DocumentAnalysisRequest,
    DocumentAnalysisResponse
)
from app.services.analysis_document_service import DocumentAnalysisService

router = APIRouter(prefix="/analysis", tags=["Analysis - Document"])


@router.post(
    "/doc",
    response_model=DocumentAnalysisResponse,
    summary="문서 분석",
    description="PDF, DOCX, XLSX, TXT 파일을 분석하여 사건과 관련된 핵심 정보를 추출합니다."
)
async def analyze_document(request: DocumentAnalysisRequest) -> DocumentAnalysisResponse:
    """
    문서 분석 API
    
    - **file_id**: 분석할 파일의 고유 ID
    - **file_path**: 파일의 실제 경로
    - **case_context**: 사건 정보 (선택사항)
    
    Returns:
        DocumentAnalysisResponse: 분석 결과
    """
    try:
        service = DocumentAnalysisService()
        
        result = service.analyze(
            file_id=request.file_id,
            file_path=request.file_path,
            case_context=request.case_context
        )
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"문서 분석 중 오류 발생: {str(e)}"
        )
