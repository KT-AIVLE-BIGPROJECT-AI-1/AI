# app/services/analysis_callback_service.py

import json
import re
from typing import Dict, List, Any, Union
from app.models.analysis_callback_schema import (
    AnalysisCallbackRequest,
    AnalysisResultItem,
    StageResult
)


class AnalysisCallbackService:
    """
    분석 콜백 서비스 (저장 + 조회)
    
    각 stage의 JSON은 이전 단계에서 이미 생성된 데이터.
    
    [저장 경로]
    - TRANSCRIPT, KEY_STATEMENT, CONTRADICTION, QUESTION, VIDEO_EVENT
      → 외부 AI가 콜백 엔드포인트로 payload 전송하여 저장
    - SUMMARY
      → ANALYSIS_DOC/IMG 서비스에서 register_analysis_result()로 등록
    
    [조회]
    - 백엔드가 빈 payload로 요청 → 파일별 stage 데이터를 그룹핑하여 반환
    
    [음성 파일 stage 의존성]
    - TRANSCRIPT → 항상 생성
    - KEY_STATEMENT → 항상 생성
    - CONTRADICTION → KEY_STATEMENT에서 모순이 감지된 경우에만 생성
    - QUESTION → CONTRADICTION이 있을 때만 생성 (CONTRADICTION 없으면 QUESTION도 없음)
    """
    
    # {case_id: [{analysis_id, file_type, origin_name, ...}]}
    _investigation_files: Dict[str, List[Dict[str, Any]]] = {}
    
    # {case_id: {analysis_id: [{"stage": ..., "payload": ...}]}}
    _stage_storage: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    
    # {analysis_id: {result_data, ...}} — ANALYSIS_DOC/IMG 결과 (SUMMARY용)
    _analysis_results: Dict[str, Dict[str, Any]] = {}
    
    # {case_id: {description, title, type, ...}}
    _case_details: Dict[str, Dict[str, Any]] = {}
    
    VALID_STAGES = {"SUMMARY", "TRANSCRIPT", "KEY_STATEMENT", "CONTRADICTION", "QUESTION", "VIDEO_EVENT"}
    
    # 음성 파일 stage 순서 (응답 시 이 순서로 정렬)
    AUDIO_STAGE_ORDER = ["TRANSCRIPT", "KEY_STATEMENT", "CONTRADICTION", "QUESTION"]
    
    # ============================================================
    # 외부 서비스에서 호출하는 등록 메서드
    # ============================================================
    
    @staticmethod
    def register_investigation_files(case_id: str, case_detail: dict, files: list):
        """
        INVESTIGATION_FILE 서비스에서 호출.
        case에 속한 파일 목록과 사건 정보를 등록.
        """
        AnalysisCallbackService._investigation_files[case_id] = files
        AnalysisCallbackService._case_details[case_id] = case_detail
        
        print(f"   📋 콜백 서비스에 파일 {len(files)}개 등록 (case_id={case_id})")
    
    @staticmethod
    def register_analysis_result(analysis_id: str, result_data: dict):
        """
        ANALYSIS_DOC / ANALYSIS_IMG 서비스에서 호출.
        분석 결과를 등록 (SUMMARY 조회 시 사용).
        """
        AnalysisCallbackService._analysis_results[analysis_id] = result_data
        
        print(f"   📊 콜백 서비스에 분석 결과 등록 (analysis_id={analysis_id})")
    
    # ============================================================
    # 메인 핸들러
    # ============================================================
    
    @staticmethod
    def handle_callback(
        case_id: str,
        analysis_id: str,
        request: AnalysisCallbackRequest
    ) -> Union[dict, List[AnalysisResultItem]]:
        """
        콜백 처리 메인 로직
        
        - payload가 비어있으면 → 조회 모드 (파일별 그룹핑 응답)
        - payload에 데이터가 있으면 → 저장 모드 ("Callback received" 응답)
        """
        is_empty = AnalysisCallbackService._is_empty_payload(request.payload)
        
        if is_empty:
            # ==================== 조회 모드 ====================
            print("\n" + "=" * 70)
            print(f"📤 콜백 조회 요청")
            print(f"   - case_id: {case_id}")
            print(f"   - stages: {request.stage}")
            print("=" * 70)
            
            results = AnalysisCallbackService._retrieve_all(case_id, request.stage)
            
            print(f"✅ 조회 완료: {len(results)}개 파일")
            print("=" * 70)
            
            return results
        else:
            # ==================== 저장 모드 ====================
            print("\n" + "=" * 70)
            print(f"📥 콜백 저장 요청")
            print(f"   - case_id: {case_id}")
            print(f"   - analysis_id: {analysis_id}")
            print(f"   - stage: {request.stage}")
            print("=" * 70)
            
            AnalysisCallbackService._store(case_id, analysis_id, request)
            
            print(f"✅ 저장 완료")
            print("=" * 70)
            
            return {"message": "Callback received"}
    
    # ============================================================
    # 저장 모드: 외부 AI가 stage 결과 전송
    # ============================================================
    
    @staticmethod
    def _store(case_id: str, analysis_id: str, request: AnalysisCallbackRequest):
        """외부 AI가 보낸 stage 데이터를 저장"""
        storage = AnalysisCallbackService._stage_storage
        
        # 저장소 초기화
        if case_id not in storage:
            storage[case_id] = {}
        if analysis_id not in storage[case_id]:
            storage[case_id][analysis_id] = []
        
        stage = request.stage.strip().upper()
        payload = AnalysisCallbackService._to_serializable(request.payload)
        
        storage[case_id][analysis_id].append({
            "stage": stage,
            "payload": payload
        })
        
        print(f"   📦 저장: [{stage}] → analysis_id={analysis_id}")
        print(f"   📦 현재 저장 건수: {len(storage[case_id][analysis_id])}건")
    
    # ============================================================
    # 조회 모드: 파일별 stage 데이터 그룹핑 반환
    # ============================================================
    
    @staticmethod
    def _retrieve_all(case_id: str, stage_str: str) -> List[AnalysisResultItem]:
        """
        case의 모든 파일별로 요청된 stage 데이터를 그룹핑하여 반환.
        
        - 문서/이미지: result_data = {"stage": "SUMMARY", "payload": {...}}
        - 음성: result_data = [TRANSCRIPT, KEY_STATEMENT, (CONTRADICTION, QUESTION)]
        - 영상: result_data = [VIDEO_EVENT, ...]
        """
        requested_stages = {s.strip().upper() for s in stage_str.split("|") if s.strip()}
        
        files = AnalysisCallbackService._investigation_files.get(case_id, [])
        stage_storage = AnalysisCallbackService._stage_storage.get(case_id, {})
        
        if not files:
            print(f"   ⚠️ case_id={case_id}에 등록된 파일이 없습니다.")
            return []
        
        results = []
        
        for file_info in files:
            file_type = file_info.get("file_type", "").upper()
            aid = file_info.get("analysis_id", "")
            origin_name = file_info.get("origin_name", "")
            
            print(f"   📁 [{aid}] {origin_name} ({file_type})")
            
            if file_type in ("DOCUMENT", "IMAGE"):
                # ── 문서/이미지 → SUMMARY (ANALYSIS 결과에서 가져옴) ──
                if "SUMMARY" not in requested_stages:
                    continue
                
                result = AnalysisCallbackService._get_summary_for_file(aid)
                if result:
                    results.append(result)
            
            elif file_type == "AUDIO":
                # ── 음성 → TRANSCRIPT, KEY_STATEMENT, (CONTRADICTION, QUESTION) ──
                result = AnalysisCallbackService._build_audio_result(
                    aid, requested_stages, stage_storage
                )
                if result:
                    results.append(result)
            
            elif file_type == "VIDEO":
                # ── 영상 → VIDEO_EVENT ──
                if "VIDEO_EVENT" not in requested_stages:
                    continue
                
                result = AnalysisCallbackService._build_video_result(
                    aid, stage_storage
                )
                if result:
                    results.append(result)
        
        return results
    
    # ============================================================
    # 문서/이미지 → SUMMARY
    # ============================================================
    
    @staticmethod
    def _get_summary_for_file(analysis_id: str) -> AnalysisResultItem:
        """ANALYSIS_DOC/IMG 결과에서 SUMMARY를 가져와서 반환"""
        analysis_result = AnalysisCallbackService._analysis_results.get(analysis_id)
        
        if not analysis_result:
            print(f"      ⚠️ analysis_id={analysis_id}: 분석 결과 없음")
            return None
        
        result_data_raw = analysis_result.get("result_data", "")
        summary_payload = AnalysisCallbackService._extract_summary(result_data_raw)
        
        print(f"      → SUMMARY 로드 완료")
        
        return AnalysisResultItem(
            analysis_id=analysis_id,
            result_data={
                "stage": "SUMMARY",
                "payload": summary_payload
            }
        )
    
    @staticmethod
    def _extract_summary(result_data: Any) -> dict:
        """ANALYSIS 결과에서 summary, confidence, keywords 추출"""
        if isinstance(result_data, dict):
            return {
                "summary": result_data.get("summary", result_data.get("result_data", "")),
                "confidence": result_data.get("confidence", 0.0),
                "keywords": result_data.get("keywords", [])
            }
        
        if isinstance(result_data, str):
            try:
                cleaned = re.sub(r"```json|```", "", result_data).strip()
                parsed = json.loads(cleaned)
                return {
                    "summary": parsed.get("summary", result_data[:200]),
                    "confidence": parsed.get("confidence", 0.85),
                    "keywords": parsed.get("keywords", [])
                }
            except (json.JSONDecodeError, AttributeError):
                return {
                    "summary": str(result_data)[:500],
                    "confidence": 0.8,
                    "keywords": []
                }
        
        return {"summary": "", "confidence": 0.0, "keywords": []}
    
    # ============================================================
    # 음성 → TRANSCRIPT, KEY_STATEMENT, (CONTRADICTION, QUESTION)
    # ============================================================
    
    @staticmethod
    def _build_audio_result(
        analysis_id: str,
        requested_stages: set,
        stage_storage: dict
    ) -> AnalysisResultItem:
        """
        음성 파일의 stage 데이터를 조회하여 반환.
        
        의존성:
        - TRANSCRIPT: 항상 포함
        - KEY_STATEMENT: 항상 포함
        - CONTRADICTION: 저장된 경우에만 포함
        - QUESTION: CONTRADICTION이 있을 때만 포함 (없으면 QUESTION도 제외)
        """
        entries = stage_storage.get(analysis_id, [])
        if not entries:
            return None
        
        # stage별로 분류
        stage_map = {}
        for entry in entries:
            stage_name = entry["stage"]
            if stage_name not in stage_map:
                stage_map[stage_name] = []
            stage_map[stage_name].append(entry)
        
        # 응답에 포함할 stage 결정 (순서 보장)
        result_data = []
        
        # TRANSCRIPT — 항상 포함
        if "TRANSCRIPT" in requested_stages and "TRANSCRIPT" in stage_map:
            result_data.extend(stage_map["TRANSCRIPT"])
        
        # KEY_STATEMENT — 항상 포함
        if "KEY_STATEMENT" in requested_stages and "KEY_STATEMENT" in stage_map:
            result_data.extend(stage_map["KEY_STATEMENT"])
        
        # CONTRADICTION — 저장된 경우에만 포함
        has_contradiction = "CONTRADICTION" in stage_map and len(stage_map["CONTRADICTION"]) > 0
        
        if "CONTRADICTION" in requested_stages and has_contradiction:
            result_data.extend(stage_map["CONTRADICTION"])
        
        # QUESTION — CONTRADICTION이 있을 때만 포함
        if "QUESTION" in requested_stages and has_contradiction and "QUESTION" in stage_map:
            result_data.extend(stage_map["QUESTION"])
        
        if not result_data:
            return None
        
        stage_names = [e["stage"] for e in result_data]
        print(f"      → 음성 stages: {stage_names}")
        
        return AnalysisResultItem(
            analysis_id=analysis_id,
            result_data=result_data
        )
    
    # ============================================================
    # 영상 → VIDEO_EVENT
    # ============================================================
    
    @staticmethod
    def _build_video_result(
        analysis_id: str,
        stage_storage: dict
    ) -> AnalysisResultItem:
        """영상 파일의 VIDEO_EVENT 데이터를 조회하여 반환"""
        entries = stage_storage.get(analysis_id, [])
        
        video_events = [
            entry for entry in entries
            if entry["stage"] == "VIDEO_EVENT"
        ]
        
        if not video_events:
            return None
        
        print(f"      → VIDEO_EVENT {len(video_events)}건")
        
        return AnalysisResultItem(
            analysis_id=analysis_id,
            result_data=video_events
        )
    
    # ============================================================
    # 유틸리티
    # ============================================================
    
    @staticmethod
    def _is_empty_payload(payload: Any) -> bool:
        """payload가 비어있는지 확인"""
        if payload is None:
            return True
        if isinstance(payload, dict) and len(payload) == 0:
            return True
        return False
    
    @staticmethod
    def _to_serializable(payload: Any) -> Any:
        """payload를 JSON 직렬화 가능한 형태로 변환"""
        if hasattr(payload, 'model_dump'):
            return payload.model_dump()
        if isinstance(payload, list):
            return [
                item.model_dump() if hasattr(item, 'model_dump')
                else dict(item) if hasattr(item, '__dict__')
                else item
                for item in payload
            ]
        if isinstance(payload, dict):
            return payload
        if hasattr(payload, '__dict__'):
            return dict(payload)
        return payload
    
    # ============================================================
    # 디버깅용 조회 메서드
    # ============================================================
    
    @staticmethod
    def get_registered_files(case_id: str = None) -> Any:
        """등록된 파일 목록 조회"""
        if case_id:
            return AnalysisCallbackService._investigation_files.get(case_id, [])
        return AnalysisCallbackService._investigation_files
    
    @staticmethod
    def get_stage_storage(case_id: str = None, analysis_id: str = None) -> Any:
        """저장된 stage 데이터 조회"""
        if case_id and analysis_id:
            return AnalysisCallbackService._stage_storage.get(case_id, {}).get(analysis_id, [])
        if case_id:
            return AnalysisCallbackService._stage_storage.get(case_id, {})
        return AnalysisCallbackService._stage_storage
    
    @staticmethod
    def get_analysis_results(analysis_id: str = None) -> Any:
        """등록된 ANALYSIS 분석 결과 조회"""
        if analysis_id:
            return AnalysisCallbackService._analysis_results.get(analysis_id, {})
        return AnalysisCallbackService._analysis_results