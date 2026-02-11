# app/services/chat_service.py

from typing import List, Dict
from openai import OpenAI
from app.config import settings
from app.models.chat_schema import ChatRequest, ChatResponse, UsedContext

client = OpenAI(api_key=settings.OPENAI_API_KEY)


class ChatService:
    """채팅 서비스 - VIDEO_EVENT 자동 참조"""

    _chat_history: List[Dict[str, str]] = []
    MAX_HISTORY = 20

    SYSTEM_PROMPT = """당신은 수사 보조 AI 어시스턴트입니다.

다음은 CCTV 영상 분석 결과(VIDEO_EVENT)입니다.
영상 분석 결과에 포함된 사실만을 근거로 답변하십시오.

{video_event_context}
"""

    # 🔥 OpenAI role 변환
    @staticmethod
    def _map_role(role: str) -> str:
        if role == "USER":
            return "user"
        if role == "AI":
            return "assistant"
        return "user"

    # 🔥 VIDEO_EVENT 강제 수집 로직 (안전 버전)
    @staticmethod
    def _load_video_events():
        from app.services.analysis_callback_service import AnalysisCallbackService

        analysis_ids = []
        video_sources = []

        print("📦 현재 _analysis_results 상태:")
        print(AnalysisCallbackService._analysis_results)

        for analysis_id, data in AnalysisCallbackService._analysis_results.items():

            file_type = data.get("file_type")
            if file_type != "VIDEO":
                continue

            origin_name = data.get("origin_name", f"영상_{analysis_id[:8]}")
            result_data = data.get("result_data")

            if not result_data:
                continue

            # 🔥 result_data가 list인 경우
            if isinstance(result_data, list):
                for item in result_data:
                    if isinstance(item, dict) and item.get("stage") == "VIDEO_EVENT":
                        video_sources.append({
                            "analysis_id": analysis_id,
                            "origin_name": origin_name,
                            "events": item.get("payload", [])
                        })
                        analysis_ids.append(analysis_id)

            # 🔥 result_data가 dict인 경우
            elif isinstance(result_data, dict):
                if result_data.get("stage") == "VIDEO_EVENT":
                    video_sources.append({
                        "analysis_id": analysis_id,
                        "origin_name": origin_name,
                        "events": result_data.get("payload", [])
                    })
                    analysis_ids.append(analysis_id)

        print(f"🎥 로드된 VIDEO_EVENT 개수: {len(video_sources)}")

        return analysis_ids, video_sources

    @staticmethod
    def _format_video_events(video_sources: List[Dict]) -> str:
        if not video_sources:
            return "[VIDEO_EVENT 데이터 없음]"

        lines = []

        for idx, src in enumerate(video_sources, 1):
            lines.append(f"\n--- 영상 {idx}: {src['origin_name']} ---")

            for event in src["events"]:
                lines.append(
                    f"[{event.get('start_time')}초 ~ {event.get('end_time')}초] "
                    f"{event.get('event_type')} - {event.get('event_description')}"
                )

        return "\n".join(lines)

    @staticmethod
    def respond(request: ChatRequest) -> ChatResponse:

        print(f"\n💬 채팅 요청: {request.role} - {request.message}")

        analysis_ids, video_sources = ChatService._load_video_events()

        video_context = ChatService._format_video_events(video_sources)

        system_prompt = ChatService.SYSTEM_PROMPT.format(
            video_event_context=video_context
        )

        # 내부 기록 (도메인 표현 유지)
        ChatService._chat_history.append({
            "role": request.role,
            "content": request.message
        })

        if len(ChatService._chat_history) > ChatService.MAX_HISTORY:
            ChatService._chat_history = ChatService._chat_history[-ChatService.MAX_HISTORY:]

        # 🔥 OpenAI 전달 직전 role 변환
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend([
            {
                "role": ChatService._map_role(m["role"]),
                "content": m["content"]
            }
            for m in ChatService._chat_history
        ])

        used_context = UsedContext(
            analysis_ids=analysis_ids,
            type="VIDEO_EVENT" if video_sources else None
        )

        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.4,
                max_tokens=1500
            )

            assistant_message = response.choices[0].message.content.strip()

            # 내부 표현 유지
            ChatService._chat_history.append({
                "role": "AI",
                "content": assistant_message
            })

            print("✅ GPT 응답 생성 성공")

            return ChatResponse(
                message=assistant_message,
                used_context=used_context
            )

        except Exception as e:
            print(f"❌ GPT 호출 실패: {e}")

            return ChatResponse(
                message=f"응답 생성에 실패했습니다: {str(e)}",
                used_context=used_context
            )
