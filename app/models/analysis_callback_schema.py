# app/models/analysis_callback_schema.py
# TRANSCRIPT → KEY_STATEMENT → CONTRADICTION → QUESTION 연결 구조 반영

from pydantic import BaseModel, Field
from typing import List, Optional, Union, Any


# ============================================================
# Payload 스키마
# ============================================================

class SummaryPayload(BaseModel):
    summary: str
    confidence: float
    keywords: List[str]


class TranscriptItem(BaseModel):
    temp_id: str
    speaker: str
    content: str


class KeyStatement(BaseModel):
    temp_id: str  # TRANSCRIPT의 temp_id와 동일 (연결)
    statement_text: str  # 원본 전사 문장 (TRANSCRIPT.content)
    content: str  # 핵심 진술 설명 (description)


class Contradiction(BaseModel):
    temp_id: str  # KEY_STATEMENT의 temp_id (연결)
    description: str  # 모순 설명 + 끝에 "(temp_id : xx)" 포함
    type: str  # TIME, LOCATION, CONTENT, BEHAVIOR, CROSS_STATEMENT, CROSS_FILE


class Question(BaseModel):
    temp_id: str  # CONTRADICTION의 temp_id (연결)
    target: str  # 질문 대상 (temp_id 발화자가 아닌 상대방)
    question: str  # 질문 내용
    rationale: str  # 질문 근거


class VideoEvent(BaseModel):
    start_time: float
    end_time: float
    event_type: str  # ASSAULT, THEFT, SUSPICIOUS, MOVEMENT, INTERACTION, OTHER
    event_description: str


# ============================================================
# 요청/응답 스키마
# ============================================================

class AnalysisCallbackRequest(BaseModel):
    stage: str = Field(
        ...,
        description="SUMMARY | TRANSCRIPT | KEY_STATEMENT | CONTRADICTION | QUESTION | VIDEO_EVENT"
    )
    payload: Union[
        SummaryPayload,
        List[TranscriptItem],
        List[KeyStatement],
        List[Contradiction],
        List[Question],
        List[VideoEvent],
        dict
    ]


class AnalysisCallbackResponse(BaseModel):
    message: str = "Callback received"
