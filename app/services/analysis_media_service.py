# app/services/analysis_media_service.py

import uuid
import json
import re
import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any
from openai import OpenAI

from app.config import settings
from app.models.analysis_media_schema import AnalysisMediaRequest

client = OpenAI(api_key=settings.OPENAI_API_KEY)


# ============================================================
# 비디오 프레임 추출 + GPT-4o Vision 분석
# ============================================================

class VideoAnalyzer:
    ANALYSIS_PROMPT = """당신은 CCTV 영상 분석 전문가입니다.

아래에 영상에서 추출한 프레임들이 제공됩니다.
각 프레임에는 해당 시간(초)이 표시되어 있습니다.

영상에서 발생하는 주요 이벤트를 감지하고, 각 이벤트를 아래 JSON 형식으로 출력하십시오.

**이벤트 유형:**
- ASSAULT: 폭행, 물리적 충돌
- THEFT: 절도, 강탈, 물건 빼앗기
- SUSPICIOUS: 의심스러운 행동, 배회
- MOVEMENT: 이동, 도주, 접근
- INTERACTION: 대화, 접촉, 대면
- OTHER: 기타

**규칙:**
- 프레임에 보이는 객관적 사실만 기술
- 각 이벤트의 시작/종료 시간을 최대한 정확히 추정
- 추정, 단정 금지
- 최소 1개 이상의 이벤트 감지

**출력 형식 (JSON 배열만 출력):**
[
  {{
    "start_time": 시작시간(초),
    "end_time": 종료시간(초),
    "event_type": "이벤트유형",
    "event_description": "이벤트 설명 (2-3문장)"
  }}
]
"""

    def __init__(self, client, model: str = "gpt-4o"):
        self.client = client
        self.model = model

    def extract_frames(self, video_path: Path, interval_sec: float = 2.0, max_frames: int = 15) -> List[Dict]:
        try:
            import cv2
        except ImportError:
            raise ImportError("opencv-python이 설치되어 있지 않습니다. pip install opencv-python")

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"비디오 파일을 열 수 없습니다: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        print(f"   📹 비디오 정보: {duration:.1f}초, {fps:.1f}fps, {total_frames}프레임")

        if duration <= 0:
            raise ValueError("비디오 길이를 읽을 수 없습니다")

        if duration / interval_sec > max_frames:
            interval_sec = duration / max_frames

        frames = []
        current_time = 0.0

        while current_time < duration and len(frames) < max_frames:
            frame_number = int(current_time * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = cap.read()
            if not ret:
                break

            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            b64 = base64.b64encode(buffer).decode('utf-8')

            frames.append({
                "time_sec": round(current_time, 1),
                "base64": b64
            })
            current_time += interval_sec

        cap.release()
        print(f"   📸 {len(frames)}개 프레임 추출 완료 (간격: {interval_sec:.1f}초)")
        return frames

    def analyze_video(self, video_path: Path) -> Dict:
        frames = self.extract_frames(video_path)

        if not frames:
            return {
                "stage": "VIDEO_EVENT",
                "payload": [{"start_time": 0.0, "end_time": 0.0, "event_type": "OTHER", "event_description": "프레임 추출 실패"}]
            }

        content = [{"type": "text", "text": self.ANALYSIS_PROMPT}]
        for frame in frames:
            content.append({"type": "text", "text": f"[{frame['time_sec']}초]"})
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{frame['base64']}", "detail": "low"}
            })

        print(f"   🤖 GPT-4o Vision 분석 중...")

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            temperature=0.2,
            max_tokens=2000
        )

        result_text = response.choices[0].message.content.strip()

        try:
            result_text = re.sub(r"```json|```", "", result_text).strip()
            events = json.loads(result_text)
            if not isinstance(events, list):
                events = [events]

            validated_events = []
            for event in events:
                validated_events.append({
                    "start_time": float(event.get("start_time", 0.0)),
                    "end_time": float(event.get("end_time", 0.0)),
                    "event_type": str(event.get("event_type", "OTHER")),
                    "event_description": str(event.get("event_description", ""))
                })

            print(f"   ✅ {len(validated_events)}개 이벤트 감지")
            return {"stage": "VIDEO_EVENT", "payload": validated_events}

        except (json.JSONDecodeError, Exception) as e:
            print(f"   ⚠️ JSON 파싱 실패: {e}")
            return {
                "stage": "VIDEO_EVENT",
                "payload": [{"start_time": 0.0, "end_time": 0.0, "event_type": "OTHER", "event_description": f"분석 결과 파싱 실패: {result_text[:200]}"}]
            }


