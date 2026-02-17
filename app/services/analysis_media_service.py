# app/services/analysis_media_service.py
# 영상/음성 분석 엔진 (내부 전용 - investigation_file_service에서 호출)
# ✅ CASE 정보를 활용한 사건 연관 분석 적용
# ✅ temperature 0.0 (객관적 증거 수집)
# ✅ 적응형 프레임 추출 간격 적용
# ✅ ID 체계 통일: 글로벌 연속 번호 (tr-N, ks-N, ct-N, q-N)
# ✅ 무효 ID 참조 필터링
# ✅ description에서 temp_id 참조 자동 제거
# ✅ 콜백 페이로드 ID 체계:
#    TRANSCRIPT    → temp_id: tr-N
#    KEY_STATEMENT → temp_id: ks-N,  transcript_id → tr-N
#    CONTRADICTION → temp_id: ct-N,  statement_id_1 / statement_id_2 → ks-N
#    QUESTION      → temp_id: q-N,   contradiction_id → ct-N

import json
import re
import base64
from pathlib import Path
from typing import List, Dict, Any
from openai import OpenAI

from app.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)


# ============================================================
# 공통: CASE 정보 포맷 헬퍼
# ============================================================

def format_case_info(case_json: dict) -> str:
    """CASE 정보를 프롬프트용 텍스트로 변환"""
    if not case_json:
        return "사건 정보 없음"

    info_parts = []
    if "title" in case_json:
        info_parts.append(f"사건명: {case_json['title']}")
    if "type" in case_json:
        info_parts.append(f"사건 유형: {case_json['type']}")
    if "description" in case_json:
        info_parts.append(f"사건 개요: {case_json['description']}")
    occurred_time = case_json.get('occurred_at', case_json.get('occured_at', ''))
    if occurred_time:
        info_parts.append(f"발생 일시: {occurred_time}")
    if "location" in case_json:
        info_parts.append(f"발생 장소: {case_json['location']}")
    if "summary" in case_json and case_json["summary"]:
        summary = case_json["summary"]
        if isinstance(summary, dict) and any(summary.values()):
            info_parts.append("\n사건 요약:")
            for key, value in summary.items():
                if value:
                    info_parts.append(f"  - {key}: {value}")
    return "\n".join(info_parts)


def _strip_temp_ids(text: str) -> str:
    """description 텍스트에서 temp_id 참조를 제거 (예: (ks-2), ks-10 등)"""
    text = re.sub(r'\(?(?:ks|ct|tr|q)-\d+\)?', '', text)
    text = re.sub(r'\s{2,}', ' ', text).strip()
    text = re.sub(r',\s*,', ',', text)
    text = re.sub(r'\(\s*\)', '', text).strip()
    return text


# ============================================================
# 비디오 프레임 추출 + GPT-4o Vision 분석
# ============================================================

