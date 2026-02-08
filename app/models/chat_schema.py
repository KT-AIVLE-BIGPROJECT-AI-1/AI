# app/models/chat_schema.py
# =========================
# 수정 필요
# =========================

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class ChatRequest(BaseModel):
    role: str = Field(..., description="user|assistant|system")
    message: str


class UsedContext(BaseModel):
    analysis_ids: List[str] = Field(default_factory=list)
    type: Optional[str] = None


class ChatResponse(BaseModel):
    message: str
    used_context: UsedContext



# =======



# # ----------- 요청 ------------

# class VideoEventItem(BaseModel):
#     analysis_id: str
#     start_time: float
#     end_time: float
#     event_type: str
#     description: str

# class ChatInput(BaseModel):
#     role: str
#     message: str

# class ChatRespondRequest(BaseModel):
#     """
#     BE가 DB에서 VIDEO_EVENT를 조회해서 넘겨준다는 가정
#     """

#     video_events: List[VideoEventItem]   # DB에서 조회한 VIDEO_EVENT
#     chat: ChatInput                      # 사용자 질문

# # ----------- 응답 ------------

# class UsedContext(BaseModel):
#     analysis_ids: List[str]
#     type: Optional[str] = None

# class ChatRespondResponse(BaseModel):
#     message: str
#     used_context: UsedContext

