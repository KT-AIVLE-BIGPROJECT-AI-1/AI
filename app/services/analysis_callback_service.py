"""
분석 콜백 처리 서비스
"""
from typing import Dict, Any
import uuid
from datetime import datetime, timezone

from app.models.analysis_callback_schema import (
    CallbackStage,
    AnalysisCallbackResponse
)


class AnalysisCallbackService:
    """분석 콜백 처리 서비스"""
    
    def __init__(self):
        # 실제 프로덕션에서는 DB에 저장
        self._storage: Dict[str, Dict[str, Any]] = {}
    
    def process_callback(
        self,
        case_id: str,
        analysis_id: str,
        stage: CallbackStage,
        payload: Dict[str, Any]
    ) -> AnalysisCallbackResponse:
        """콜백 데이터 처리"""
        
        callback_id = str(uuid.uuid4())
        
        try:
            # 단계별 처리
            if stage == CallbackStage.TRANSCRIPT:
                message = self._process_transcript(case_id, analysis_id, payload)
            
            elif stage == CallbackStage.KEY_STATEMENT:
                message = self._process_key_statement(case_id, analysis_id, payload)
            
            elif stage == CallbackStage.CONTRADICTION:
                message = self._process_contradiction(case_id, analysis_id, payload)
            
            elif stage == CallbackStage.QUESTION:
                message = self._process_question(case_id, analysis_id, payload)
            
            elif stage == CallbackStage.VIDEO_EVENT:
                message = self._process_video_event(case_id, analysis_id, payload)
            
            elif stage == CallbackStage.SUMMARY:
                message = self._process_summary(case_id, analysis_id, payload)
            
            else:
                message = f"알 수 없는 단계: {stage}"
                status = "FAILED"
                
                return AnalysisCallbackResponse(
                    callback_id=callback_id,
                    case_id=case_id,
                    analysis_id=analysis_id,
                    stage=stage,
                    status=status,
                    message=message,
                    created_at=datetime.now(timezone.utc)
                )
            
            # 저장 (메모리 - 실제로는 DB 사용)
            storage_key = f"{case_id}:{analysis_id}:{stage.value}"
            self._storage[storage_key] = {
                "callback_id": callback_id,
                "payload": payload,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            return AnalysisCallbackResponse(
                callback_id=callback_id,
                case_id=case_id,
                analysis_id=analysis_id,
                stage=stage,
                status="SUCCESS",
                message=message,
                created_at=datetime.now(timezone.utc)
            )
        
        except Exception as e:
            return AnalysisCallbackResponse(
                callback_id=callback_id,
                case_id=case_id,
                analysis_id=analysis_id,
                stage=stage,
                status="FAILED",
                message=f"처리 중 오류 발생: {str(e)}",
                created_at=datetime.now(timezone.utc)
            )
    
    def _process_transcript(
        self, 
        case_id: str, 
        analysis_id: str, 
        payload: Dict[str, Any]
    ) -> str:
        """전사 데이터 처리"""
        content = payload.get("content", [])
        segment_count = len(content)
        
        # 실제로는 DB에 저장
        print(f"📝 전사 데이터 저장: {segment_count}개 세그먼트")
        
        return f"전사 데이터 {segment_count}개 세그먼트가 저장되었습니다."
    
    def _process_key_statement(
        self, 
        case_id: str, 
        analysis_id: str, 
        payload: Dict[str, Any]
    ) -> str:
        """핵심 진술 처리"""
        temp_id = payload.get("tempId", "")
        
        print(f"🔑 핵심 진술 저장: {temp_id}")
        
        return f"핵심 진술 ({temp_id})이 저장되었습니다."
    
    def _process_contradiction(
        self, 
        case_id: str, 
        analysis_id: str, 
        payload: Dict[str, Any]
    ) -> str:
        """모순 데이터 처리"""
        temp_id_1 = payload.get("statementTempId_1", "")
        temp_id_2 = payload.get("statementTempId_2", "")
        contra_type = payload.get("type", "")
        
        print(f"⚠️ 모순 탐지 저장: {temp_id_1} ↔ {temp_id_2} (타입: {contra_type})")
        
        return f"모순 정보가 저장되었습니다 ({temp_id_1} ↔ {temp_id_2})."
    
    def _process_question(
        self, 
        case_id: str, 
        analysis_id: str, 
        payload: Dict[str, Any]
    ) -> str:
        """추가 질문 처리"""
        question = payload.get("question", "")
        
        print(f"❓ 추가 질문 저장: {question[:50]}...")
        
        return "추가 질문이 저장되었습니다."
    
    def _process_video_event(
        self, 
        case_id: str, 
        analysis_id: str, 
        payload: Dict[str, Any]
    ) -> str:
        """비디오 이벤트 처리"""
        event_id = payload.get("event_id", "")
        event_type = payload.get("event_type", "")
        
        print(f"🎬 비디오 이벤트 저장: {event_id} (타입: {event_type})")
        
        return f"비디오 이벤트 ({event_id})가 저장되었습니다."
    
    def _process_summary(
        self, 
        case_id: str, 
        analysis_id: str, 
        payload: Dict[str, Any]
    ) -> str:
        """요약 데이터 처리"""
        summary = payload.get("summary", "")
        key_findings = payload.get("key_findings", [])
        
        print(f"📊 요약 저장: {len(summary)} 글자, {len(key_findings)}개 주요 발견사항")
        
        return f"요약이 저장되었습니다 (주요 발견사항 {len(key_findings)}개)."
    
    def get_callback_data(
        self, 
        case_id: str, 
        analysis_id: str, 
        stage: CallbackStage
    ) -> Dict[str, Any]:
        """저장된 콜백 데이터 조회"""
        storage_key = f"{case_id}:{analysis_id}:{stage.value}"
        return self._storage.get(storage_key, {})
