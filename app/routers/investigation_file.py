"""
파일 업로드 API 엔드포인트
POST /analysis/upload
"""
from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from typing import List

from app.models.investigation_file_schema import (
    InvestigateFileResponse,
    BatchUploadResponse
)
from app.services.investigation_file_service import InvestigationFileService

router = APIRouter(prefix="/analysis", tags=["Investigation Files"])


@router.post(
    "/upload",
    response_model=BatchUploadResponse,
    summary="증거 파일 업로드",
    description="사건 관련 증거 파일(문서, 이미지, 영상, 음성)을 업로드합니다."
)
async def upload_investigation_files(
    case_id: str = Form(..., description="사건 ID"),
    files: List[UploadFile] = File(..., description="업로드할 파일 목록")
) -> BatchUploadResponse:
    """
    증거 파일 업로드 API
    
    - **case_id**: 파일이 속한 사건의 ID
    - **files**: 업로드할 파일들 (멀티파트 폼)
    
    Returns:
        BatchUploadResponse: 업로드 결과
    """
    try:
        service = InvestigationFileService()
        
        # 파일 업로드
        uploaded_files = await service.upload_files(case_id, files)
        
        total_count = len(files)
        success_count = len(uploaded_files)
        failed_count = total_count - success_count
        
        return BatchUploadResponse(
            files=uploaded_files,
            total_count=total_count,
            success_count=success_count,
            failed_count=failed_count
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"파일 업로드 중 오류 발생: {str(e)}"
        )


@router.post(
    "/upload/single",
    response_model=InvestigateFileResponse,
    summary="단일 파일 업로드",
    description="단일 증거 파일을 업로드합니다."
)
async def upload_single_file(
    case_id: str = Form(..., description="사건 ID"),
    file: UploadFile = File(..., description="업로드할 파일")
) -> InvestigateFileResponse:
    """
    단일 파일 업로드 API
    
    - **case_id**: 파일이 속한 사건의 ID
    - **file**: 업로드할 파일
    
    Returns:
        InvestigateFileResponse: 업로드된 파일 정보
    """
    try:
        service = InvestigationFileService()
        
        result = await service.upload_file(case_id, file)
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"파일 업로드 중 오류 발생: {str(e)}"
        )