# ============================================================
# 오디오 전사 + 발화자 분리 + 진술 분석
# ============================================================

class AudioAnalyzer:

    DIARIZE_PROMPT = """당신은 수사 기록 전문가입니다.

아래는 수사 관련 음성을 전사한 원문입니다.
이 전사 내용에서 **발화자를 구분**하여 대화 형식으로 재구성하십시오.

**발화자 구분 기준:**
- 질문하는 사람 → "수사관" (경찰, 검사, 조사관 등)
- 답변하는 사람 → 실제 이름이 언급되면 "피의자 홍길동" 형식, 없으면 "피의자" / "참고인" / "피해자" / "목격자"
- 첫 부분의 조사 시작 안내, 인적사항 고지 등 → "수사관"
- "네", "맞습니다", "아닙니다" 등 짧은 답변 → 직전 질문에 대한 답변자
- 반박, 부정, 해명 → 피의자/참고인

**규칙:**
- 모든 발화를 빠짐없이 포함할 것
- 원문의 내용을 변경하거나 생략하지 말 것
- 발화 순서를 반드시 유지할 것

**출력 형식 (JSON 배열만 출력):**
[
  {{
    "speaker": "수사관",
    "content": "발화 내용"
  }},
  {{
    "speaker": "피의자 김루팡",
    "content": "발화 내용"
  }}
]

**전사 원문:**
{transcript}
"""

    KEY_STATEMENT_PROMPT = """당신은 수사 전문 분석관입니다.

아래는 수사 관련 음성의 발화자별 전사 내용입니다.
전사 내용에서 **사건의 핵심이 되는 진술**을 추출하십시오.

**핵심 진술 기준:**
- 범행의 실행, 계획, 공모에 직접 관련된 진술
- 범죄 구성요건을 입증하거나 부정하는 진술
- 피의자의 범행 동기, 의도, 인식을 드러내는 진술
- 공범 간 역할 분담, 사전 모의에 관한 진술
- 알리바이 또는 알리바이를 부정하는 진술
- 증거와 관련된 사실 진술

**규칙:**
- 3~10개 추출
- 각 진술에 고유 temp_id 부여: {prefix}-1, {prefix}-2, ...
- 원문을 최대한 유지하되 핵심만 발췌
- 단순 인적사항, 절차적 안내는 제외

**전사 내용 [{source_label}]:**
{transcript}

**출력 형식 (JSON 배열만 출력):**
[
  {{
    "temp_id": "{prefix}-1",
    "content": "핵심 진술 내용"
  }}
]
"""

    CONTRADICTION_PROMPT = """당신은 수사 전문 분석관입니다.

아래는 전사 내용과 추출된 핵심 진술입니다.
핵심 진술들 간의 **모순점**을 분석하십시오.

**모순 유형:**
- TIME: 시간 관련 모순
- LOCATION: 장소 관련 모순
- CONTENT: 내용 관련 모순
- BEHAVIOR: 행동 관련 모순
- CROSS_STATEMENT: 다른 관련자의 진술과 상충

**규칙:**
- 모순이 없으면 빈 배열 [] 반환
- 명확한 모순만 추출

**전사 내용:**
{transcript}

**핵심 진술:**
{key_statements}

**출력 형식 (JSON 배열만 출력):**
[
  {{
    "statement_temp_id": "ks-1",
    "description": "모순 내용 설명 (2-3문장)",
    "type": "TIME|LOCATION|CONTENT|BEHAVIOR|CROSS_STATEMENT"
  }}
]
"""

    CROSS_CONTRADICTION_PROMPT = """당신은 수사 전문 분석관입니다.

아래는 **여러 음성 파일**의 전사 내용과 핵심 진술입니다.
각 파일 내부의 모순뿐만 아니라, **파일 간 교차 모순**도 분석하십시오.

**모순 유형:**
- TIME: 시간 관련 모순
- LOCATION: 장소 관련 모순
- CONTENT: 내용 관련 모순
- BEHAVIOR: 행동 관련 모순
- CROSS_STATEMENT: 같은 파일 내 다른 관련자 진술과 상충
- CROSS_FILE: **서로 다른 파일의 진술이 상충** (가장 중요)

**교차 모순 분석 기준:**
- 동일 사건에 대해 서로 다른 진술자가 다르게 설명하는 부분
- 시간, 장소, 행위, 역할에 대한 설명이 진술자 간 불일치하는 부분
- 한쪽은 인정하고 다른 쪽은 부인하는 사실
- 범행 역할(주도/가담)에 대한 상반된 주장

**규칙:**
- 모순이 없으면 빈 배열 [] 반환
- 명확한 모순만 추출
- CROSS_FILE 모순 시 양쪽 statement_temp_id를 모두 명시

{all_transcripts}

**출력 형식 (JSON 배열만 출력):**
[
  {{
    "statement_temp_id": "ks-A-1",
    "counter_statement_temp_id": "ks-B-2",
    "description": "모순 내용 설명 (2-3문장)",
    "type": "TIME|LOCATION|CONTENT|BEHAVIOR|CROSS_STATEMENT|CROSS_FILE"
  }}
]
"""

    QUESTION_PROMPT = """당신은 수사 전문 분석관입니다.

아래는 전사 내용, 핵심 진술, 모순점입니다.
추가 수사를 위한 **질문 전략**을 생성하십시오.

**규칙:**
- 3~8개 생성
- 각 질문은 특정 핵심 진술과 연결

**전사 내용:**
{transcript}

**핵심 진술:**
{key_statements}

**모순점:**
{contradictions}

**출력 형식 (JSON 배열만 출력):**
[
  {{
    "statement_temp_id": "ks-1",
    "question": "질문 내용"
  }}
]
"""

    CROSS_QUESTION_PROMPT = """당신은 수사 전문 분석관입니다.

아래는 **여러 음성 파일**의 전사 내용, 핵심 진술, 모순점(교차 모순 포함)입니다.
추가 수사를 위한 **질문 전략**을 생성하십시오.

**질문 유형:**
- 파일 내부 모순을 파고드는 질문
- **파일 간 교차 모순을 검증하는 질문** (가장 중요)
- 진술자 A의 주장을 진술자 B에게 확인하는 질문
- 공범 관계, 역할 분담을 명확히 하는 질문
- 알리바이를 교차 검증하는 질문

**규칙:**
- 5~12개 생성
- 각 질문은 특정 핵심 진술과 연결
- 교차 모순 관련 질문은 대상 진술자를 명시

{all_transcripts}

**모순점 (교차 모순 포함):**
{contradictions}

**출력 형식 (JSON 배열만 출력):**
[
  {{
    "statement_temp_id": "ks-A-1",
    "target": "진술자 또는 파일명",
    "question": "질문 내용"
  }}
]
"""

    def __init__(self, client, model: str = "gpt-4o"):
        self.client = client
        self.model = model

    # ----------------------------------------------------------
    # STEP 1: Whisper 전사
    # ----------------------------------------------------------

    def transcribe(self, audio_path: Path) -> str:
        print(f"   🎙️ Whisper 전사 중: {audio_path.name}")
        with open(audio_path, "rb") as audio_file:
            response = self.client.audio.transcriptions.create(
                model="whisper-1", file=audio_file, language="ko", response_format="text"
            )
        transcript = response.strip()
        print(f"   ✅ 전사 완료: {len(transcript)}자")
        return transcript

    # ----------------------------------------------------------
    # STEP 2: 발화자 분리 (diarize)
    # ----------------------------------------------------------

    def diarize(self, raw_transcript: str) -> List[Dict]:
        """GPT-4o로 발화자 분리"""
        print(f"   👥 발화자 분리 중...")

        prompt = self.DIARIZE_PROMPT.format(transcript=raw_transcript)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=4000
        )

        result_text = response.choices[0].message.content.strip()
        result_text = re.sub(r"```json|```", "", result_text).strip()

        try:
            dialogues = json.loads(result_text)
            if not isinstance(dialogues, list):
                dialogues = [dialogues]

            validated = []
            for d in dialogues:
                validated.append({
                    "speaker": str(d.get("speaker", "미상")),
                    "content": str(d.get("content", ""))
                })

            print(f"   ✅ 발화자 분리 완료: {len(validated)}개 발화")

            speakers = {}
            for d in validated:
                s = d["speaker"]
                speakers[s] = speakers.get(s, 0) + 1
            for s, count in speakers.items():
                print(f"      - {s}: {count}회")

            return validated

        except json.JSONDecodeError as e:
            print(f"   ⚠️ 발화자 분리 파싱 실패: {e}")
            return [{"speaker": "미상", "content": raw_transcript}]

    # ----------------------------------------------------------
    # 주요 진술자 식별
    # ----------------------------------------------------------

    def _get_main_speaker(self, dialogues: List[Dict]) -> str:
        """발화자 목록에서 수사관이 아닌 주요 진술자 추출"""
        speakers = {}
        for d in dialogues:
            s = d["speaker"]
            if "수사관" not in s and "조사관" not in s and "경위" not in s:
                speakers[s] = speakers.get(s, 0) + 1

        if speakers:
            return max(speakers, key=speakers.get)
        return "미상"

    # ----------------------------------------------------------
    # STEP 3: 핵심 진술 추출
    # ----------------------------------------------------------

    def extract_key_statements(self, diarized_text: str, prefix: str = "ks", source_label: str = "음성") -> List[Dict]:
        print(f"   🔑 핵심 진술 추출 중... [{source_label}]")
        prompt = self.KEY_STATEMENT_PROMPT.format(
            transcript=diarized_text, prefix=prefix, source_label=source_label
        )
        response = self.client.chat.completions.create(
            model=self.model, messages=[{"role": "user", "content": prompt}],
            temperature=0.2, max_tokens=2000
        )
        result_text = re.sub(r"```json|```", "", response.choices[0].message.content.strip()).strip()
        try:
            statements = json.loads(result_text)
            if not isinstance(statements, list):
                statements = [statements]
            print(f"   ✅ {len(statements)}개 핵심 진술 추출")
            return statements
        except json.JSONDecodeError as e:
            print(f"   ⚠️ 핵심 진술 파싱 실패: {e}")
            return []

    # ----------------------------------------------------------
    # STEP 4: 모순점 분석 (단일)
    # ----------------------------------------------------------

    def find_contradictions(self, diarized_text: str, key_statements: List[Dict]) -> List[Dict]:
        print(f"   ⚠️ 모순점 분석 중...")
        ks_text = json.dumps(key_statements, ensure_ascii=False, indent=2)
        prompt = self.CONTRADICTION_PROMPT.format(transcript=diarized_text, key_statements=ks_text)
        response = self.client.chat.completions.create(
            model=self.model, messages=[{"role": "user", "content": prompt}],
            temperature=0.2, max_tokens=2000
        )
        result_text = re.sub(r"```json|```", "", response.choices[0].message.content.strip()).strip()
        try:
            contradictions = json.loads(result_text)
            if not isinstance(contradictions, list):
                contradictions = [contradictions]
            print(f"   ✅ {len(contradictions)}개 모순점 발견")
            return contradictions
        except json.JSONDecodeError as e:
            print(f"   ⚠️ 모순점 파싱 실패: {e}")
            return []

    # ----------------------------------------------------------
    # STEP 4: 교차 모순 분석 (다수 파일)
    # ----------------------------------------------------------

    def find_cross_contradictions(self, all_sources: List[Dict]) -> List[Dict]:
        print(f"\n   🔀 교차 모순 분석 중... ({len(all_sources)}개 파일)")
        sections = []
        for src in all_sources:
            ks_text = json.dumps(src["key_statements"], ensure_ascii=False, indent=2)
            sections.append(
                f"[파일: {src['label']} / 주요 진술자: {src.get('speaker', '미상')}]\n"
                f"전사 내용:\n{src['diarized_text']}\n\n"
                f"핵심 진술:\n{ks_text}"
            )
        all_transcripts = "\n\n" + "\n\n---\n\n".join(sections)
        prompt = self.CROSS_CONTRADICTION_PROMPT.format(all_transcripts=all_transcripts)
        response = self.client.chat.completions.create(
            model=self.model, messages=[{"role": "user", "content": prompt}],
            temperature=0.2, max_tokens=3000
        )
        result_text = re.sub(r"```json|```", "", response.choices[0].message.content.strip()).strip()
        try:
            contradictions = json.loads(result_text)
            if not isinstance(contradictions, list):
                contradictions = [contradictions]
            print(f"   ✅ 교차 모순 {len(contradictions)}개 발견")
            return contradictions
        except json.JSONDecodeError as e:
            print(f"   ⚠️ 교차 모순 파싱 실패: {e}")
            return []

    # ----------------------------------------------------------
    # STEP 5: 질문 생성 (단일)
    # ----------------------------------------------------------

    def generate_questions(self, diarized_text: str, key_statements: List[Dict], contradictions: List[Dict]) -> List[Dict]:
        print(f"   ❓ 질문 전략 생성 중...")
        ks_text = json.dumps(key_statements, ensure_ascii=False, indent=2)
        ct_text = json.dumps(contradictions, ensure_ascii=False, indent=2)
        prompt = self.QUESTION_PROMPT.format(
            transcript=diarized_text, key_statements=ks_text, contradictions=ct_text
        )
        response = self.client.chat.completions.create(
            model=self.model, messages=[{"role": "user", "content": prompt}],
            temperature=0.3, max_tokens=2000
        )
        result_text = re.sub(r"```json|```", "", response.choices[0].message.content.strip()).strip()
        try:
            questions = json.loads(result_text)
            if not isinstance(questions, list):
                questions = [questions]
            print(f"   ✅ {len(questions)}개 질문 생성")
            return questions
        except json.JSONDecodeError as e:
            print(f"   ⚠️ 질문 파싱 실패: {e}")
            return []

    # ----------------------------------------------------------
    # STEP 5: 교차 질문 생성 (다수 파일)
    # ----------------------------------------------------------

    def generate_cross_questions(self, all_sources: List[Dict], contradictions: List[Dict]) -> List[Dict]:
        print(f"\n   🔀❓ 교차 질문 생성 중...")
        sections = []
        for src in all_sources:
            ks_text = json.dumps(src["key_statements"], ensure_ascii=False, indent=2)
            sections.append(
                f"[파일: {src['label']} / 주요 진술자: {src.get('speaker', '미상')}]\n"
                f"전사 내용:\n{src['diarized_text']}\n\n"
                f"핵심 진술:\n{ks_text}"
            )
        all_transcripts = "\n\n" + "\n\n---\n\n".join(sections)
        ct_text = json.dumps(contradictions, ensure_ascii=False, indent=2)
        prompt = self.CROSS_QUESTION_PROMPT.format(
            all_transcripts=all_transcripts, contradictions=ct_text
        )
        response = self.client.chat.completions.create(
            model=self.model, messages=[{"role": "user", "content": prompt}],
            temperature=0.3, max_tokens=3000
        )
        result_text = re.sub(r"```json|```", "", response.choices[0].message.content.strip()).strip()
        try:
            questions = json.loads(result_text)
            if not isinstance(questions, list):
                questions = [questions]
            print(f"   ✅ 교차 질문 {len(questions)}개 생성")
            return questions
        except json.JSONDecodeError as e:
            print(f"   ⚠️ 교차 질문 파싱 실패: {e}")
            return []

    # ----------------------------------------------------------
    # 전체 파이프라인
    # ----------------------------------------------------------

    def analyze_audio(self, audio_path: Path, previous_sources: List[Dict] = None) -> tuple:
        """
        오디오 전체 분석 파이프라인
        1. Whisper 전사
        2. GPT-4o 발화자 분리
        3. 핵심 진술 추출
        4. 모순점 분석 (단일 또는 교차)
        5. 질문 전략 생성 (단일 또는 교차)
        """
        print(f"\n   📋 오디오 분석 파이프라인 시작")

        file_index = len(previous_sources) if previous_sources else 0
        prefix = f"ks-{chr(65 + file_index)}"
        source_label = audio_path.stem

        # STEP 1: Whisper 전사
        raw_transcript = self.transcribe(audio_path)

        # STEP 2: 발화자 분리
        dialogues = self.diarize(raw_transcript)

        # 주요 진술자 식별
        speaker = self._get_main_speaker(dialogues)
        print(f"   👤 주요 진술자: {speaker}")

        # 발화자 분리된 텍스트 (이후 분석에 사용)
        diarized_text = "\n".join(
            f"[{d['speaker']}] {d['content']}" for d in dialogues
        )

        # STEP 3: 핵심 진술
        key_statements = self.extract_key_statements(diarized_text, prefix=prefix, source_label=source_label)

        current_source = {
            "label": source_label,
            "prefix": prefix,
            "speaker": speaker,
            "transcript": raw_transcript,
            "diarized_text": diarized_text,
            "dialogues": dialogues,
            "key_statements": key_statements
        }

        # STEP 4 & 5: 모순 + 질문
        if previous_sources and len(previous_sources) > 0:
            all_sources = previous_sources + [current_source]
            print(f"\n   🔀 교차 분석 모드: {len(all_sources)}개 파일")
            contradictions = self.find_cross_contradictions(all_sources)
            questions = self.generate_cross_questions(all_sources, contradictions)
        else:
            contradictions = self.find_contradictions(diarized_text, key_statements)
            questions = self.generate_questions(diarized_text, key_statements, contradictions)

        print(f"\n   📊 분석 결과 요약:")
        print(f"      - 주요 진술자: {speaker}")
        print(f"      - 발화: {len(dialogues)}개")
        print(f"      - 핵심 진술: {len(key_statements)}개 (prefix: {prefix})")
        print(f"      - 모순점: {len(contradictions)}개")
        print(f"      - 질문: {len(questions)}개")
        if previous_sources:
            print(f"      - 교차 분석 대상: {len(previous_sources)}개 이전 파일")

        return [
            {
                "stage": "TRANSCRIPT",
                "payload": {
                    "content": dialogues
                }
            },
            {"stage": "KEY_STATEMENT", "payload": key_statements},
            {"stage": "CONTRADICTION", "payload": contradictions},
            {"stage": "QUESTION", "payload": questions}
        ], current_source


