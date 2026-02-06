"""
문서 분석 관련 스키마
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class AnalysisStatus(str, Enum):
    """분석 상태"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AnalysisType(str, Enum):
    """분석 타입"""
    DOC = "DOC"
    IMG = "IMG"
    VDO = "VDO"
    AUD = "AUD"


class DocumentAnalysisRequest(BaseModel):
    """문서 분석 요청"""
    file_id: str = Field(..., description="분석할 파일 ID")
    file_path: str = Field(..., description="파일 경로")
    case_context: Optional[dict] = Field(None, description="사건 컨텍스트 (CASE JSON)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_id": "84b76f99-aee9-4a14-bcd7-a8d7958272fc",
                "file_path": "/path/to/document.pdf",
                "case_context": {
                    "case_id": "2e6b7f2a-6b1d-4c9e-9e59-4c1b2a7f3d91",
                    "title": "서울시 주택가 벽돌담 골목 스마트폰 강탈 사건",
                    "type": "THEFT"
                }
            }
        }


class DocumentAnalysisResponse(BaseModel):
    """문서 분석 응답"""
    analysis_id: str = Field(..., description="분석 ID")
    file_id: str = Field(..., description="파일 ID")
    analysis_type: AnalysisType = Field(AnalysisType.DOC, description="분석 타입")
    status: AnalysisStatus = Field(..., description="분석 상태")
    result_data: str = Field(..., description="분석 결과 텍스트")
    created_at: datetime = Field(..., description="생성 시각")
    
    class Config:
        json_schema_extra = {
            "example": {
                "analysis_id": "2d0e6ac2-807a-460d-b38d-beb427a24c65",
                "file_id": "84b76f99-aee9-4a14-bcd7-a8d7958272fc",
                "analysis_type": "DOC",
                "status": "COMPLETED",
                "result_data": "본 문서는 2026년 6월 12일...",
                "created_at": "2026-02-06T05:43:37.246003+00:00"
            }
        }
