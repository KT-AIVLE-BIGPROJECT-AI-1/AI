from typing import List, Literal, Union
from pydantic import BaseModel

StageType = Literal[
    "TRANSCRIPT",
    "KEY_STATEMENT",
    "CONTRADICTION",
    "QUESTION",
    "VIDEO_EVENT",
    "SUMMARY"
]

# ====== 각 Stage별 payload ======

class TranscriptPayload(BaseModel):
    content: str

class KeyStatementItem(BaseModel):
    tempId: str
    content: str

class ContradictionItem(BaseModel):
    statementTempId: str
    description: str
    type: Literal["TIME", "LOCATION", "ACTION", "STATEMENT"]

class QuestionItem(BaseModel):
    statementTempId: str
    question: str

class VideoEventItem(BaseModel):
    startTime: float
    endTime: float
    eventType: str
    description: str

class SummaryPayload(BaseModel):
    summary: str
    confidence: float
    keywords: List[str]

# ====== 최종 콜백 바디 ======

class CallbackBody(BaseModel):
    stage: StageType
    payload: dict | list