class VideoAnalyzer:
    ANALYSIS_PROMPT = """당신은 CCTV 영상 분석 전문가입니다.

아래에 사건 정보와 영상에서 추출한 프레임들이 제공됩니다.
각 프레임에는 해당 시간(초)이 표시되어 있습니다.

사건 정보를 참고하여, 영상에서 발생하는 주요 이벤트를 감지하고
사건과의 연관성을 포함하여 각 이벤트를 아래 JSON 형식으로 출력하십시오.

[사건 정보]
{case_info}

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
- 사건 정보와 직접적으로 연관되는 부분을 우선 식별
- 추정, 단정 금지
- 최소 1개 이상의 이벤트 감지
- 이벤트가 1개뿐이라도 반드시 JSON 배열로 출력
- 프레임에 보이지 않는 내용을 절대로 생성하지 마십시오
- 사건 정보에 없는 행위나 인물을 추측하여 추가하지 마십시오

**출력 형식 (JSON 배열만 출력):**
[
  {{
    "start_time": 시작시간(초),
    "end_time": 종료시간(초),
    "event_type": "이벤트유형",
    "event_description": "이벤트 설명 (2-3문장, 사건과의 연관성 포함)"
  }}
]
"""

    def __init__(self, client, model: str = "gpt-4o"):
        self.client = client
        self.model = model

    def extract_frames(self, video_path: Path, max_frames: int = 25) -> List[Dict]:
        """
        적응형 프레임 추출
        - ≤15초: 0.5초 간격
        - ≤60초: 1.0초 간격
        - >60초: 1.5초 간격
        - max_frames 초과 시 자동 간격 조정
        """
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

        if duration <= 15:
            interval_sec = 0.5
        elif duration <= 60:
            interval_sec = 1.0
        else:
            interval_sec = 1.5

        if duration / interval_sec > max_frames:
            interval_sec = duration / max_frames

        print(f"   ⏱️ 적응형 간격: {interval_sec:.2f}초 (영상 {duration:.1f}초)")

        frames = []
        current_time = 0.0

        while current_time < duration and len(frames) < max_frames:
            frame_number = int(current_time * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = cap.read()
            if not ret:
                break

            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            b64 = base64.b64encode(buffer).decode('utf-8')

            frames.append({"time_sec": round(current_time, 1), "base64": b64})
            current_time += interval_sec

        cap.release()
        print(f"   📸 {len(frames)}개 프레임 추출 완료 (간격: {interval_sec:.2f}초)")
        return frames

    def analyze_video(self, video_path: Path, case_json: dict = None) -> Dict:
        frames = self.extract_frames(video_path)

        if not frames:
            return {
                "stage": "VIDEO_EVENT",
                "payload": [{"start_time": 0.0, "end_time": 0.0, "event_type": "OTHER", "event_description": "프레임 추출 실패"}],
                "frames": []
            }

        case_info = format_case_info(case_json)

        content = [{"type": "text", "text": self.ANALYSIS_PROMPT.format(case_info=case_info)}]
        for frame in frames:
            content.append({"type": "text", "text": f"[{frame['time_sec']}초]"})
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{frame['base64']}", "detail": "low"}
            })

        print(f"   🤖 GPT-4o Vision 분석 중... (CASE 연관 분석)")

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            temperature=0.0,
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
            return {
                "stage": "VIDEO_EVENT",
                "payload": validated_events,
                "frames": frames
            }

        except (json.JSONDecodeError, Exception) as e:
            print(f"   ⚠️ JSON 파싱 실패: {e}")
            return {
                "stage": "VIDEO_EVENT",
                "payload": [{"start_time": 0.0, "end_time": 0.0, "event_type": "OTHER", "event_description": f"분석 결과 파싱 실패: {result_text[:200]}"}],
                "frames": frames
            }


# ============================================================
# 오디오 전사 + 발화자 분리 + 진술 분석
# ============================================================

