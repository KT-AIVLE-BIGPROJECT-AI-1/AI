# app/services/analysis_media_service.py
# 영상/음성 분석 엔진 (내부 전용 - investigation_file_service에서 호출)
# TRANSCRIPT → KEY_STATEMENT → CONTRADICTION → QUESTION 연결 구조 반영

import json
import re
import base64
from pathlib import Path
from typing import List, Dict, Any
from openai import OpenAI

from app.config import settings

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
- 이벤트가 1개뿐이라도 반드시 JSON 배열로 출력

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
            raise ImportError("opencv-python이 설치되어 있지 않습니다.")

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

            frames.append({"time_sec": round(current_time, 1), "base64": b64})
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
- 질문하는 사람 → "수사관"
- 답변하는 사람 → 실제 이름이 언급되면 "피의자 홍길동" 형식, 없으면 "피의자" / "참고인" / "피해자" / "목격자"
- 첫 부분의 조사 시작 안내, 인적사항 고지 등 → "수사관"
- "네", "맞습니다", "아닙니다" 등 짧은 답변 → 직전 질문에 대한 답변자
- 반박, 부정, 해명 → 피의자/참고인

**규칙:**
- 모든 발화를 빠짐없이 포함할 것
- 원문의 내용을 변경하거나 생략하지 말 것
- 발화 순서를 반드시 유지할 것
- 각 발화에 temp_id를 순서대로 부여: {prefix}-1, {prefix}-2, ...
- 발화가 1개뿐이라도 반드시 JSON 배열로 출력

