# app/services/video_event_service.py

import requests
import cv2
import base64
import json
import time
import uuid
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime, timezone
from openai import OpenAI, RateLimitError


# ============================================================
# 파일 다운로드 유틸
# ============================================================

def download_video(presigned_url: str, save_dir: str = "temp_videos") -> str:
    """
    presignedURL로 영상 다운로드 후 로컬 경로 반환
    """
    Path(save_dir).mkdir(exist_ok=True)

    file_path = f"{save_dir}/{uuid.uuid4()}.mp4"

    r = requests.get(presigned_url)
    with open(file_path, "wb") as f:
        f.write(r.content)

    return file_path


# ============================================================
# CrimeDetector 클래스 (당신 코랩 코드 기반)
# ============================================================

class CrimeDetector:

    def __init__(self, client: OpenAI, model="gpt-4o-mini"):
        self.client = client
        self.model = model

    def extract_frames(self, video_path: str, interval: float = 2.0) -> List[Dict]:
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_interval = int(fps * interval)

        frames = []
        frame_count = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % frame_interval == 0:
                timestamp = frame_count / fps

                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                _, buffer = cv2.imencode('.jpg', frame_rgb)
                base64_image = base64.b64encode(buffer).decode('utf-8')

                frames.append({
                    "timestamp": round(timestamp, 2),
                    "base64_image": base64_image
                })

            frame_count += 1

        cap.release()
        return frames

    def analyze_frame(self, base64_image: str, case_context: str, retry_count: int = 3) -> str:
        prompt = f"""당신은 범죄 영상 분석 전문가입니다.

{case_context}

이 프레임에서 관찰되는 객관적 사실만 기술하십시오.
"""

        for attempt in range(retry_count):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }],
                    temperature=0.0,
                    max_tokens=500
                )
                return response.choices[0].message.content.strip()

            except RateLimitError:
                time.sleep(5)

        return "분석 실패"

    def detect_events(self, frame_analyses: List[Dict], case_context: str) -> List[Dict]:
        timeline = "\n\n".join([
            f"[{fa['timestamp']}초] {fa['analysis']}"
            for fa in frame_analyses
        ])

        prompt = f"""영상 타임라인:
{timeline}

이걸 기반으로 사건 이벤트를 JSON으로 정리:
{{
  "events": [
    {{
      "start_time": 5.0,
      "end_time": 9.0,
      "event_type": "ASSAULT",
      "event_description": "폭행 장면 감지"
    }}
  ]
}}
"""

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"}
        )

        result = json.loads(resp.choices[0].message.content)
        return result.get("events", [])

    def analyze(self, video_path: str, case_context: str = "") -> List[Dict]:
        frames = self.extract_frames(video_path, interval=2.0)

        frame_analyses = []
        for frame in frames:
            analysis_text = self.analyze_frame(
                frame["base64_image"], case_context
            )
            frame_analyses.append({
                "timestamp": frame["timestamp"],
                "analysis": analysis_text
            })

        events = self.detect_events(frame_analyses, case_context)

        video_events = []
        for e in events:
            video_events.append({
                "startTime": e.get("start_time"),
                "endTime": e.get("end_time"),
                "eventType": e.get("event_type"),
                "description": e.get("event_description")
            })

        return video_events

