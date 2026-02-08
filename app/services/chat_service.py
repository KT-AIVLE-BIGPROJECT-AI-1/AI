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

