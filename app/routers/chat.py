<<<<<<< HEAD
# app/routers/chat.py

from fastapi import APIRouter, HTTPException
from app.models.chat_schema import (
    ChatRequest,
    ChatResponse
)
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/respond", response_model=ChatResponse)
async def chat_respond(request: ChatRequest):
    """
    채팅
    
    **사용자 메시지를 받아 AI가 응답합니다.**
    
    **입력:**
    - role: "user" | "assistant" | "system"
    - message: 메시지 내용
    
    **출력:**
    - message: AI 응답
    - used_context: 사용된 분석 컨텍스트
      - analysis_ids: 참조한 분석 ID 목록
      - type: 분석 타입 (DOC/IMG/VDO/STT/null)
    
    **예시:**
```
    요청: { "role": "user", "message": "압수물 목록에 뭐가 있어?" }
    응답: { 
      "message": "압수물 목록에는...",
      "used_context": {
        "analysis_ids": [],
        "type": "DOC"
      }
    }
```
    """
    try:
        response = ChatService.chat(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"채팅 처리 실패: {str(e)}")
=======
from fastapi import APIRouter, Depends
from openai import OpenAI

from app.models.chat_schema import (
    ChatRespondRequest,
    ChatRespondResponse,
    UsedContext
)
from app.services.chat_service import VideoInvestigationChatbotAPI
from app.config import OPENAI_API_KEY

router = APIRouter(prefix="/chat", tags=["Chat"])

def get_client():
    return OpenAI(api_key=OPENAI_API_KEY)

@router.post("/respond", response_model=ChatRespondResponse)
def chat_respond(
    req: ChatRespondRequest,
    client: OpenAI = Depends(get_client),
):
    chatbot = VideoInvestigationChatbotAPI(
        client=client,
        video_events=[v.dict() for v in req.video_events]
    )

    answer, ctx = chatbot.explain(req.chat.message)

    return {
        "message": answer,
        "used_context": UsedContext(**ctx)
    }
>>>>>>> 88bdb9c (commit)
