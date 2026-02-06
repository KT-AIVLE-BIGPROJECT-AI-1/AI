"""
분석 콜백 관련 스키마
POST /cases/{caseId}/analysis/{analysisId}/callback
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from enum import Enum


class CallbackStage(str, Enum):
    """콜백 단계"""
    TRANSCRIPT = "TRANSCRIPT"  # 음성 전사
    KEY_STATEMENT = "KEY_STATEMENT"  # 핵심 진술
    CONTRADICTION = "CONTRADICTION"  # 모순 탐지
    QUESTION = "QUESTION"  # 추가 질문
    VIDEO_EVENT = "VIDEO_EVENT"  # 비디오 이벤트
    SUMMARY = "SUMMARY"  # 최종 요약


class TranscriptSegment(BaseModel):
    """전사 세그먼트"""
    start: float = Field(..., description="시작 시간 (초)")
    end: float = Field(..., description="종료 시간 (초)")
    speaker: str = Field(..., description="화자 (SPEAKER_1, SPEAKER_2 등)")
    text: str = Field(..., description="전사 텍스트")


class TranscriptCallback(BaseModel):
    """음성 전사 콜백 데이터"""
    stage: CallbackStage = Field(CallbackStage.TRANSCRIPT, description="단계")
    content: List[TranscriptSegment] = Field(..., description="전사 내용")


class KeyStatementCallback(BaseModel):
    """핵심 진술 콜백 데이터"""
    stage: CallbackStage = Field(CallbackStage.KEY_STATEMENT, description="단계")
    tempId: str = Field(..., description="임시 ID (예: ks-1)")
    transcript_id: str = Field(..., description="전사 ID")
    transcript: str = Field(..., description="원본 전사 텍스트")
    description: str = Field(..., description="진술 설명")


class ContradictionCallback(BaseModel):
    """모순 탐지 콜백 데이터"""
    stage: CallbackStage = Field(CallbackStage.CONTRADICTION, description="단계")
    statementTempId_1: str = Field(..., description="모순되는 진술 1의 tempId")
    statementTempId_2: str = Field(..., description="모순되는 진술 2의 tempId")
    type: str = Field(..., description="모순 타입 (TIME/LOCATION/ACTION/STATEMENT)")
    description: str = Field(..., description="모순 설명")
    status: str = Field("ONGOING", description="상태 (ONGOING/RESOLVED)")


class QuestionCallback(BaseModel):
    """추가 질문 콜백 데이터"""
    stage: CallbackStage = Field(CallbackStage.QUESTION, description="단계")
    contradictionTempId: str = Field(..., description="관련 모순 tempId")
    question: str = Field(..., description="추가 질문 내용")


class VideoEventCallback(BaseModel):
    """비디오 이벤트 콜백 데이터"""
    stage: CallbackStage = Field(CallbackStage.VIDEO_EVENT, description="단계")
    event_id: str = Field(..., description="이벤트 ID")
    origin_name: str = Field(..., description="원본 파일명")
    start_time: float = Field(..., description="시작 시간 (초)")
    end_time: float = Field(..., description="종료 시간 (초)")
    event_type: str = Field(..., description="이벤트 타입 (ASSAULT/THEFT/OTHER)")
    event_description: str = Field(..., description="이벤트 설명")


class SummaryCallback(BaseModel):
    """요약 콜백 데이터"""
    stage: CallbackStage = Field(CallbackStage.SUMMARY, description="단계")
    summary: str = Field(..., description="최종 요약 내용")
    key_findings: List[str] = Field(default_factory=list, description="주요 발견사항")


class AnalysisCallbackRequest(BaseModel):
    """분석 콜백 요청 (통합)"""
    case_id: str = Field(..., description="사건 ID")
    analysis_id: str = Field(..., description="분석 ID")
    stage: CallbackStage = Field(..., description="콜백 단계")
    payload: Union[
        TranscriptCallback,
        KeyStatementCallback,
        ContradictionCallback,
        QuestionCallback,
        VideoEventCallback,
        SummaryCallback,
        Dict[str, Any]
    ] = Field(..., description="단계별 페이로드")
    
    class Config:
        json_schema_extra = {
            "example": {
                "case_id": "2e6b7f2a-6b1d-4c9e-9e59-4c1b2a7f3d91",
                "analysis_id": "dfbde9f8-1234-5678-90ab-cdef12345678",
                "stage": "TRANSCRIPT",
                "payload": {
                    "stage": "TRANSCRIPT",
                    "content": [
                        {
                            "start": 1.0,
                            "end": 5.5,
                            "speaker": "SPEAKER_1",
                            "text": "안녕하세요"
                        }
                    ]
                }
            }
        }


class AnalysisCallbackResponse(BaseModel):
    """분석 콜백 응답"""
    callback_id: str = Field(..., description="콜백 ID")
    case_id: str = Field(..., description="사건 ID")
    analysis_id: str = Field(..., description="분석 ID")
    stage: CallbackStage = Field(..., description="처리된 단계")
    status: str = Field(..., description="처리 상태 (SUCCESS/FAILED)")
    message: str = Field(..., description="처리 메시지")
    created_at: datetime = Field(..., description="생성 시각")
    
    class Config:
        json_schema_extra = {
            "example": {
                "callback_id": "cb-123-456",
                "case_id": "2e6b7f2a-6b1d-4c9e-9e59-4c1b2a7f3d91",
                "analysis_id": "dfbde9f8-1234-5678-90ab-cdef12345678",
                "stage": "TRANSCRIPT",
                "status": "SUCCESS",
                "message": "전사 데이터가 성공적으로 저장되었습니다.",
                "created_at": "2026-02-06T06:33:55.946919+00:00"
            }
        }
