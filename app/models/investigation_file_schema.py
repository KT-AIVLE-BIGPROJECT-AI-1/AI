"""
파일 업로드 및 조사 파일 관련 스키마
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class FileType(str, Enum):
    """파일 타입"""
    DOCUMENT = "document"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


class InvestigateFileRequest(BaseModel):
    """파일 업로드 요청 (단일 파일)"""
    case_id: str = Field(..., description="사건 ID")
    origin_name: str = Field(..., description="원본 파일명")
    file_type: FileType = Field(..., description="파일 타입")
    
    class Config:
        json_schema_extra = {
            "example": {
                "case_id": "2e6b7f2a-6b1d-4c9e-9e59-4c1b2a7f3d91",
                "origin_name": "evidence_photo.jpg",
                "file_type": "image"
            }
        }


class InvestigateFileResponse(BaseModel):
    """파일 업로드 응답"""
    file_id: str = Field(..., description="파일 ID")
    case_id: str = Field(..., description="사건 ID")
    origin_name: str = Field(..., description="원본 파일명")
    file_path: str = Field(..., description="저장된 파일 경로")
    file_type: FileType = Field(..., description="파일 타입")
    file_size: int = Field(..., description="파일 크기 (bytes)")
    created_at: datetime = Field(..., description="생성 시각")
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_id": "84b76f99-aee9-4a14-bcd7-a8d7958272fc",
                "case_id": "2e6b7f2a-6b1d-4c9e-9e59-4c1b2a7f3d91",
                "origin_name": "evidence_photo.jpg",
                "file_path": "/uploads/84b76f99-aee9-4a14-bcd7-a8d7958272fc.jpg",
                "file_type": "image",
                "file_size": 2048576,
                "created_at": "2026-02-06T05:43:37.246003+00:00"
            }
        }


class BatchUploadResponse(BaseModel):
    """배치 업로드 응답"""
    files: List[InvestigateFileResponse] = Field(..., description="업로드된 파일 목록")
    total_count: int = Field(..., description="총 파일 수")
    success_count: int = Field(..., description="성공한 파일 수")
    failed_count: int = Field(..., description="실패한 파일 수")