**출력 형식 (JSON 배열만 출력):**
[
  {{"temp_id": "{prefix}-1", "speaker": "수사관", "content": "발화 내용"}},
  {{"temp_id": "{prefix}-2", "speaker": "피의자 김루팡", "content": "발화 내용"}}
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
- 각 핵심 진술의 temp_id는 반드시 원본 전사(TRANSCRIPT)의 temp_id를 그대로 사용
- statement_text에는 원본 전사 문장을 그대로 복사
- content에는 해당 진술의 수사적 의미/설명을 작성
- 단순 인적사항, 절차적 안내는 제외
- 결과가 1개뿐이라도 반드시 JSON 배열로 출력

**전사 내용 [{source_label}]:**
{transcript}

**출력 형식 (JSON 배열만 출력):**
[
  {{
    "temp_id": "전사의 temp_id를 그대로 사용",
    "statement_text": "원본 전사 문장 그대로",
    "content": "이 진술의 수사적 의미/설명"
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
- 모순은 반드시 **쌍**으로 생성: A와 B가 모순이면 A 기준 1개, B 기준 1개 → 총 2개
- 각 항목의 temp_id는 핵심 진술의 temp_id를 사용
- description 끝에 반드시 상대 temp_id를 "(temp_id : xx)" 형식으로 포함
- 결과가 1쌍(2개)뿐이라도 반드시 JSON 배열로 출력

**전사 내용:**
{transcript}

**핵심 진술:**
{key_statements}

**출력 형식 (JSON 배열만 출력):**
[
  {{"temp_id": "tr-1", "description": "진술자 A는 ...라고 주장하나 진술자 B는 ...라고 진술하여 모순됨 (temp_id : tr-3)", "type": "CROSS_STATEMENT"}},
  {{"temp_id": "tr-3", "description": "진술자 B는 ...라고 진술하나 진술자 A는 ...라고 주장하여 모순됨 (temp_id : tr-1)", "type": "CROSS_STATEMENT"}}
]
"""

    CROSS_CONTRADICTION_PROMPT = """당신은 수사 전문 분석관입니다.

아래는 **여러 음성 파일**의 전사 내용과 핵심 진술입니다.
각 파일 내부의 모순뿐만 아니라, **파일 간 교차 모순**도 분석하십시오.

**모순 유형:**
- TIME / LOCATION / CONTENT / BEHAVIOR / CROSS_STATEMENT
- CROSS_FILE: **서로 다른 파일의 진술이 상충** (가장 중요)

**교차 모순 분석 기준:**
- 동일 사건에 대해 서로 다른 진술자가 다르게 설명하는 부분
- 시간, 장소, 행위, 역할에 대한 설명이 진술자 간 불일치하는 부분
- 한쪽은 인정하고 다른 쪽은 부인하는 사실
- 범행 역할(주도/가담)에 대한 상반된 주장

**규칙:**
- 모순이 없으면 빈 배열 [] 반환
- 모순은 반드시 **쌍**으로 생성: A와 B가 모순이면 A 기준 1개, B 기준 1개 → 총 2개
- 각 항목의 temp_id는 핵심 진술의 temp_id를 사용
- description 끝에 반드시 상대 temp_id를 "(temp_id : xx)" 형식으로 포함
- 결과가 1쌍(2개)뿐이라도 반드시 JSON 배열로 출력

{all_transcripts}

**출력 형식 (JSON 배열만 출력):**
[
  {{"temp_id": "ks-A-1", "description": "진술자 A는 ...라고 주장하나 진술자 B는 ...라고 진술하여 모순됨 (temp_id : ks-B-2)", "type": "CROSS_FILE"}},
  {{"temp_id": "ks-B-2", "description": "진술자 B는 ...라고 진술하나 진술자 A는 ...라고 주장하여 모순됨 (temp_id : ks-A-1)", "type": "CROSS_FILE"}}
]
"""

    QUESTION_PROMPT = """당신은 수사 전문 분석관입니다.

아래는 전사 내용, 핵심 진술, 모순점입니다.
모순점에 대해 추가 수사를 위한 **질문 전략**을 생성하십시오.

**규칙:**
- 모순이 있는 temp_id당 질문 3개씩 생성
- temp_id는 모순점(CONTRADICTION)의 temp_id를 사용
- target은 해당 temp_id의 발화자가 **아닌** 상대방으로 지정
- rationale에 질문의 근거를 반드시 포함
- 모순이 없으면 빈 배열 [] 반환
- 결과가 1개뿐이라도 반드시 JSON 배열로 출력

**전사 내용:**
{transcript}

**핵심 진술:**
{key_statements}

**모순점:**
{contradictions}

**출력 형식 (JSON 배열만 출력):**
[
  {{"temp_id": "tr-1", "target": "상대방 이름", "question": "질문 내용", "rationale": "질문 근거"}}
]
"""

    CROSS_QUESTION_PROMPT = """당신은 수사 전문 분석관입니다.

아래는 **여러 음성 파일**의 전사 내용, 핵심 진술, 모순점(교차 모순 포함)입니다.
추가 수사를 위한 **질문 전략**을 생성하십시오.

**질문 유형:**
- 파일 내부 모순을 파고드는 질문
- **파일 간 교차 모순을 검증하는 질문** (가장 중요)
- 진술자 A의 주장을 진술자 B에게 확인하는 질문

**규칙:**
- 모순이 있는 temp_id당 질문 3개씩 생성
- temp_id는 모순점(CONTRADICTION)의 temp_id를 사용
- target은 해당 temp_id의 발화자가 **아닌** 상대방으로 지정
- rationale에 질문의 근거를 반드시 포함
- 결과가 1개뿐이라도 반드시 JSON 배열로 출력

{all_transcripts}

**모순점:**
{contradictions}

**출력 형식 (JSON 배열만 출력):**
[
  {{"temp_id": "ks-A-1", "target": "상대방 이름", "question": "질문 내용", "rationale": "질문 근거"}}
]
"""

    def __init__(self, client, model: str = "gpt-4o"):
        self.client = client
        self.model = model

    def _call_gpt(self, prompt: str, max_tokens: int = 4000, temperature: float = 0.2) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content.strip()

    def _parse_json(self, text: str) -> Any:
        """JSON 파싱 + 항상 list 반환 보장"""
        text = re.sub(r"```json|```", "", text).strip()
        result = json.loads(text)
        if not isinstance(result, list):
            result = [result]
        return result

    # STEP 1: Whisper 전사
    def transcribe(self, audio_path: Path) -> str:
        print(f"   🎙️ Whisper 전사 중: {audio_path.name}")
        with open(audio_path, "rb") as f:
            response = self.client.audio.transcriptions.create(
                model="whisper-1", file=f, language="ko", response_format="text"
            )
        transcript = response.strip()
        print(f"   ✅ 전사 완료: {len(transcript)}자")
        return transcript

    # STEP 2: 발화자 분리 (temp_id 포함)
    def diarize(self, raw_transcript: str, prefix: str = "tr") -> List[Dict]:
        print(f"   👥 발화자 분리 중...")
        prompt = self.DIARIZE_PROMPT.format(transcript=raw_transcript, prefix=prefix)
        result_text = self._call_gpt(prompt)
        try:
            dialogues = self._parse_json(result_text)
            validated = []
            for i, d in enumerate(dialogues, 1):
                validated.append({
                    "temp_id": str(d.get("temp_id", f"{prefix}-{i}")),
                    "speaker": str(d.get("speaker", "미상")),
                    "content": str(d.get("content", ""))
                })
            print(f"   ✅ 발화자 분리 완료: {len(validated)}개 발화")
            return validated
        except json.JSONDecodeError as e:
            print(f"   ⚠️ 발화자 분리 파싱 실패: {e}")
            return [{"temp_id": f"{prefix}-1", "speaker": "미상", "content": raw_transcript}]

    # 주요 진술자 식별
    def _get_main_speaker(self, dialogues: List[Dict]) -> str:
        speakers = {}
        for d in dialogues:
            s = d["speaker"]
            if "수사관" not in s and "조사관" not in s and "경위" not in s:
                speakers[s] = speakers.get(s, 0) + 1
        return max(speakers, key=speakers.get) if speakers else "미상"

    # STEP 3: 핵심 진술 추출
    def extract_key_statements(self, diarized_text: str, transcript_items: List[Dict], source_label: str = "음성") -> List[Dict]:
        """
        핵심 진술 추출
        - temp_id는 TRANSCRIPT의 temp_id를 그대로 사용
        - statement_text에 원본 전사 문장 포함
        """
        print(f"   🔑 핵심 진술 추출 중... [{source_label}]")

        # 전사 내용에 temp_id 정보를 포함하여 프롬프트 생성
        transcript_with_ids = "\n".join(
            f"[{item['temp_id']}] [{item['speaker']}] {item['content']}"
            for item in transcript_items
        )

        prompt = self.KEY_STATEMENT_PROMPT.format(
            transcript=transcript_with_ids,
            source_label=source_label
        )
        try:
            results = self._parse_json(self._call_gpt(prompt, max_tokens=2000))
            # 유효성 검증: 필수 필드 보장
            validated = []
            for item in results:
                validated.append({
                    "temp_id": str(item.get("temp_id", "")),
                    "statement_text": str(item.get("statement_text", "")),
                    "content": str(item.get("content", ""))
                })
            return validated
        except json.JSONDecodeError as e:
            print(f"   ⚠️ 핵심 진술 파싱 실패: {e}")
            return []

    # STEP 4a: 모순 분석 (단일)
    def find_contradictions(self, diarized_text: str, key_statements: List[Dict]) -> List[Dict]:
        print(f"   ⚠️ 모순점 분석 중...")
        ks_text = json.dumps(key_statements, ensure_ascii=False, indent=2)
        prompt = self.CONTRADICTION_PROMPT.format(transcript=diarized_text, key_statements=ks_text)
        try:
            results = self._parse_json(self._call_gpt(prompt, max_tokens=2000))
            # 유효성 검증
            validated = []
            for item in results:
                validated.append({
                    "temp_id": str(item.get("temp_id", "")),
                    "description": str(item.get("description", "")),
                    "type": str(item.get("type", "CONTENT"))
                })
            return validated
        except json.JSONDecodeError:
            return []

    # STEP 4b: 교차 모순 분석
    def find_cross_contradictions(self, all_sources: List[Dict]) -> List[Dict]:
        print(f"\n   🔀 교차 모순 분석 중... ({len(all_sources)}개 파일)")
        sections = []
        for src in all_sources:
            ks_text = json.dumps(src["key_statements"], ensure_ascii=False, indent=2)
            sections.append(
                f"[파일: {src['label']} / 주요 진술자: {src.get('speaker', '미상')}]\n"
                f"전사 내용:\n{src['diarized_text']}\n\n핵심 진술:\n{ks_text}"
            )
        all_transcripts = "\n\n---\n\n".join(sections)
        prompt = self.CROSS_CONTRADICTION_PROMPT.format(all_transcripts=all_transcripts)
        try:
            results = self._parse_json(self._call_gpt(prompt, max_tokens=3000))
            validated = []
            for item in results:
                validated.append({
                    "temp_id": str(item.get("temp_id", "")),
                    "description": str(item.get("description", "")),
                    "type": str(item.get("type", "CROSS_FILE"))
                })
            return validated
        except json.JSONDecodeError:
            return []

    # STEP 5a: 질문 생성 (단일)
    def generate_questions(self, diarized_text: str, key_statements: List[Dict], contradictions: List[Dict]) -> List[Dict]:
        print(f"   ❓ 질문 전략 생성 중...")
        prompt = self.QUESTION_PROMPT.format(
            transcript=diarized_text,
            key_statements=json.dumps(key_statements, ensure_ascii=False, indent=2),
            contradictions=json.dumps(contradictions, ensure_ascii=False, indent=2)
        )
        try:
            results = self._parse_json(self._call_gpt(prompt, max_tokens=2000, temperature=0.3))
            validated = []
            for item in results:
                validated.append({
                    "temp_id": str(item.get("temp_id", "")),
                    "target": str(item.get("target", "")),
                    "question": str(item.get("question", "")),
                    "rationale": str(item.get("rationale", ""))
                })
            return validated
        except json.JSONDecodeError:
            return []

    # STEP 5b: 교차 질문 생성
    def generate_cross_questions(self, all_sources: List[Dict], contradictions: List[Dict]) -> List[Dict]:
        print(f"\n   🔀❓ 교차 질문 생성 중...")
        sections = []
        for src in all_sources:
            ks_text = json.dumps(src["key_statements"], ensure_ascii=False, indent=2)
            sections.append(
                f"[파일: {src['label']} / 주요 진술자: {src.get('speaker', '미상')}]\n"
                f"전사 내용:\n{src['diarized_text']}\n\n핵심 진술:\n{ks_text}"
            )
        prompt = self.CROSS_QUESTION_PROMPT.format(
            all_transcripts="\n\n---\n\n".join(sections),
            contradictions=json.dumps(contradictions, ensure_ascii=False, indent=2)
        )
        try:
            results = self._parse_json(self._call_gpt(prompt, max_tokens=3000, temperature=0.3))
            validated = []
            for item in results:
                validated.append({
                    "temp_id": str(item.get("temp_id", "")),
                    "target": str(item.get("target", "")),
                    "question": str(item.get("question", "")),
                    "rationale": str(item.get("rationale", ""))
                })
            return validated
        except json.JSONDecodeError:
            return []

    # 전체 파이프라인
    def analyze_audio(self, audio_path: Path, previous_sources: List[Dict] = None) -> tuple:
        print(f"\n   📋 오디오 분석 파이프라인 시작")

        file_index = len(previous_sources) if previous_sources else 0
        prefix = f"ks-{chr(65 + file_index)}"
        source_label = audio_path.stem

        raw_transcript = self.transcribe(audio_path)
        dialogues = self.diarize(raw_transcript, prefix=prefix)
        speaker = self._get_main_speaker(dialogues)
        print(f"   👤 주요 진술자: {speaker}")

        # temp_id 포함된 전사 텍스트 생성
        diarized_text = "\n".join(
            f"[{d['temp_id']}] [{d['speaker']}] {d['content']}"
            for d in dialogues
        )

        key_statements = self.extract_key_statements(
            diarized_text, transcript_items=dialogues, source_label=source_label
        )

        current_source = {
            "label": source_label, "prefix": prefix, "speaker": speaker,
            "transcript": raw_transcript, "diarized_text": diarized_text,
            "dialogues": dialogues, "key_statements": key_statements
        }

        if previous_sources and len(previous_sources) > 0:
            all_sources = previous_sources + [current_source]
            contradictions = self.find_cross_contradictions(all_sources)
            questions = self.generate_cross_questions(all_sources, contradictions)
        else:
            contradictions = self.find_contradictions(diarized_text, key_statements)
            questions = self.generate_questions(diarized_text, key_statements, contradictions)

        print(f"\n   📊 분석 결과: 발화 {len(dialogues)}개 / 핵심진술 {len(key_statements)}개 / 모순 {len(contradictions)}개 / 질문 {len(questions)}개")

        # ✅ TRANSCRIPT payload: 직접 list (content 감싸기 제거)
        stages = [
            {"stage": "TRANSCRIPT", "payload": dialogues},
            {"stage": "KEY_STATEMENT", "payload": key_statements},
            {"stage": "CONTRADICTION", "payload": contradictions},
            {"stage": "QUESTION", "payload": questions}
        ]

        return stages, current_source


# ============================================================
# Analyzer 인스턴스 (investigation_file_service에서 import하여 사용)
# ============================================================

video_analyzer = VideoAnalyzer(client=client, model="gpt-4o")
audio_analyzer = AudioAnalyzer(client=client, model="gpt-4o")


# ============================================================
# 오디오 교차분석용 상태 저장
# ============================================================

class AnalysisMediaService:
    _audio_sources: List[Dict] = []
