# app/models/analysis_callback_schema.py

from pydantic import BaseModel, Field
from typing import List, Optional, Union, Any


# ============================================================
# Stage별 Payload 스키마
# ============================================================

class SummaryPayload(BaseModel):
    summary: str
    confidence: float
    keywords: List[str]


class TranscriptPayload(BaseModel):
    content: str


class KeyStatement(BaseModel):
    temp_id: str
    content: str


class Contradiction(BaseModel):
    statement_temp_id: str
    description: str
    type: str  # TIME, LOCATION, CONTENT


class Question(BaseModel):
    statement_temp_id: str
    question: str


class VideoEvent(BaseModel):
    start_time: float
    end_time: float
    event_type: str  # ASSAULT, THEFT 등
    event_description: str


# ============================================================
# 요청 스키마
# ============================================================

class AnalysisCallbackRequest(BaseModel):
    stage: str = Field(
        ...,
        description="'TRANSCRIPT | KEY_STATEMENT | CONTRADICTION | QUESTION | VIDEO_EVENT | SUMMARY'"
    )
    payload: Union[
        SummaryPayload,
        TranscriptPayload,
        List[KeyStatement],
        List[Contradiction],
        List[Question],
        List[VideoEvent],
        dict
    ] = Field(default_factory=dict)


# ============================================================
# 응답 스키마
# ============================================================

class StageResult(BaseModel):
    stage: str
    payload: Any


class AnalysisResultItem(BaseModel):
    analysis_id: str
    result_data: Any = Field(
        ...,
        description="""
        파일 유형별 응답 구조:
        - 문서/이미지: {"stage": "SUMMARY", "payload": {...}} (단일 객체)
        - 음성: [TRANSCRIPT, KEY_STATEMENT, (CONTRADICTION, QUESTION)] (배열)
          * CONTRADICTION이 없으면 QUESTION도 없음
          * CONTRADICTION이 있으면 QUESTION도 반드시 있음
        - 영상: [VIDEO_EVENT, VIDEO_EVENT, ...] (배열)
        """
    )