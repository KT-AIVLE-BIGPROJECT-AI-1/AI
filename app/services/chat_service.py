# app/services/chat_service.py

from typing import List, Dict, Optional
from openai import OpenAI
from app.config import settings
from app.models.chat_schema import ChatRequest, ChatResponse, UsedContext

client = OpenAI(api_key=settings.OPENAI_API_KEY)


class ChatService:
    """채팅 서비스 - 다수 VIDEO_EVENT 교차 분석 대화"""

    _chat_history: List[Dict[str, str]] = []
    MAX_HISTORY = 20

    SYSTEM_PROMPT = """당신은 수사 보조 AI 어시스턴트입니다.
당신에게는 CCTV 영상 분석 결과(VIDEO_EVENT)가 제공되어 있습니다.
**여러 영상이 있을 수 있으며**, 각 영상은 파일명으로 구분됩니다.

**핵심 규칙:**

1. **사실 기반 답변**: VIDEO_EVENT에 기록된 객관적 사실만을 기반으로 답변하십시오.

2. **추론은 요청 시에만**: 사용자가 명시적으로 추론을 요청하기 전까지는 사실만 전달하십시오.
   - "추론할 수 있는 내용이 뭐가 있어?", "분석해줘" 등의 질문이 있을 때만 추론을 제공하십시오.
   - 추론 시 "~로 추정됩니다", "~가능성이 있습니다" 등 추정 표현을 사용하십시오.

3. **시간 질문 대응**: 특정 이벤트의 시간을 묻는 질문에는 start_time, end_time을 정확히 답변하십시오.
   - 여러 영상에 같은 유형이 있으면 각 영상별로 구분하여 답변하십시오.

4. **이벤트 요약**: "영상에 뭐가 있어?" 등의 질문에는 각 영상별로 시간순 요약하십시오.

5. **다수 영상 교차 분석** (영상 2개 이상인 경우):
   사용자가 교차 분석, 비교, 관계, 모순 등을 요청하면 다음을 수행하십시오.
   - **시간대 비교**: 각 영상의 이벤트 시간대가 겹치거나 연속되는지 분석
   - **행위 연결**: 한 영상의 도주가 다른 영상의 접근과 연결되는지 등
   - **모순 탐지**: 같은 시간대에 서로 다른 장소에서 동일인이 포착되는 등의 모순
   - **동선 추정**: 여러 CCTV를 통해 이동 경로 추정
   - **역할 분석**: 각 영상에서 인물들의 행동 패턴으로 역할 추정 (주도자, 망보기 등)
   - **수사 단서**: 영상 간 교차 분석으로 도출되는 수사에 도움이 되는 정보

6. **없는 정보**: 확인되지 않는 내용은 "영상 분석 결과에서 확인되지 않습니다"라고 답변하십시오.

{video_event_context}
"""

    @staticmethod
    def _load_video_events() -> tuple:
        """AnalysisCallbackService에서 VIDEO_EVENT 데이터 로드 (파일별 구분)"""
        from app.services.analysis_callback_service import AnalysisCallbackService

        analysis_ids = []
        video_sources = []  # [{analysis_id, origin_name, events}]

        for analysis_id, data in AnalysisCallbackService._analysis_results.items():
            file_type = data.get("file_type", "")
            if file_type != "VIDEO":
                continue

            origin_name = data.get("origin_name", f"영상_{analysis_id[:8]}")
            rd = data.get("result_data")

            if isinstance(rd, list):
                for item in rd:
                    if isinstance(item, dict) and item.get("stage") == "VIDEO_EVENT":
                        analysis_ids.append(analysis_id)
                        video_sources.append({
                            "analysis_id": analysis_id,
                            "origin_name": origin_name,
                            "events": item.get("payload", [])
                        })
            elif isinstance(rd, dict) and rd.get("stage") == "VIDEO_EVENT":
                analysis_ids.append(analysis_id)
                video_sources.append({
                    "analysis_id": analysis_id,
                    "origin_name": origin_name,
                    "events": rd.get("payload", [])
                })

        return analysis_ids, video_sources

    @staticmethod
    def _format_video_events(video_sources: List[Dict]) -> str:
        if not video_sources:
            return "[VIDEO_EVENT 데이터 없음]"

        lines = [f"[VIDEO_EVENT 분석 결과 - 총 {len(video_sources)}개 영상]"]

        for src_idx, src in enumerate(video_sources, 1):
            origin = src["origin_name"]
            events = src["events"]

            lines.append(f"\n--- 영상 {src_idx}: {origin} ---")
            for i, event in enumerate(events, 1):
                lines.append(
                    f"  이벤트 {i}: [{event['start_time']}초 ~ {event['end_time']}초] "
                    f"유형={event['event_type']} | "
                    f"설명={event['event_description']}"
                )

        if len(video_sources) >= 2:
            lines.append(f"\n[참고: {len(video_sources)}개 영상이 등록되어 있으므로 교차 분석이 가능합니다.]")

        return "\n".join(lines)

    @staticmethod
    def respond(request: ChatRequest) -> ChatResponse:
        print(f"\n💬 채팅 요청: [{request.role}] {request.message[:50]}...")

        analysis_ids, video_sources = ChatService._load_video_events()

        video_context = ChatService._format_video_events(video_sources)
        system_prompt = ChatService.SYSTEM_PROMPT.format(video_event_context=video_context)

        ChatService._chat_history.append({
            "role": request.role,
            "content": request.message
        })

        if len(ChatService._chat_history) > ChatService.MAX_HISTORY:
            ChatService._chat_history = ChatService._chat_history[-ChatService.MAX_HISTORY:]

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(ChatService._chat_history)

        used_context = UsedContext(
            analysis_ids=analysis_ids,
            type="VIDEO_EVENT" if video_sources else None
        )

        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.5,
                max_tokens=2000
            )

            assistant_message = response.choices[0].message.content.strip()

            ChatService._chat_history.append({
                "role": "assistant",
                "content": assistant_message
            })

            print(f"   ✅ 응답 생성 완료: {len(assistant_message)}자")

            return ChatResponse(
                message=assistant_message,
                used_context=used_context
            )

        except Exception as e:
            print(f"   ⚠️ 채팅 응답 실패: {e}")
            return ChatResponse(
                message=f"응답 생성에 실패했습니다: {str(e)}",
                used_context=used_context
            )