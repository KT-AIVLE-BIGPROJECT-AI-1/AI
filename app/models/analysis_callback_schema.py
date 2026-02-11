# app/models/analysis_callback_schema.py
# camelCase → snake_case 전면 변경 (#18)

from pydantic import BaseModel, Field
from typing import List, Optional, Union, Any


# ============================================================
# Payload 스키마 (snake_case)
# ============================================================

class SummaryPayload(BaseModel):
    summary: str
    confidence: float
    keywords: List[str]


class TranscriptPayload(BaseModel):
    content: Any  # str 또는 List[{"speaker": ..., "content": ...}]


class KeyStatement(BaseModel):
    temp_id: str
    content: str


class Contradiction(BaseModel):
    statement_temp_id: str
    counter_statement_temp_id: Optional[str] = None
    description: str
    type: str  # TIME, LOCATION, CONTENT, BEHAVIOR, CROSS_STATEMENT, CROSS_FILE


class Question(BaseModel):
    statement_temp_id: str
    target: Optional[str] = None
    question: str


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
        TranscriptPayload,
        List[KeyStatement],
        List[Contradiction],
        List[Question],
        List[VideoEvent],
        dict
    ]


class AnalysisCallbackResponse(BaseModel):
    message: str = "Callback received"