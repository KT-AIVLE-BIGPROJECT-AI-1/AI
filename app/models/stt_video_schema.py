from typing import List, Literal, Optional
from pydantic import BaseModel

# ===============================
# 🔹 STAGE 타입
# ===============================
StageType = Literal[
    "TRANSCRIPT",
    "KEY_STATEMENT",
    "CONTRADICTION",
    "QUESTION",
    "VIDEO_EVENT",
    "SUMMARY"
]

# ===============================
# 🔹 CALLBACK PAYLOAD (각 stage별)
# ===============================

class SummaryPayload(BaseModel):
    summary: str
    confidence: float
    keywords: List[str]

class TranscriptPayload(BaseModel):
    content: str

class KeyStatementItem(BaseModel):
    tempId: str
    content: str

class ContradictionItem(BaseModel):
    statementTempId: str
    description: str
    type: str

class QuestionItem(BaseModel):
    statementTempId: str
    question: str

class VideoEventItem(BaseModel):
    startTime: float
    endTime: float
    eventType: str
    description: str

# ===============================
# 🔹 CALLBACK REQUEST MODEL
# ===============================

class StageCallbackRequest(BaseModel):
    stage: StageType
    payload: dict   # stage별로 위 구조를 담음


