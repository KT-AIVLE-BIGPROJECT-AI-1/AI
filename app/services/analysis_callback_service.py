# app/services/analysis_callback_service.py
# ✅ 분석 결과 JSON 파일 영속 저장 (서버 재시작 후에도 챗봇 사용 가능)

import json
from pathlib import Path
from typing import Dict, List, Any
from app.models.analysis_callback_schema import (
    AnalysisCallbackRequest,
    AnalysisCallbackResponse
)

# 영속 저장 경로
_PERSISTENCE_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_RESULTS_FILE = _PERSISTENCE_DIR / "analysis_results.json"
_CALLBACKS_FILE = _PERSISTENCE_DIR / "callback_storage.json"


class AnalysisCallbackService:

    _callback_storage: Dict[str, Dict[str, Dict[str, List[Dict[str, Any]]]]] = {}
    _analysis_results: Dict[str, Dict[str, Any]] = {}

    # ============================================================
    # JSON 파일 영속 저장/로드
    # ============================================================

    @staticmethod
    def _save_results_to_disk():
        """_analysis_results를 JSON 파일로 저장"""
        try:
            _PERSISTENCE_DIR.mkdir(parents=True, exist_ok=True)
            with open(_RESULTS_FILE, "w", encoding="utf-8") as f:
                json.dump(AnalysisCallbackService._analysis_results, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"   ⚠️ 분석 결과 저장 실패: {e}")

    @staticmethod
    def _save_callbacks_to_disk():
        """_callback_storage를 JSON 파일로 저장"""
        try:
            _PERSISTENCE_DIR.mkdir(parents=True, exist_ok=True)
            with open(_CALLBACKS_FILE, "w", encoding="utf-8") as f:
                json.dump(AnalysisCallbackService._callback_storage, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"   ⚠️ 콜백 저장소 저장 실패: {e}")

    @staticmethod
    def load_from_disk():
        """서버 시작 시 JSON 파일에서 복원"""
        # analysis_results 복원
        if _RESULTS_FILE.exists():
            try:
                with open(_RESULTS_FILE, "r", encoding="utf-8") as f:
                    AnalysisCallbackService._analysis_results = json.load(f)
                print(f"   ✅ 분석 결과 복원: {len(AnalysisCallbackService._analysis_results)}건 ({_RESULTS_FILE})")
            except Exception as e:
                print(f"   ⚠️ 분석 결과 복원 실패: {e}")
        else:
            print(f"   ℹ️ 저장된 분석 결과 없음")

        # callback_storage 복원
        if _CALLBACKS_FILE.exists():
            try:
                with open(_CALLBACKS_FILE, "r", encoding="utf-8") as f:
                    AnalysisCallbackService._callback_storage = json.load(f)
                print(f"   ✅ 콜백 저장소 복원: {len(AnalysisCallbackService._callback_storage)}건")
            except Exception as e:
                print(f"   ⚠️ 콜백 저장소 복원 실패 (깨진 파일 삭제): {e}")
                _CALLBACKS_FILE.unlink(missing_ok=True)
                AnalysisCallbackService._callback_storage = {}
        else:
            print(f"   ℹ️ 저장된 콜백 저장소 없음")

    # ============================================================
    # 외부 AI → AI 서버 콜백 수신
    # ============================================================

    @staticmethod
    def handle_callback(
        case_id: str,
        analysis_id: str,
        request: AnalysisCallbackRequest
    ) -> AnalysisCallbackResponse:

        stage = request.stage.upper()

        if case_id not in AnalysisCallbackService._callback_storage:
            AnalysisCallbackService._callback_storage[case_id] = {}

        if analysis_id not in AnalysisCallbackService._callback_storage[case_id]:
            AnalysisCallbackService._callback_storage[case_id][analysis_id] = {
                "SUMMARY": [],
                "TRANSCRIPT": [],
                "KEY_STATEMENT": [],
                "CONTRADICTION": [],
                "QUESTION": [],
                "VIDEO_EVENT": []
            }

        payload = request.payload

        # ✅ Pydantic 모델을 dict로 변환 (JSON 직렬화 보장)
        if isinstance(payload, list):
            converted = []
            for item in payload:
                if hasattr(item, "model_dump"):
                    converted.append(item.model_dump())
                elif hasattr(item, "dict"):
                    converted.append(item.dict())
                elif isinstance(item, dict):
                    converted.append(item)
                else:
                    converted.append(str(item))
            AnalysisCallbackService._callback_storage[case_id][analysis_id][stage].extend(converted)
        else:
            if hasattr(payload, "model_dump"):
                converted = payload.model_dump()
            elif hasattr(payload, "dict"):
                converted = payload.dict()
            elif isinstance(payload, dict):
                converted = payload
            else:
                converted = str(payload)
            AnalysisCallbackService._callback_storage[case_id][analysis_id][stage].append(converted)

        # ✅ 디스크 동기화
        AnalysisCallbackService._save_callbacks_to_disk()

        return AnalysisCallbackResponse(message="Callback received")

    # ============================================================
    # ✅ 누락됐던 메서드 복원
    # ============================================================

    @staticmethod
    def register_investigation_files(case_id: str, case_detail: dict, files: list):
        """
        investigation_file_service에서 호출하는 초기 등록 메서드
        분석 시작 전 storage 구조 미리 생성
        """

        if case_id not in AnalysisCallbackService._callback_storage:
            AnalysisCallbackService._callback_storage[case_id] = {}

        for f in files:
            analysis_id = f.get("analysis_id")
            if not analysis_id:
                continue

            if analysis_id not in AnalysisCallbackService._callback_storage[case_id]:
                AnalysisCallbackService._callback_storage[case_id][analysis_id] = {
                    "SUMMARY": [],
                    "TRANSCRIPT": [],
                    "KEY_STATEMENT": [],
                    "CONTRADICTION": [],
                    "QUESTION": [],
                    "VIDEO_EVENT": []
                }

        print(f"   📂 조사 파일 {len(files)}개 등록 (case_id: {case_id})")

        # ✅ 디스크 동기화
        AnalysisCallbackService._save_callbacks_to_disk()

    # ============================================================
    # 내부 분석 결과 저장 + 콜백 전송
    # ============================================================

    @staticmethod
    def register_analysis_result(
        analysis_id: str,
        result_data: Dict[str, Any]
    ):

        AnalysisCallbackService._analysis_results[analysis_id] = result_data
        print(f"   📦 분석 결과 등록: {analysis_id}")

        # ✅ 디스크 동기화
        AnalysisCallbackService._save_results_to_disk()

        from app.integrations.backend_callback_client import send_stage_callback_sync

        case_id = result_data.get("case_id")
        rd = result_data.get("result_data")

        if not case_id:
            return

        if isinstance(rd, list):
            for item in rd:
                if not isinstance(item, dict):
                    continue

                stage = item.get("stage")
                payload = item.get("payload", {})

                if not stage:
                    continue

                send_stage_callback_sync(
                    case_id=case_id,
                    analysis_id=analysis_id,
                    stage=stage,
                    payload=payload
                )

        elif isinstance(rd, dict):
            stage = rd.get("stage")
            payload = rd.get("payload", {})

            if stage:
                send_stage_callback_sync(
                    case_id=case_id,
                    analysis_id=analysis_id,
                    stage=stage,
                    payload=payload
                )

    # ============================================================
    # 조회용
    # ============================================================

    @staticmethod
    def get_video_events() -> List[Dict[str, Any]]:
        video_sources = []

        for analysis_id, data in AnalysisCallbackService._analysis_results.items():
            if data.get("file_type") != "VIDEO":
                continue

            origin_name = data.get("origin_name", f"영상_{analysis_id[:8]}")
            rd = data.get("result_data")

            if isinstance(rd, list):
                for item in rd:
                    if isinstance(item, dict) and item.get("stage") == "VIDEO_EVENT":
                        video_sources.append({
                            "analysis_id": analysis_id,
                            "origin_name": origin_name,
                            "events": item.get("payload", [])
                        })

        return video_sources

    @staticmethod
    def get_callbacks(case_id: str, analysis_id: str, stage: str = None):

        if case_id not in AnalysisCallbackService._callback_storage:
            return []

        if analysis_id not in AnalysisCallbackService._callback_storage[case_id]:
            return []

        if stage:
            return AnalysisCallbackService._callback_storage[case_id][analysis_id].get(stage.upper(), [])

        return AnalysisCallbackService._callback_storage[case_id][analysis_id]