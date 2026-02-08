<<<<<<< HEAD
# app/services/chat_service.py

from openai import OpenAI
from app.config import settings
from app.models.chat_schema import (
    ChatRequest,
    ChatResponse,
    UsedContext
)

client = OpenAI(api_key=settings.OPENAI_API_KEY)


class ChatService:
    """
    채팅 서비스
    사용자의 메시지에 대해 AI가 응답하며,
    필요시 분석 결과를 참조하여 답변
    """
    
    # 메모리 저장소 (대화 히스토리)
    _chat_history = []
    
    @staticmethod
    def chat(request: ChatRequest) -> ChatResponse:
        """
        채팅 처리
        
        - 사용자 메시지 수신
        - AI 응답 생성
        - 사용된 컨텍스트 정보 반환
        """
        print("\n" + "=" * 70)
        print(f"💬 채팅 요청: {request.role}")
        print(f"   - message: {request.message[:100]}...")
        print("=" * 70)
        
        # 대화 히스토리에 추가
        ChatService._chat_history.append({
            "role": request.role,
            "content": request.message
        })
        
        # 시스템 프롬프트
        system_prompt = """당신은 경찰 수사 보조 AI입니다.

사용자의 질문에 대해:
1. 분석 결과를 참조하여 답변
2. 법률 지식을 활용하여 설명
3. 명확하고 전문적인 답변 제공

규칙:
- 존댓말 사용
- 객관적이고 중립적인 태도
- 추측은 명확히 표시
- 법적 조언이 아님을 명시"""
        
        # GPT-4o로 응답 생성
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                *ChatService._chat_history[-10:]  # 최근 10개 대화만 유지
            ]
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            ai_message = response.choices[0].message.content.strip()
            
            # 대화 히스토리에 AI 응답 추가
            ChatService._chat_history.append({
                "role": "assistant",
                "content": ai_message
            })
            
            # 사용된 컨텍스트 분석 (간단한 키워드 매칭)
            used_analysis_ids = []
            context_type = None
            
            # 메시지에서 분석 관련 키워드 감지
            message_lower = request.message.lower()
            
            if any(keyword in message_lower for keyword in ["문서", "압수물", "목록서", "서류"]):
                context_type = "DOC"
            elif any(keyword in message_lower for keyword in ["이미지", "사진", "영상", "cctv"]):
                context_type = "IMG"
            elif any(keyword in message_lower for keyword in ["전사", "음성", "녹취", "대화"]):
                context_type = "STT"
            elif any(keyword in message_lower for keyword in ["비디오", "동영상", "영상"]):
                context_type = "VDO"
            
            print(f"✅ AI 응답 생성 완료")
            print(f"   - used_context_type: {context_type}")
            print("=" * 70)
            
            return ChatResponse(
                message=ai_message,
                used_context=UsedContext(
                    analysis_ids=used_analysis_ids,
                    type=context_type
                )
            )
        
        except Exception as e:
            print(f"⚠️ 채팅 처리 실패: {e}")
            return ChatResponse(
                message=f"죄송합니다. 응답 생성 중 오류가 발생했습니다: {str(e)}",
                used_context=UsedContext(
                    analysis_ids=[],
                    type=None
                )
            )
    
    @staticmethod
    def clear_history():
        """대화 히스토리 초기화"""
        ChatService._chat_history.clear()
        print("💬 대화 히스토리 초기화 완료")
=======
from typing import List, Dict, Any
from openai import OpenAI

class VideoInvestigationChatbotAPI:
    """
    👉 case_detail 제거 버전
    VIDEO_EVENT만으로 답변 생성
    """

    def __init__(
        self,
        client: OpenAI,
        video_events: List[Dict[str, Any]]
    ):
        self.client = client

        # {analysis_id: [event, ...]}
        self.analysis_events = {}
        self.last_analysis_id = None

        for e in video_events:
            aid = e.get("analysis_id")
            if not aid:
                continue
            self.analysis_events.setdefault(aid, []).append(e)

        if self.analysis_events:
            self.last_analysis_id = next(iter(self.analysis_events))

    @staticmethod
    def _fmt_time(val) -> str:
        try:
            m, s = divmod(int(float(val)), 60)
            return f"{m:02d}:{s:02d}"
        except:
            return "00:00"

    def _build_events_block(self, aid: str) -> str:
        events = self.analysis_events.get(aid, [])
        lines = []

        for ev in events:
            t_s = self._fmt_time(ev.get("start_time", 0))
            t_e = self._fmt_time(ev.get("end_time", 0))
            lines.append(
                f"- [{t_s}~{t_e}] {ev['event_type']} : {ev['description']}"
            )
        return "\n".join(lines) if lines else "(이벤트 없음)"

    def explain(self, user_input: str):
        aid = self.last_analysis_id
        events_block = self._build_events_block(aid)

        prompt = f"""
당신은 영상 분석 수사 보조 AI입니다.

[탐지 이벤트]
{events_block}

[사용자 질문]
{user_input}

답변 원칙:
- 자연스러운 설명문으로 작성
- 법적 판단 금지
- 추정이면 (추정) 표기
"""

        resp = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=700
        )

        answer = resp.choices[0].message.content.strip()

        return answer, {"analysis_ids": [aid], "type": None}

>>>>>>> 88bdb9c (commit)
