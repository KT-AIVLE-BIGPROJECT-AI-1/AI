"""
채팅 로그 관련 스키마
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class ChatRole(str, Enum):
    """채팅 역할"""
    USER = "USER"
    AI = "AI"


class ChatRequest(BaseModel):
    """채팅 요청"""
    case_id: str = Field(..., description="사건 ID")
    message: str = Field(..., description="사용자 메시지")
    video_events: Optional[List[Dict[str, Any]]] = Field(None, description="비디오 이벤트 목록")
    video_frames: Optional[Dict[str, Any]] = Field(None, description="비디오 프레임 정보")
    inferences: Optional[List[Dict[str, Any]]] = Field(None, description="추론 정보")
    case_context: Optional[Dict[str, Any]] = Field(None, description="사건 컨텍스트")
    
    class Config:
        json_schema_extra = {
            "example": {
                "case_id": "2e6b7f2a-6b1d-4c9e-9e59-4c1b2a7f3d91",
                "message": "범행 준비의 증거 시간은 어디가 수상한거야?",
                "video_events": [],
                "case_context": {}
            }
        }


class ChatResponse(BaseModel):
    """채팅 응답"""
    chat_id: str = Field(..., description="채팅 ID")
    case_id: str = Field(..., description="사건 ID")
    role: ChatRole = Field(..., description="메시지 역할 (USER/AI)")
    message: str = Field(..., description="메시지 내용")
    used_context: Dict[str, Any] = Field(default_factory=dict, description="사용된 컨텍스트 정보")
    created_at: datetime = Field(..., description="생성 시각")
    
    class Config:
        json_schema_extra = {
            "example": {
                "chat_id": "edf57321-9589-4106-a63d-7fe916e8b07c",
                "case_id": "2e6b7f2a-6b1d-4c9e-9e59-4c1b2a7f3d91",
                "role": "AI",
                "message": "범행 준비 카테고리의 증거 시간대를 분석하면...",
                "used_context": {
                    "analysis_ids": ["b3651061-7214-4f66-9765-a8964f0ee90d"],
                    "type": "evidence_time"
                },
                "created_at": "2026-02-06T06:09:01.877642+00:00"
            }
        }


class ChatLogExport(BaseModel):
    """채팅 로그 전체 내보내기"""
    chat_logs: List[ChatResponse] = Field(..., description="채팅 로그 목록")
    total_count: int = Field(..., description="총 메시지 수")
