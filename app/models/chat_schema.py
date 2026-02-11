# app/models/chat_schema.py

from pydantic import BaseModel, Field
from typing import List, Optional


class ChatRequest(BaseModel):
    role: str = Field(..., description="user 또는 assistant")
    message: str = Field(..., description="채팅 메시지")


class UsedContext(BaseModel):
    analysis_ids: List[str] = Field(default_factory=list, description="참조한 분석 ID 목록")
    type: Optional[str] = Field(default=None, description="참조 타입")


class ChatResponse(BaseModel):
    message: str = Field(..., description="AI 응답 메시지")
    used_context: UsedContext = Field(default_factory=UsedContext, description="사용된 컨텍스트")