# ============================================================
# 기존 함수들 (콜백용)
# ============================================================

def create_analysis_vdo_from_video_events(video_events, investigate_files):
    analysis_vdo_list = []
    events_by_origin = {}
    for video_event in video_events:
        origin = video_event.get("origin_name")
        if origin not in events_by_origin:
            events_by_origin[origin] = []
        for event in video_event.get("payload", []):
            events_by_origin[origin].append({
                "event_id": str(uuid.uuid4()), "analysis_id": video_event.get("analysis_id"),
                "origin_name": origin, "start_time": event.get("start_time", 0.0),
                "end_time": event.get("end_time", 0.0), "event_type": event.get("event_type", "OTHER"),
                "event_description": event.get("event_description", ""), "created_at": video_event.get("created_at")
            })
    for origin_name, events in events_by_origin.items():
        file_id = None
        for rec in investigate_files:
            if rec.get("origin_name") == origin_name:
                file_id = rec["file_id"]
                break
        analysis_vdo_list.append({
            "analysis_id": str(uuid.uuid4()), "file_id": file_id, "file_type": "VIDEO",
            "status": "COMPLETED" if file_id else "PENDING", "result_data": events,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    return analysis_vdo_list


def create_analysis_aud(file_id, dialogue, status="COMPLETED"):
    return {
        "analysis_id": str(uuid.uuid4()), "file_id": file_id, "file_type": "AUDIO",
        "status": status, "payload": {"stage": "TRANSCRIPT", "content": dialogue},
        "created_at": datetime.now(timezone.utc).isoformat()
    }


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def create_analysis_stt(transcript_list, key_statement_list, contradiction_list, question_list):
    analysis_groups = {}
    for t in transcript_list:
        aid = t.get("analysis_id")
        fid = t.get("file_id")
        if not aid:
            continue
        if aid not in analysis_groups:
            analysis_groups[aid] = {
                "file_id": fid, "transcript": [],
                "key_statements": [], "contradictions": [], "questions": []
            }
        analysis_groups[aid]["transcript"] = t.get("payload", {}).get("content", [])
    for ks in key_statement_list:
        aid = ks.get("analysis_id")
        if aid and aid in analysis_groups:
            analysis_groups[aid]["key_statements"].append(ks)
    for cont in contradiction_list:
        aid = cont.get("analysis_id")
        if aid and aid in analysis_groups:
            analysis_groups[aid]["contradictions"].append(cont)
    for q in question_list:
        aid = q.get("analysis_id")
        if aid and aid in analysis_groups:
            analysis_groups[aid]["questions"].append(q)
    result = []
    for aid, data in analysis_groups.items():
        rd = {}
        if data["transcript"]:
            rd["transcript"] = data["transcript"]
        ks_list = [
            {"temp_id": ks.get("payload", {}).get("temp_id", ""), "content": ks.get("payload", {}).get("content", "")}
            for ks in data["key_statements"]
        ]
        if ks_list:
            rd["key_statements"] = ks_list
        ct_list = [
            {"statement_temp_id": c.get("payload", {}).get("statement_temp_id", ""), "type": c.get("payload", {}).get("type", ""), "description": c.get("payload", {}).get("description", "")}
            for c in data["contradictions"]
        ]
        if ct_list:
            rd["contradictions"] = ct_list
        q_list = [
            {"statement_temp_id": q.get("payload", {}).get("statement_temp_id", ""), "question": q.get("payload", {}).get("question", "")}
            for q in data["questions"]
        ]
        if q_list:
            rd["questions"] = q_list
        result.append({
            "analysis_id": aid, "file_id": data["file_id"], "file_type": "AUDIO",
            "status": "COMPLETED", "result_data": rd, "created_at": utc_now_iso()
        })
    return result


# ============================================================
# Analyzer 인스턴스
# ============================================================

video_analyzer = VideoAnalyzer(client=client, model="gpt-4o")
audio_analyzer = AudioAnalyzer(client=client, model="gpt-4o")


# ============================================================
# FastAPI Service
# ============================================================

class AnalysisMediaService:

    _audio_sources: List[Dict] = []

    @staticmethod
    def analyze_media(request: AnalysisMediaRequest):
        print(f"\n🎬 미디어 분석 시작: {request.file_id}")
        print(f"   - file_type: {request.file_type}")
        print(f"   - file_path: {request.file_path}")
        print(f"   - presigned_url: {'있음' if request.presigned_url else '없음'}")

        file_type_lower = request.file_type.lower()
        temp_file = None

        # presigned_url이 있으면 다운로드, 없으면 로컬 경로 사용
        if request.presigned_url:
            from app.utils.file_downloader import download_from_presigned_url
            file_path = download_from_presigned_url(request.presigned_url)
            temp_file = file_path  # 나중에 삭제할 임시 파일
        elif request.file_path:
            file_path = Path(request.file_path)
        else:
            raise ValueError("file_path 또는 presigned_url 중 하나는 필수입니다")

        if not file_path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

        analysis_id = str(uuid.uuid4())

        try:
            if file_type_lower == "video":
                print(f"   🎥 비디오 분석 모드")
                video_event = video_analyzer.analyze_video(file_path)
                result_data = [video_event]

                from app.services.analysis_callback_service import AnalysisCallbackService
                AnalysisCallbackService.register_analysis_result(
                    analysis_id=analysis_id,
                    result_data={
                        "case_id": request.case_id, "analysis_id": analysis_id,
                        "file_id": request.file_id, "file_type": "VIDEO",
                        "origin_name": request.origin_name,
                        "status": "COMPLETED", "result_data": result_data
                    }
                )
                return {"analysis_id": analysis_id, "result_data": result_data}

            elif file_type_lower == "audio":
                print(f"   🎙️ 오디오 분석 모드")

                stages, current_source = audio_analyzer.analyze_audio(
                    file_path,
                    previous_sources=AnalysisMediaService._audio_sources
                )

                AnalysisMediaService._audio_sources.append(current_source)

                from app.services.analysis_callback_service import AnalysisCallbackService
                AnalysisCallbackService.register_analysis_result(
                    analysis_id=analysis_id,
                    result_data={
                        "case_id": request.case_id, "analysis_id": analysis_id,
                        "file_id": request.file_id, "file_type": "AUDIO",
                        "origin_name": request.origin_name,
                        "status": "COMPLETED", "result_data": stages
                    }
                )
                return {"analysis_id": analysis_id, "result_data": stages}

            else:
                raise ValueError(f"지원하지 않는 파일 타입: {request.file_type}")

        finally:
            # 임시 파일 정리
            if temp_file:
                from app.utils.file_downloader import cleanup_temp_file
                cleanup_temp_file(temp_file)

    @staticmethod
    def analyze_video(video_events, investigate_files):
        return create_analysis_vdo_from_video_events(video_events, investigate_files)

    @staticmethod
    def analyze_audio(file_id, dialogue, status="COMPLETED"):
        return create_analysis_aud(file_id, dialogue, status)

    @staticmethod
    def create_stt_analysis(transcript_list, key_statement_list, contradiction_list, question_list):
        return create_analysis_stt(transcript_list, key_statement_list, contradiction_list, question_list)