"""
채팅 API 엔드포인트
POST /chat/respond
"""
from fastapi import APIRouter, HTTPException, status

from app.models.chat_log_schema import (
    ChatRequest,
    ChatResponse
)
from app.services.chat_log_service import ChatService

router = APIRouter(prefix="/chat", tags=["Chat"])


# 전역 채팅 서비스 인스턴스 (세션 관리)
# 실제 프로덕션에서는 Redis 등을 사용하여 세션 관리
_chat_services: dict = {}


def get_chat_service(case_id: str) -> ChatService:
    """사건 ID별 채팅 서비스 가져오기"""
    if case_id not in _chat_services:
        _chat_services[case_id] = ChatService()
    return _chat_services[case_id]


@router.post(
    "/respond",
    response_model=ChatResponse,
    summary="채팅 메시지 전송",
    description="사건 분석에 대한 질문을 전송하고 AI 응답을 받습니다."
)
async def chat_respond(request: ChatRequest) -> ChatResponse:
    """
    채팅 API
    
    - **case_id**: 대화 중인 사건의 ID
    - **message**: 사용자의 질문/메시지
    - **video_events**: 참조할 비디오 이벤트 (선택사항)
    - **video_frames**: 비디오 프레임 정보 (선택사항)
    - **inferences**: 분석 추론 정보 (선택사항)
    - **case_context**: 사건 컨텍스트 (선택사항)
    
    Returns:
        ChatResponse: AI의 응답
    """
    try:
        service = get_chat_service(request.case_id)
        
        response = service.process_message(
            case_id=request.case_id,
            user_message=request.message,
            case_context=request.case_context,
            video_events=request.video_events,
            video_frames=request.video_frames,
            inferences=request.inferences
        )
        
        return response
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"채팅 응답 생성 중 오류 발생: {str(e)}"
        )


@router.post(
    "/reset/{case_id}",
    summary="채팅 히스토리 초기화",
    description="특정 사건의 채팅 히스토리를 초기화합니다."
)
async def reset_chat_history(case_id: str):
    """
    채팅 히스토리 초기화 API
    
    - **case_id**: 초기화할 사건의 ID
    
    Returns:
        성공 메시지
    """
    try:
        if case_id in _chat_services:
            _chat_services[case_id].clear_history()
            return {"message": f"사건 {case_id}의 채팅 히스토리가 초기화되었습니다."}
        else:
            return {"message": "해당 사건의 채팅 히스토리가 없습니다."}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"히스토리 초기화 중 오류 발생: {str(e)}"
        )
