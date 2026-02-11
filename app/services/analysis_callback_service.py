# app/services/analysis_callback_service.py

from typing import Dict, List, Any
from app.models.analysis_callback_schema import (
    AnalysisCallbackRequest,
    AnalysisCallbackResponse
)


class AnalysisCallbackService:

    _callback_storage: Dict[str, Dict[str, Dict[str, List[Dict[str, Any]]]]] = {}
    _analysis_results: Dict[str, Dict[str, Any]] = {}

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

        if isinstance(payload, list):
            AnalysisCallbackService._callback_storage[case_id][analysis_id][stage].extend(payload)
        else:
            AnalysisCallbackService._callback_storage[case_id][analysis_id][stage].append(payload)

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
