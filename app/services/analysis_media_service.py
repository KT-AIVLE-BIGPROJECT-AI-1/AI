# app/services/analysis_media_service.py

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any
from openai import OpenAI

from app.config import settings
from app.models.analysis_media_schema import (
    AnalysisMediaRequest,
    AnalysisMediaResponse
)

client = OpenAI(api_key=settings.OPENAI_API_KEY)


# ============================================================
# create_analysis_vdo_from_video_events (AI.ipynb와 100% 동일)
# ============================================================

def create_analysis_vdo_from_video_events(
    video_events: List[Dict],
    investigate_files: List[Dict]
) -> List[Dict[str, Any]]:
    """VIDEO_EVENT를 ANALYSIS_VDO 형식으로 변환"""
    analysis_vdo_list = []

    events_by_origin = {}
    for video_event in video_events:
        origin = video_event.get("origin_name")
        if origin not in events_by_origin:
            events_by_origin[origin] = []

        for event in video_event.get("payload", []):
            events_by_origin[origin].append({
                "event_id": str(uuid.uuid4()),
                "analysis_id": video_event.get("analysis_id"),
                "origin_name": origin,
                "start_time": event.get("start_time", 0.0),
                "end_time": event.get("end_time", 0.0),
                "event_type": event.get("event_type", "OTHER"),
                "event_description": event.get("event_description", ""),
                "created_at": video_event.get("created_at")
            })

    for origin_name, events in events_by_origin.items():
        print(f"📄 PROCESSING: {origin_name}")

        file_id = None
        for rec in investigate_files:
            if rec.get("origin_name") == origin_name:
                file_id = rec["file_id"]
                break

        if not file_id:
            print(f"⚠️ PENDING: {origin_name}")
            status = "PENDING"
        else:
            status = "COMPLETED"
            print(f"✅ COMPLETED: {origin_name}")

        analysis_vdo = {
            "analysis_id": str(uuid.uuid4()),
            "file_id": file_id,
            "analysis_type": "VDO",
            "status": status,
            "result_data": events,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        analysis_vdo_list.append(analysis_vdo)

    return analysis_vdo_list


# ============================================================
# create_analysis_aud (AI.ipynb와 100% 동일)
# ============================================================

def create_analysis_aud(file_id: str, dialogue: list, status: str = "COMPLETED") -> dict:
    """음성 파일 분석 결과를 ANALYSIS_AUD 형식으로 생성 (stage + payload 구조)"""

    payload = {
        "stage": "TRANSCRIPT",
        "content": dialogue
    }

    analysis_aud = {
        "analysis_id": str(uuid.uuid4()),
        "file_id": file_id,
        "analysis_type": "AUD",
        "status": status,
        "payload": payload,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    return analysis_aud


# ============================================================
# create_analysis_stt (AI.ipynb와 100% 동일)
# ============================================================

def utc_now_iso():
    """UTC 현재 시간을 ISO 형식으로 반환"""
    return datetime.now(timezone.utc).isoformat()


def create_analysis_stt(
    transcript_list: List[Dict],
    key_statement_list: List[Dict],
    contradiction_list: List[Dict],
    question_list: List[Dict]
) -> List[Dict]:
    """TRANSCRIPT, KEY_STATEMENT, CONTRADICTION, QUESTION을 ANALYSIS_STT로 통합"""

    print("\n" + "="*70)
    print("📦 ANALYSIS_STT 생성")
    print("="*70 + "\n")

    # analysis_id별로 데이터 그룹핑
    analysis_groups = {}

    # 1. TRANSCRIPT 그룹핑
    for t in transcript_list:
        analysis_id = t.get("analysis_id")
        file_id = t.get("file_id")

        if not analysis_id:
            continue

        if analysis_id not in analysis_groups:
            analysis_groups[analysis_id] = {
                "file_id": file_id,
                "transcript": [],
                "key_statements": [],
                "contradictions": [],
                "questions": []
            }

        # TRANSCRIPT의 content 추출
        payload = t.get("payload", {})
        content = payload.get("content", [])
        analysis_groups[analysis_id]["transcript"] = content

    # 2. KEY_STATEMENT 그룹핑
    for ks in key_statement_list:
        analysis_id = ks.get("analysis_id")
        if analysis_id and analysis_id in analysis_groups:
            analysis_groups[analysis_id]["key_statements"].append(ks)

    # 3. CONTRADICTION 그룹핑
    for cont in contradiction_list:
        analysis_id = cont.get("analysis_id")
        if analysis_id and analysis_id in analysis_groups:
            analysis_groups[analysis_id]["contradictions"].append(cont)

    # 4. QUESTION 그룹핑
    for q in question_list:
        analysis_id = q.get("analysis_id")
        if analysis_id and analysis_id in analysis_groups:
            analysis_groups[analysis_id]["questions"].append(q)

    print(f"📂 {len(analysis_groups)}개 분석 파일 발견\n")

    # 각 analysis_id별로 ANALYSIS_STT 생성
    analysis_stt_list = []

    for analysis_id, data in analysis_groups.items():
        print(f"📄 분석 중: analysis_id={analysis_id[:8]}...")

        file_id = data["file_id"]
        transcript_content = data["transcript"]
        key_statements = data["key_statements"]
        contradictions = data["contradictions"]
        questions = data["questions"]

        # result_data 구성 (타입별로 그룹핑)
        result_data = {}

        # TRANSCRIPT - content 배열
        if transcript_content:
            result_data["transcript"] = transcript_content

        # KEY_STATEMENT - 배열로 그룹핑
        key_statement_list = []
        for ks in key_statements:
            payload = ks.get("payload", {})
            key_statement_list.append({
                "tempId": payload.get("tempId", ""),
                "transcript_id": payload.get("transcript_id", ""),
                "transcript": payload.get("transcript", ""),
                "description": payload.get("description", ""),
                "statement_id": ks.get("statement_id"),
                "created_at": ks.get("created_at")
            })
        if key_statement_list:
            result_data["key_statements"] = key_statement_list

        # CONTRADICTION - 배열로 그룹핑
        contradiction_list = []
        for cont in contradictions:
            payload = cont.get("payload", {})
            contradiction_list.append({
                "statementTempId_1": payload.get("statementTempId_1", ""),
                "statementTempId_2": payload.get("statementTempId_2", ""),
                "type": payload.get("type", ""),
                "description": payload.get("description", ""),
                "status": payload.get("status", ""),
                "contradiction_id": cont.get("contradiction_id"),
                "created_at": cont.get("created_at")
            })
        if contradiction_list:
            result_data["contradictions"] = contradiction_list

        # QUESTION - 배열로 그룹핑
        question_list = []
        for q in questions:
            payload = q.get("payload", {})
            question_list.append({
                "statementTempId": payload.get("statementTempId", ""),
                "question": payload.get("question", ""),
                "rationale": payload.get("rationale", ""),
                "question_id": q.get("question_id"),
                "contradiction_id": q.get("contradiction_id"),
                "created_at": q.get("created_at")
            })
        if question_list:
            result_data["questions"] = question_list

        # ANALYSIS_STT 레코드 생성
        analysis_stt = {
            "analysis_id": analysis_id,
            "file_id": file_id,
            "analysis_type": "STT",
            "status": "COMPLETED",
            "result_data": result_data,
            "created_at": utc_now_iso()
        }

        analysis_stt_list.append(analysis_stt)

        print(f"   ✅ 통합 완료")
        print(f"      - transcript: {len(transcript_content)}개 발화")
        print(f"      - key_statements: {len(key_statements)}개")
        print(f"      - contradictions: {len(contradictions)}개")
        print(f"      - questions: {len(questions)}개")
        print()

    print("="*70)
    print(f"✅ ANALYSIS_STT 생성 완료: {len(analysis_stt_list)}건")
    print("="*70)

    return analysis_stt_list


# ============================================================
# FastAPI Service
# ============================================================

class AnalysisMediaService:
    """
    미디어 분석 서비스
    - 영상 분석 (VDO)
    - 음성 분석 (STT)
    """
    
    @staticmethod
    def analyze_media(request: AnalysisMediaRequest) -> AnalysisMediaResponse:
        """
        미디어 파일 분석 (비디오/오디오 자동 분기)
        
        **현재는 분석 작업만 등록하고 PENDING 상태로 반환**
        실제 분석은 외부 AI 서버에서 수행 후 콜백으로 결과 전달
        """
        print(f"\n🎬 미디어 분석 시작: {request.file_id}")
        print(f"   - file_type: {request.file_type}")
        print(f"   - file_path: {request.file_path}")
        
        # 파일 타입에 따라 analysis_type 결정
        file_type_lower = request.file_type.lower()
        
        if file_type_lower == "video":
            analysis_type = "VDO"
        elif file_type_lower == "audio":
            analysis_type = "STT"
        else:
            raise ValueError(f"지원하지 않는 파일 타입: {request.file_type}")
        
        # 파일 존재 확인
        file_path = Path(request.file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {request.file_path}")
        
        # 분석 작업 등록 (실제 분석은 외부 AI 서버에서 수행)
        analysis_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        
        print(f"✅ 분석 작업 등록 완료")
        print(f"   - analysis_id: {analysis_id}")
        print(f"   - analysis_type: {analysis_type}")
        print(f"   - status: PENDING (외부 AI 서버에서 분석 중)")
        
        return AnalysisMediaResponse(
            analysis_id=analysis_id,
            file_id=request.file_id,
            analysis_type=analysis_type,
            status="PENDING",
            result_data="분석 대기 중. AI 서버에서 분석 완료 후 콜백으로 결과 전달됩니다.",
            created_at=created_at
        )
    
    @staticmethod
    def analyze_video(video_events: List[Dict], investigate_files: List[Dict]) -> List[Dict]:
        """영상 이벤트를 ANALYSIS_VDO로 변환 (콜백 결과 처리용)"""
        return create_analysis_vdo_from_video_events(video_events, investigate_files)
    
    @staticmethod
    def analyze_audio(file_id: str, dialogue: list, status: str = "COMPLETED") -> dict:
        """음성 전사 결과를 ANALYSIS_AUD로 변환 (콜백 결과 처리용)"""
        return create_analysis_aud(file_id, dialogue, status)
    
    @staticmethod
    def create_stt_analysis(
        transcript_list: List[Dict],
        key_statement_list: List[Dict],
        contradiction_list: List[Dict],
        question_list: List[Dict]
    ) -> List[Dict]:
        """STT 분석 통합 (콜백 결과 처리용)"""
        return create_analysis_stt(
            transcript_list,
            key_statement_list,
            contradiction_list,
            question_list
        )