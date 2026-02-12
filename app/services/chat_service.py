# app/services/chat_service.py
# ✅ VIDEO_EVENT 텍스트 + 저장된 프레임 base64를 함께 활용
# ✅ 수사관의 시각적 질문에도 GPT-4o Vision으로 답변 가능

from typing import List, Dict
from openai import OpenAI
from app.config import settings
from app.models.chat_schema import ChatRequest, ChatResponse, UsedContext

client = OpenAI(api_key=settings.OPENAI_API_KEY)


class ChatService:
    """채팅 서비스 - VIDEO_EVENT + 프레임 Vision 질의"""

    _chat_history: List[Dict[str, str]] = []
    MAX_HISTORY = 20

    # 프레임이 있을 때 사용하는 시스템 프롬프트
    SYSTEM_PROMPT_WITH_FRAMES = """당신은 수사 보조 AI 어시스턴트입니다.

다음은 CCTV 영상 분석 결과(VIDEO_EVENT)와 해당 영상에서 추출된 프레임 이미지입니다.

[영상 분석 결과]
{video_event_context}

위 분석 결과와 제공된 프레임 이미지를 함께 참고하여 수사관의 질문에 답변하십시오.

규칙:
- 프레임 이미지에 실제로 보이는 객관적 사실만 근거로 답변할 것
- 이미지에서 확인할 수 없는 내용은 "해당 프레임에서 확인되지 않음"으로 답변할 것
- 추정, 단정, 법적 판단 금지
- 시간대별 프레임을 참고하여 시간 기반 질문에도 답변할 것
"""

    # 프레임이 없을 때 사용하는 시스템 프롬프트 (기존)
    SYSTEM_PROMPT_TEXT_ONLY = """당신은 수사 보조 AI 어시스턴트입니다.

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

    # ============================================================
    # VIDEO_EVENT + 프레임 수집
    # ============================================================

    @staticmethod
    def _load_video_events():
        """VIDEO_EVENT 텍스트 + 저장된 프레임 base64 로드"""
        from app.services.analysis_callback_service import AnalysisCallbackService

        analysis_ids = []
        video_sources = []
        all_frames = []  # 모든 영상의 프레임 통합

        for analysis_id, data in AnalysisCallbackService._analysis_results.items():

            file_type = data.get("file_type")
            if file_type != "VIDEO":
                continue

            origin_name = data.get("origin_name", f"영상_{analysis_id[:8]}")
            result_data = data.get("result_data")
            video_frames = data.get("video_frames", [])  # 저장된 프레임

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

            # 프레임 수집 (영상명 태그 포함)
            if video_frames:
                for frame in video_frames:
                    all_frames.append({
                        "origin_name": origin_name,
                        "time_sec": frame.get("time_sec", 0.0),
                        "base64": frame.get("base64", "")
                    })

        print(f"🎥 로드된 VIDEO_EVENT: {len(video_sources)}건, 프레임: {len(all_frames)}개")

        return analysis_ids, video_sources, all_frames

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

    # ============================================================
    # Vision 메시지 구성 (프레임 포함)
    # ============================================================

    @staticmethod
    def _build_vision_messages(
        system_prompt: str,
        chat_history: List[Dict],
        frames: List[Dict],
        max_frames: int = 10
    ) -> List[Dict]:
        """
        GPT-4o Vision용 메시지 구성
        - system 프롬프트 + 프레임 이미지 + 대화 히스토리
        - 프레임이 너무 많으면 균등 샘플링
        """
        messages = []

        # 1. 시스템 프롬프트 + 프레임 이미지를 첫 번째 user 메시지로 구성
        #    (Vision API에서 system role에 이미지 첨부 불가)
        system_content = [{"type": "text", "text": system_prompt}]

        # 프레임 샘플링 (max_frames 초과 시 균등 추출)
        sampled_frames = frames
        if len(frames) > max_frames:
            step = len(frames) / max_frames
            sampled_frames = [frames[int(i * step)] for i in range(max_frames)]

        for frame in sampled_frames:
            if frame.get("base64"):
                system_content.append({
                    "type": "text",
                    "text": f"[{frame['origin_name']} - {frame['time_sec']}초]"
                })
                system_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{frame['base64']}",
                        "detail": "low"
                    }
                })

        # 첫 번째 메시지: 시스템 역할 텍스트 + 프레임 이미지
        messages.append({"role": "user", "content": system_content})
        messages.append({
            "role": "assistant",
            "content": "네, 영상 분석 결과와 프레임 이미지를 확인하였습니다. 질문해 주십시오."
        })

        # 2. 이후 대화 히스토리 (텍스트만)
        for m in chat_history:
            messages.append({
                "role": ChatService._map_role(m["role"]),
                "content": m["content"]
            })

        return messages

    # ============================================================
    # 텍스트 전용 메시지 구성 (프레임 없을 때)
    # ============================================================

    @staticmethod
    def _build_text_messages(
        system_prompt: str,
        chat_history: List[Dict]
    ) -> List[Dict]:
        """기존 텍스트 전용 메시지 구성"""
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend([
            {
                "role": ChatService._map_role(m["role"]),
                "content": m["content"]
            }
            for m in chat_history
        ])
        return messages

    # ============================================================
    # 메인 응답
    # ============================================================

    @staticmethod
    def respond(request: ChatRequest) -> ChatResponse:

        print(f"\n💬 채팅 요청: {request.role} - {request.message}")

        analysis_ids, video_sources, all_frames = ChatService._load_video_events()

        video_context = ChatService._format_video_events(video_sources)

        # 내부 기록 (도메인 표현 유지)
        ChatService._chat_history.append({
            "role": request.role,
            "content": request.message
        })

        if len(ChatService._chat_history) > ChatService.MAX_HISTORY:
            ChatService._chat_history = ChatService._chat_history[-ChatService.MAX_HISTORY:]

        used_context = UsedContext(
            analysis_ids=analysis_ids,
            type="VIDEO_EVENT" if video_sources else None
        )

        try:
            # 프레임이 있으면 Vision 모드, 없으면 텍스트 모드
            if all_frames:
                print(f"   🖼️ Vision 모드: {len(all_frames)}개 프레임 포함")
                system_prompt = ChatService.SYSTEM_PROMPT_WITH_FRAMES.format(
                    video_event_context=video_context
                )
                messages = ChatService._build_vision_messages(
                    system_prompt=system_prompt,
                    chat_history=ChatService._chat_history,
                    frames=all_frames,
                    max_frames=10
                )
            else:
                print(f"   📝 텍스트 모드")
                system_prompt = ChatService.SYSTEM_PROMPT_TEXT_ONLY.format(
                    video_event_context=video_context
                )
                messages = ChatService._build_text_messages(
                    system_prompt=system_prompt,
                    chat_history=ChatService._chat_history
                )

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