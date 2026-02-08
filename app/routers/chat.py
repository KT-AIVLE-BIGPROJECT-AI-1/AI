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
