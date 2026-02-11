# app/routers/chat.py

from fastapi import APIRouter, HTTPException
from app.models.chat_schema import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/respond", response_model=ChatResponse)
async def chat_respond(request: ChatRequest):
    """
    채팅 응답 (VIDEO_EVENT 기반)

    **첫 요청 시 video_events를 함께 전달:**
```json
    {
      "role": "user",
      "message": "영상에 어떤 장면들이 있어?",
      "video_events": [
        {
          "start_time": 2.0,
          "end_time": 6.0,
          "event_type": "MOVEMENT",
          "event_description": "두 사람이 골목길을 걸어오고 있다."
        }
      ]
    }
```

    **이후 요청은 message만:**
```json
    {
      "role": "user",
      "message": "폭행 장면은 몇 초에 나와?"
    }
```
    """
    try:
        response = ChatService.respond(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"채팅 응답 실패: {str(e)}")