class AudioAnalyzer:

    # ──────────────────────────────────────────────
    # STEP 2: 발화자 분리
    # 출력 temp_id = tr-N
    # ──────────────────────────────────────────────

    DIARIZE_PROMPT = """당신은 수사 기록 전문가입니다.

아래는 수사 관련 음성을 전사한 원문입니다.
사건 정보를 참고하여, 이 전사 내용에서 **발화자를 구분**하여 대화 형식으로 재구성하십시오.

[사건 정보]
{case_info}

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
- 각 발화에 temp_id를 순서대로 부여: {tr_prefix}-1, {tr_prefix}-2, ...
- 발화가 1개뿐이라도 반드시 JSON 배열로 출력

**출력 형식 (JSON 배열만 출력):**
[
  {{"temp_id": "{tr_prefix}-1", "speaker": "수사관", "content": "발화 내용"}},
  {{"temp_id": "{tr_prefix}-2", "speaker": "피의자 김루팡", "content": "발화 내용"}}
]

**전사 원문:**
{transcript}
"""

    # ──────────────────────────────────────────────
    # STEP 3: 핵심 진술 추출
    # 출력 temp_id = ks-N (자체 ID)
    # 출력 transcript_id = tr-N (TRANSCRIPT 참조)
    # ──────────────────────────────────────────────

    KEY_STATEMENT_PROMPT = """당신은 수사 전문 분석관입니다.

아래는 수사 관련 음성의 발화자별 전사 내용입니다.
사건 정보를 참고하여, 전사 내용에서 **사건의 핵심이 되는 진술**을 추출하십시오.

[사건 정보]
{case_info}

**핵심 진술 기준:**
- 범행의 실행, 계획, 공모에 직접 관련된 진술
- 범죄 구성요건을 입증하거나 부정하는 진술
- 피의자의 범행 동기, 의도, 인식을 드러내는 진술
- 공범 간 역할 분담, 사전 모의에 관한 진술
- 알리바이 또는 알리바이를 부정하는 진술
- 증거와 관련된 사실 진술
- 사건 정보와 직접적으로 연관되는 진술

**규칙:**
- 3~10개 추출
- temp_id는 {ks_prefix}-1, {ks_prefix}-2, ... 순서대로 부여 (KEY_STATEMENT의 고유 ID)
- transcript_id는 해당 진술에 대응하는 원본 전사(TRANSCRIPT)의 temp_id를 그대로 기입
- statement_text에는 원본 전사 문장을 그대로 복사
- content에는 해당 진술의 수사적 의미/설명을 작성 (사건과의 연관성 포함)
- 단순 인적사항, 절차적 안내는 제외
- 전사 내용에 없는 진술을 절대로 생성하지 마십시오
- 결과가 1개뿐이라도 반드시 JSON 배열로 출력

**전사 내용 [{source_label}]:**
{transcript}

**출력 형식 (JSON 배열만 출력):**
[
  {{
    "temp_id": "{ks_prefix}-1",
    "transcript_id": "원본 전사의 temp_id (예: {tr_prefix}-8)",
    "statement_text": "원본 전사 문장 그대로",
    "content": "이 진술의 수사적 의미/설명"
  }}
]
"""

    # ──────────────────────────────────────────────
    # STEP 4a: 모순 분석 (단일 파일)
    # 출력 temp_id = ct-N (자체 ID)
    # 출력 statement_id_1, statement_id_2 = ks-N (KEY_STATEMENT 참조)
    # ──────────────────────────────────────────────

    CONTRADICTION_PROMPT = """당신은 수사 전문 분석관입니다.

아래는 전사 내용과 추출된 핵심 진술입니다.
사건 정보를 참고하여, 핵심 진술들 간의 **모순점**을 분석하십시오.

[사건 정보]
{case_info}

**모순 유형:**
- TIME: 시간 관련 모순
- LOCATION: 장소 관련 모순
- CONTENT: 내용 관련 모순
- BEHAVIOR: 행동 관련 모순
- CROSS_STATEMENT: 다른 관련자의 진술과 상충

**규칙:**
- 모순이 없으면 빈 배열 [] 반환
- 명확한 모순만 추출
- 진술에 없는 내용을 근거로 모순을 생성하지 마십시오
- 하나의 모순은 하나의 항목으로 생성
- **동일한 주제·논점에 대한 모순은 1개만 생성하십시오. 같은 내용을 다른 표현으로 반복하지 마십시오.**
- temp_id는 {ct_prefix}-1, {ct_prefix}-2, ... 순서대로 부여 (CONTRADICTION의 고유 ID)
- **statement_id_1과 statement_id_2에는 위 핵심 진술 데이터에 있는 temp_id를 정확히 그대로 복사하십시오. 절대로 새로운 ID를 생성하지 마십시오.**
- description에 두 진술이 어떻게 모순되는지 구체적으로 기술. **description에 ks-N, ct-N, tr-N 등 temp_id를 절대 포함하지 마십시오. 진술자 이름과 진술 내용만으로 설명하십시오.**
- 결과가 1개뿐이라도 반드시 JSON 배열로 출력

**전사 내용:**
{transcript}

**핵심 진술:**
{key_statements}

**출력 형식 (JSON 배열만 출력):**
[
  {{
    "temp_id": "{ct_prefix}-1",
    "statement_id_1": "핵심 진술의 실제 temp_id를 그대로 기입",
    "statement_id_2": "핵심 진술의 실제 temp_id를 그대로 기입",
    "description": "두 진술이 모순되는 이유 (temp_id 포함 금지)",
    "type": "모순 유형"
  }}
]
"""

    # ──────────────────────────────────────────────
    # STEP 4b: 교차 모순 분석 (다중 파일)
    # ──────────────────────────────────────────────

    CROSS_CONTRADICTION_PROMPT = """당신은 수사 전문 분석관입니다.

아래는 **여러 음성 파일**의 전사 내용과 핵심 진술입니다.
사건 정보를 참고하여, 각 파일 내부의 모순뿐만 아니라, **파일 간 교차 모순**도 분석하십시오.

[사건 정보]
{case_info}

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
- 하나의 모순은 하나의 항목으로 생성
- 진술에 없는 내용을 근거로 모순을 생성하지 마십시오
- **동일한 주제·논점에 대한 모순은 1개만 생성하십시오. 같은 내용을 다른 표현으로 반복하지 마십시오.**
- temp_id는 {ct_prefix}-1, {ct_prefix}-2, ... 순서대로 부여
- **statement_id_1과 statement_id_2에는 위 핵심 진술 데이터에 있는 temp_id를 정확히 그대로 복사하십시오 (예: ks-3, ks-15 등). 절대로 새로운 ID를 생성하지 마십시오.**
- description에 두 진술이 어떻게 모순되는지 구체적으로 기술. **description에 ks-N, ct-N, tr-N 등 temp_id를 절대 포함하지 마십시오. 진술자 이름과 진술 내용만으로 설명하십시오.**
- 결과가 1개뿐이라도 반드시 JSON 배열로 출력

{all_transcripts}

**출력 형식 (JSON 배열만 출력):**
[
  {{
    "temp_id": "{ct_prefix}-1",
    "statement_id_1": "핵심진술의 실제 temp_id (예: ks-3)",
    "statement_id_2": "핵심진술의 실제 temp_id (예: ks-15)",
    "description": "두 진술이 모순되는 이유 (temp_id 포함 금지)",
    "type": "CROSS_FILE"
  }}
]
"""

    # ──────────────────────────────────────────────
    # STEP 5a: 질문 생성 (단일 파일)
    # 출력 temp_id = q-N (자체 ID)
    # 출력 contradiction_id = ct-N (CONTRADICTION 참조)
    # ──────────────────────────────────────────────

    QUESTION_PROMPT = """당신은 수사 전문 분석관입니다.

아래는 전사 내용, 핵심 진술, 모순점입니다.
사건 정보를 참고하여, 모순점에 대해 추가 수사를 위한 **질문 전략**을 생성하십시오.

[사건 정보]
{case_info}

**규칙:**
- 각 모순(CONTRADICTION)당 질문 1~3개 생성
- temp_id는 {q_prefix}-1, {q_prefix}-2, ... 순서대로 부여 (QUESTION의 고유 ID)
- **contradiction_id에는 위 모순점 데이터에 있는 temp_id를 정확히 그대로 복사하십시오. 절대로 새로운 ID를 생성하지 마십시오.**
- target은 질문 대상자 이름 (모순을 해소하기 위해 질문해야 할 사람)
- rationale에 질문의 근거를 반드시 포함
- 진술 내용에 없는 사실을 근거로 질문을 생성하지 마십시오
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
  {{
    "temp_id": "{q_prefix}-1",
    "contradiction_id": "모순점의 실제 temp_id를 그대로 기입",
    "target": "질문 대상자 이름",
    "question": "질문 내용",
    "rationale": "질문 근거"
  }}
]
"""

    # ──────────────────────────────────────────────
    # STEP 5b: 교차 질문 생성 (다중 파일)
    # ──────────────────────────────────────────────

    CROSS_QUESTION_PROMPT = """당신은 수사 전문 분석관입니다.

아래는 **여러 음성 파일**의 전사 내용, 핵심 진술, 모순점(교차 모순 포함)입니다.
사건 정보를 참고하여, 추가 수사를 위한 **질문 전략**을 생성하십시오.

[사건 정보]
{case_info}

**질문 유형:**
- 파일 내부 모순을 파고드는 질문
- **파일 간 교차 모순을 검증하는 질문** (가장 중요)
- 진술자 A의 주장을 진술자 B에게 확인하는 질문

**규칙:**
- 각 모순(CONTRADICTION)당 질문 1~3개 생성
- temp_id는 {q_prefix}-1, {q_prefix}-2, ... 순서대로 부여
- **contradiction_id에는 위 모순점 데이터에 있는 temp_id를 정확히 그대로 복사하십시오. 절대로 새로운 ID를 생성하지 마십시오.**
- target은 질문 대상자 이름
- rationale에 질문의 근거를 반드시 포함
- 진술 내용에 없는 사실을 근거로 질문을 생성하지 마십시오
- 결과가 1개뿐이라도 반드시 JSON 배열로 출력

{all_transcripts}

**모순점:**
{contradictions}

**출력 형식 (JSON 배열만 출력):**
[
  {{
    "temp_id": "{q_prefix}-1",
    "contradiction_id": "모순점의 실제 temp_id",
    "target": "질문 대상자 이름",
    "question": "질문 내용",
    "rationale": "질문 근거"
  }}
]
"""

    def __init__(self, client, model: str = "gpt-4o"):
        self.client = client
        self.model = model

    def _call_gpt(self, prompt: str, max_tokens: int = 4000, temperature: float = 0.0) -> str:
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

    # STEP 2: 발화자 분리 → temp_id: tr-N
    def diarize(self, raw_transcript: str, tr_prefix: str = "tr", case_json: dict = None) -> List[Dict]:
        print(f"   👥 발화자 분리 중...")
        case_info = format_case_info(case_json)
        prompt = self.DIARIZE_PROMPT.format(
            transcript=raw_transcript,
            tr_prefix=tr_prefix,
            case_info=case_info
        )
        result_text = self._call_gpt(prompt)
        try:
            dialogues = self._parse_json(result_text)
            validated = []
            for i, d in enumerate(dialogues, 1):
                validated.append({
                    "temp_id": str(d.get("temp_id", f"{tr_prefix}-{i}")),
                    "speaker": str(d.get("speaker", "미상")),
                    "content": str(d.get("content", ""))
                })
            print(f"   ✅ 발화자 분리 완료: {len(validated)}개 발화")
            return validated
        except json.JSONDecodeError as e:
            print(f"   ⚠️ 발화자 분리 파싱 실패: {e}")
            return [{"temp_id": f"{tr_prefix}-1", "speaker": "미상", "content": raw_transcript}]

    # 주요 진술자 식별
    def _get_main_speaker(self, dialogues: List[Dict]) -> str:
        speakers = {}
        for d in dialogues:
            s = d["speaker"]
            if "수사관" not in s and "조사관" not in s and "경위" not in s:
                speakers[s] = speakers.get(s, 0) + 1
        return max(speakers, key=speakers.get) if speakers else "미상"

    # STEP 3: 핵심 진술 추출 → temp_id: ks-N, transcript_id: tr-N
    def extract_key_statements(
        self,
        diarized_text: str,
        transcript_items: List[Dict],
        source_label: str = "음성",
        case_json: dict = None,
        ks_prefix: str = "ks",
        tr_prefix: str = "tr"
    ) -> List[Dict]:
        print(f"   🔑 핵심 진술 추출 중... [{source_label}] (CASE 연관 분석)")

        case_info = format_case_info(case_json)

        transcript_with_ids = "\n".join(
            f"[{item['temp_id']}] [{item['speaker']}] {item['content']}"
            for item in transcript_items
        )

        prompt = self.KEY_STATEMENT_PROMPT.format(
            transcript=transcript_with_ids,
            source_label=source_label,
            case_info=case_info,
            ks_prefix=ks_prefix,
            tr_prefix=tr_prefix
        )
        try:
            results = self._parse_json(self._call_gpt(prompt, max_tokens=2000))
            validated = []
            for i, item in enumerate(results, 1):
                validated.append({
                    "temp_id": str(item.get("temp_id", f"{ks_prefix}-{i}")),
                    "transcript_id": str(item.get("transcript_id", "")),
                    "statement_text": str(item.get("statement_text", "")),
                    "content": str(item.get("content", ""))
                })
            print(f"   ✅ 핵심 진술 추출 완료: {len(validated)}개")
            return validated
        except json.JSONDecodeError as e:
            print(f"   ⚠️ 핵심 진술 파싱 실패: {e}")
            return []

    # STEP 4a: 모순 분석 (단일) → temp_id: ct-N, statement_id_1/2: ks-N
    def find_contradictions(
        self,
        diarized_text: str,
        key_statements: List[Dict],
        case_json: dict = None,
        ct_prefix: str = "ct"
    ) -> List[Dict]:
        print(f"   ⚠️ 모순점 분석 중... (CASE 연관 분석)")
        case_info = format_case_info(case_json)
        ks_text = json.dumps(key_statements, ensure_ascii=False, indent=2)
        prompt = self.CONTRADICTION_PROMPT.format(
            transcript=diarized_text,
            key_statements=ks_text,
            case_info=case_info,
            ct_prefix=ct_prefix
        )
        try:
            results = self._parse_json(self._call_gpt(prompt, max_tokens=2000))
            validated = []
            for i, item in enumerate(results, 1):
                validated.append({
                    "temp_id": str(item.get("temp_id", f"{ct_prefix}-{i}")),
                    "statement_id_1": str(item.get("statement_id_1", "")),
                    "statement_id_2": str(item.get("statement_id_2", "")),
                    "description": _strip_temp_ids(str(item.get("description", ""))),
                    "type": str(item.get("type", "CONTENT"))
                })
            print(f"   ✅ 모순점 분석 완료: {len(validated)}개")
            return validated
        except json.JSONDecodeError:
            return []

    # STEP 4b: 교차 모순 분석
    def find_cross_contradictions(
        self,
        all_sources: List[Dict],
        case_json: dict = None,
        ct_prefix: str = "ct"
    ) -> List[Dict]:
        print(f"\n   🔀 교차 모순 분석 중... ({len(all_sources)}개 파일, CASE 연관 분석)")
        case_info = format_case_info(case_json)
        sections = []
        for src in all_sources:
            ks_text = json.dumps(src["key_statements"], ensure_ascii=False, indent=2)
            sections.append(
                f"[파일: {src['label']} / 주요 진술자: {src.get('speaker', '미상')}]\n"
                f"전사 내용:\n{src['diarized_text']}\n\n핵심 진술:\n{ks_text}"
            )
        all_transcripts = "\n\n---\n\n".join(sections)
        prompt = self.CROSS_CONTRADICTION_PROMPT.format(
            all_transcripts=all_transcripts,
            case_info=case_info,
            ct_prefix=ct_prefix
        )
        try:
            results = self._parse_json(self._call_gpt(prompt, max_tokens=3000))
            validated = []
            for i, item in enumerate(results, 1):
                validated.append({
                    "temp_id": str(item.get("temp_id", f"{ct_prefix}-{i}")),
                    "statement_id_1": str(item.get("statement_id_1", "")),
                    "statement_id_2": str(item.get("statement_id_2", "")),
                    "description": _strip_temp_ids(str(item.get("description", ""))),
                    "type": str(item.get("type", "CROSS_FILE"))
                })
            return validated
        except json.JSONDecodeError:
            return []

    # STEP 5a: 질문 생성 (단일) → temp_id: q-N, contradiction_id: ct-N
    def generate_questions(
        self,
        diarized_text: str,
        key_statements: List[Dict],
        contradictions: List[Dict],
        case_json: dict = None,
        q_prefix: str = "q"
    ) -> List[Dict]:
        print(f"   ❓ 질문 전략 생성 중... (CASE 연관 분석)")
        case_info = format_case_info(case_json)
        prompt = self.QUESTION_PROMPT.format(
            transcript=diarized_text,
            key_statements=json.dumps(key_statements, ensure_ascii=False, indent=2),
            contradictions=json.dumps(contradictions, ensure_ascii=False, indent=2),
            case_info=case_info,
            q_prefix=q_prefix
        )
        try:
            results = self._parse_json(self._call_gpt(prompt, max_tokens=2000, temperature=0.0))
            validated = []
            for i, item in enumerate(results, 1):
                validated.append({
                    "temp_id": str(item.get("temp_id", f"{q_prefix}-{i}")),
                    "contradiction_id": str(item.get("contradiction_id", "")),
                    "target": str(item.get("target", "")),
                    "question": str(item.get("question", "")),
                    "rationale": str(item.get("rationale", ""))
                })
            return validated
        except json.JSONDecodeError:
            return []

    # STEP 5b: 교차 질문 생성
    def generate_cross_questions(
        self,
        all_sources: List[Dict],
        contradictions: List[Dict],
        case_json: dict = None,
        q_prefix: str = "q"
    ) -> List[Dict]:
        print(f"\n   🔀❓ 교차 질문 생성 중... (CASE 연관 분석)")
        case_info = format_case_info(case_json)
        sections = []
        for src in all_sources:
            ks_text = json.dumps(src["key_statements"], ensure_ascii=False, indent=2)
            sections.append(
                f"[파일: {src['label']} / 주요 진술자: {src.get('speaker', '미상')}]\n"
                f"전사 내용:\n{src['diarized_text']}\n\n핵심 진술:\n{ks_text}"
            )
        prompt = self.CROSS_QUESTION_PROMPT.format(
            all_transcripts="\n\n---\n\n".join(sections),
            contradictions=json.dumps(contradictions, ensure_ascii=False, indent=2),
            case_info=case_info,
            q_prefix=q_prefix
        )
        try:
            results = self._parse_json(self._call_gpt(prompt, max_tokens=3000, temperature=0.0))
            validated = []
            for i, item in enumerate(results, 1):
                validated.append({
                    "temp_id": str(item.get("temp_id", f"{q_prefix}-{i}")),
                    "contradiction_id": str(item.get("contradiction_id", "")),
                    "target": str(item.get("target", "")),
                    "question": str(item.get("question", "")),
                    "rationale": str(item.get("rationale", ""))
                })
            return validated
        except json.JSONDecodeError:
            return []

    # ──────────────────────────────────────────────
    # 전체 파이프라인
    # ──────────────────────────────────────────────

    def analyze_audio(self, audio_path: Path, previous_sources: List[Dict] = None, case_json: dict = None) -> tuple:
        """
        오디오 분석 파이프라인
        - ID 체계: 모든 파일에서 tr-N, ks-N, ct-N, q-N 통일 (글로벌 연속 번호)
        """
        print(f"\n   📋 오디오 분석 파이프라인 시작 (CASE 연관 분석)")

        # ── 글로벌 오프셋 계산 (파일 간 연속 번호) ──
        tr_offset = 0
        ks_offset = 0
        if previous_sources:
            for src in previous_sources:
                tr_offset += len(src.get("dialogues", []))
                ks_offset += len(src.get("key_statements", []))

        # ── 통일된 prefix (파일 구분 접미사 없음) ──
        tr_prefix = "tr"
        ks_prefix = "ks"
        ct_prefix = "ct"
        q_prefix = "q"

        source_label = audio_path.stem

        # 1. 전사
        raw_transcript = self.transcribe(audio_path)

        # 2. 발화자 분리 (GPT는 tr-1, tr-2, ... 로컬 ID 반환)
        dialogues = self.diarize(raw_transcript, tr_prefix=tr_prefix, case_json=case_json)

        # 3. 전사 ID → 글로벌 리매핑 (tr-1 → tr-{offset+1})
        tr_id_map = {}
        for i, d in enumerate(dialogues, 1):
            old_id = d["temp_id"]
            new_id = f"tr-{tr_offset + i}"
            tr_id_map[old_id] = new_id
            d["temp_id"] = new_id

        speaker = self._get_main_speaker(dialogues)
        print(f"   👤 주요 진술자: {speaker}")

        # 4. 글로벌 ID 반영된 diarized_text 생성
        diarized_text = "\n".join(
            f"[{d['temp_id']}] [{d['speaker']}] {d['content']}"
            for d in dialogues
        )

        # 5. 핵심 진술 추출 (GPT는 ks-1, ks-2... 로컬 ID 반환)
        key_statements = self.extract_key_statements(
            diarized_text, transcript_items=dialogues, source_label=source_label,
            case_json=case_json, ks_prefix=ks_prefix, tr_prefix=tr_prefix
        )

        # 6. 핵심 진술 ID → 글로벌 리매핑 (ks-1 → ks-{offset+1})
        for i, ks in enumerate(key_statements, 1):
            ks["temp_id"] = f"ks-{ks_offset + i}"
            old_tr = ks.get("transcript_id", "")
            if old_tr in tr_id_map:
                ks["transcript_id"] = tr_id_map[old_tr]

        # 7. 유효한 ks ID 집합 수집 (이전 파일 + 현재 파일)
        all_valid_ks_ids = set()
        if previous_sources:
            for src in previous_sources:
                for ks in src.get("key_statements", []):
                    all_valid_ks_ids.add(ks["temp_id"])
        for ks in key_statements:
            all_valid_ks_ids.add(ks["temp_id"])

        current_source = {
            "label": source_label, "tr_prefix": tr_prefix,
            "ks_prefix": ks_prefix, "ct_prefix": ct_prefix,
            "q_prefix": q_prefix, "speaker": speaker,
            "transcript": raw_transcript, "diarized_text": diarized_text,
            "dialogues": dialogues, "key_statements": key_statements
        }

        if previous_sources and len(previous_sources) > 0:
            all_sources = previous_sources + [current_source]
            contradictions = self.find_cross_contradictions(
                all_sources, case_json=case_json, ct_prefix=ct_prefix
            )
            questions = self.generate_cross_questions(
                all_sources, contradictions, case_json=case_json, q_prefix=q_prefix
            )
        else:
            contradictions = self.find_contradictions(
                diarized_text, key_statements, case_json=case_json, ct_prefix=ct_prefix
            )
            questions = self.generate_questions(
                diarized_text, key_statements, contradictions,
                case_json=case_json, q_prefix=q_prefix
            )

        # 8. 무효 ID 참조 필터링 (CONTRADICTION)
        valid_contradictions = []
        valid_ct_ids = set()
        for c in contradictions:
            s1 = c.get("statement_id_1", "")
            s2 = c.get("statement_id_2", "")
            if s1 in all_valid_ks_ids and s2 in all_valid_ks_ids:
                valid_contradictions.append(c)
                valid_ct_ids.add(c.get("temp_id", ""))
            else:
                print(f"   ⚠️ 무효 ID 참조 필터링: statement_id_1={s1}, statement_id_2={s2}")
        contradictions = valid_contradictions

        # 9. 무효 ID 참조 필터링 (QUESTION)
        valid_questions = []
        for q in questions:
            ct_ref = q.get("contradiction_id", "")
            if ct_ref in valid_ct_ids:
                valid_questions.append(q)
            else:
                print(f"   ⚠️ 무효 모순 참조 필터링: contradiction_id={ct_ref}")
        questions = valid_questions

        print(f"\n   📊 분석 결과: 발화 {len(dialogues)}개 / 핵심진술 {len(key_statements)}개 / 모순 {len(contradictions)}개 / 질문 {len(questions)}개")

        stages = [
            {"stage": "TRANSCRIPT", "payload": dialogues},
            {"stage": "KEY_STATEMENT", "payload": key_statements},
            {"stage": "CONTRADICTION", "payload": contradictions},
            {"stage": "QUESTION", "payload": questions}
        ]

        return stages, current_source


# ============================================================
# Analyzer 인스턴스
# ============================================================

video_analyzer = VideoAnalyzer(client=client, model="gpt-4.1")
audio_analyzer = AudioAnalyzer(client=client, model="gpt-4.1")


# ============================================================
# 오디오 교차분석용 상태 저장
# ============================================================

class AnalysisMediaService:
    _audio_sources: List[Dict] = []