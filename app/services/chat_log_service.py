"""
채팅 서비스 (SigLIP Video RAG Chatbot 기반)
"""
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime, timezone
from openai import OpenAI

from app.config import get_settings
from app.models.chat_log_schema import ChatResponse, ChatRole


class ChatService:
    """채팅 서비스 - 사건 분석 질의응답"""
    
    def __init__(self):
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.OPENAI_API_KEY)
        self.chat_history: List[Dict[str, str]] = []
    
    def build_system_prompt(
        self, 
        case_context: Optional[Dict[str, Any]] = None,
        video_events: Optional[List[Dict[str, Any]]] = None,
        inferences: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """시스템 프롬프트 생성"""
        
        prompt_parts = [
            "당신은 범죄 수사를 돕는 AI 분석 어시스턴트입니다.",
            "사용자의 질문에 대해 제공된 증거와 분석 결과를 바탕으로 정확하게 답변하십시오.",
            "",
            "답변 원칙:",
            "- 제공된 데이터에 기반한 사실만 전달",
            "- 추측이나 가정 최소화",
            "- 명확하고 구조화된 답변",
            "- 관련 증거의 타임스탬프나 ID 언급",
            ""
        ]
        
        # 사건 정보 추가
        if case_context:
            prompt_parts.append("[사건 정보]")
            prompt_parts.append(f"사건명: {case_context.get('title', '')}")
            prompt_parts.append(f"사건 유형: {case_context.get('type', '')}")
            prompt_parts.append(f"발생 일시: {case_context.get('occured_at', '')}")
            prompt_parts.append(f"발생 장소: {case_context.get('location', '')}")
            prompt_parts.append("")
        
        # 비디오 이벤트 요약
        if video_events:
            prompt_parts.append(f"[분석된 비디오 이벤트: {len(video_events)}개]")
            for i, event in enumerate(video_events[:5], 1):  # 최대 5개만 요약
                prompt_parts.append(
                    f"{i}. {event.get('start_time', 0):.2f}s~{event.get('end_time', 0):.2f}s: "
                    f"{event.get('event_type', 'OTHER')} - {event.get('event_description', '')[:100]}"
                )
            prompt_parts.append("")
        
        # 추론 정보 요약
        if inferences:
            prompt_parts.append(f"[분석 추론: {len(inferences)}개]")
            for inference in inferences[:3]:  # 최대 3개만 요약
                insights = inference.get('insights', [])
                if insights:
                    prompt_parts.append(f"- {insights[0].get('category', '')}: {insights[0].get('inference', '')[:100]}")
            prompt_parts.append("")
        
        return "\n".join(prompt_parts)
    
    def process_message(
        self,
        case_id: str,
        user_message: str,
        case_context: Optional[Dict[str, Any]] = None,
        video_events: Optional[List[Dict[str, Any]]] = None,
        video_frames: Optional[Dict[str, Any]] = None,
        inferences: Optional[List[Dict[str, Any]]] = None
    ) -> ChatResponse:
        """사용자 메시지 처리 및 AI 응답 생성"""
        
        chat_id = str(uuid.uuid4())
        
        # 시스템 프롬프트 생성
        system_prompt = self.build_system_prompt(
            case_context=case_context,
            video_events=video_events,
            inferences=inferences
        )
        
        # 대화 히스토리에 사용자 메시지 추가
        self.chat_history.append({
            "role": "user",
            "content": user_message
        })
        
        # GPT 호출
        try:
            messages = [{"role": "system", "content": system_prompt}] + self.chat_history
            
            response = self.client.chat.completions.create(
                model=self.settings.GPT_MODEL,
                messages=messages,
                temperature=0.3,
                max_tokens=1000
            )
            
            ai_message = response.choices[0].message.content.strip()
            
            # 히스토리에 AI 응답 추가
            self.chat_history.append({
                "role": "assistant",
                "content": ai_message
            })
            
            # 사용된 컨텍스트 정보 추출 (간단한 예시)
            used_context = {}
            if video_events:
                used_context["video_event_count"] = len(video_events)
            if inferences:
                used_context["inference_count"] = len(inferences)
            
            return ChatResponse(
                chat_id=chat_id,
                case_id=case_id,
                role=ChatRole.AI,
                message=ai_message,
                used_context=used_context,
                created_at=datetime.now(timezone.utc)
            )
        
        except Exception as e:
            error_message = f"응답 생성 중 오류가 발생했습니다: {str(e)}"
            
            return ChatResponse(
                chat_id=chat_id,
                case_id=case_id,
                role=ChatRole.AI,
                message=error_message,
                used_context={"error": True},
                created_at=datetime.now(timezone.utc)
            )
    
    def clear_history(self):
        """대화 히스토리 초기화"""
        self.chat_history = []
    
    def get_history(self) -> List[Dict[str, str]]:
        """대화 히스토리 반환"""
        return self.chat_history
