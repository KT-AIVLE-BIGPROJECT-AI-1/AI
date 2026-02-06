"""
이미지 분석 관련 스키마
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class ImageAnalysisRequest(BaseModel):
    """이미지 분석 요청"""
    file_id: str = Field(..., description="분석할 이미지 파일 ID")
    file_path: str = Field(..., description="이미지 파일 경로")
    case_context: Optional[dict] = Field(None, description="사건 컨텍스트 (CASE JSON)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_id": "img-123-456",
                "file_path": "/path/to/image.jpg",
                "case_context": {
                    "case_id": "2e6b7f2a-6b1d-4c9e-9e59-4c1b2a7f3d91",
                    "title": "서울시 주택가 벽돌담 골목 스마트폰 강탈 사건"
                }
            }
        }


class ImageAnalysisResponse(BaseModel):
    """이미지 분석 응답"""
    analysis_id: str = Field(..., description="분석 ID")
    file_id: str = Field(..., description="파일 ID")
    analysis_type: str = Field("IMG", description="분석 타입")
    status: str = Field(..., description="분석 상태 (COMPLETED/PENDING/FAILED)")
    result_data: str = Field(..., description="이미지 분석 결과")
    created_at: datetime = Field(..., description="생성 시각")
    
    class Config:
        json_schema_extra = {
            "example": {
                "analysis_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "file_id": "img-123-456",
                "analysis_type": "IMG",
                "status": "COMPLETED",
                "result_data": "사진에는 좁은 골목길이 보이며...",
                "created_at": "2026-02-06T05:43:37.246003+00:00"
            }
        }
