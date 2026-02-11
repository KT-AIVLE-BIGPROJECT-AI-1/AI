# app/services/investigation_file_service.py

import traceback
import itertools
import json
from datetime import datetime, timezone
from typing import Dict, List, Any, Tuple

from openai import OpenAI

from app.config import settings
from app.models.investigation_file_schema import (
    InvestigationFilesRequest,
    InvestigationFilesResponse,
    AnalysisTarget
)
from app.services.analysis_callback_service import AnalysisCallbackService
from app.integrations.backend_callback_client import send_stage_callback_sync


class InvestigationFileService:

    @staticmethod
    def schedule_analysis(request: InvestigationFilesRequest) -> InvestigationFilesResponse:
        """
        파일 등록 (즉시 PENDING 반환)
        실제 분석은 run_analysis_pipeline()에서 백그라운드 실행
        """
        print("\n" + "=" * 70)
        print("📂 수사자료 분석 요청 수신")
        print("=" * 70)
        print(f"사건: {request.case_detail.title} ({request.case_detail.case_id})")
        print(f"파일 수: {len(request.investigation_files)}개")
        print(f"법리 기준: {len(request.legal_criteria)}개")

        targets = []
        callback_files = []

        for file_info in request.investigation_files:
            targets.append(AnalysisTarget(
                origin_name=file_info.origin_name,
                file_type=file_info.file_type
            ))
            callback_files.append({
                "analysis_id": file_info.analysis_id,
                "file_type": file_info.file_type,
                "origin_name": file_info.origin_name
            })
            print(f"  [{file_info.analysis_id}] {file_info.origin_name} ({file_info.file_type})")

        # 콜백 서비스에 파일 등록
        AnalysisCallbackService.register_investigation_files(
            case_id=request.case_detail.case_id,
            case_detail=request.case_detail.model_dump(),
            files=callback_files
        )

        print("=" * 70)
        print(f"✅ {len(targets)}개 파일 등록 완료 → 백그라운드 분석 시작 예정")
        print("=" * 70)

        return InvestigationFilesResponse(status="PENDING", targets=targets)

    @staticmethod
    def run_analysis_pipeline(request: InvestigationFilesRequest):
        """
        백그라운드 분석 파이프라인
        file_type별로 분기하여 분석 실행 → 완료 시 콜백 자동 전송
        """
        print("\n" + "=" * 70)
        print("🚀 백그라운드 분석 파이프라인 시작")
        print("=" * 70)

        case_id = request.case_detail.case_id
        case_detail_dict = request.case_detail.model_dump()
        now_iso = datetime.now(timezone.utc).isoformat()

        for file_info in request.investigation_files:
            file_type = file_info.file_type.upper()
            analysis_id = file_info.analysis_id
            origin_name = file_info.origin_name
            presigned_url = file_info.presigned_url

            print(f"\n{'─' * 50}")
            print(f"📄 분석 시작: {origin_name} ({file_type})")
            print(f"   analysis_id: {analysis_id}")
            print(f"{'─' * 50}")

            try:
                if file_type in ("DOCUMENT", "IMAGE"):
                    InvestigationFileService._analyze_doc_img(
                        case_id=case_id,
                        analysis_id=analysis_id,
                        file_type=file_type,
                        origin_name=origin_name,
                        presigned_url=presigned_url,
                        case_detail=case_detail_dict
                    )

                elif file_type == "VIDEO":
                    InvestigationFileService._analyze_video(
                        case_id=case_id,
                        analysis_id=analysis_id,
                        origin_name=origin_name,
                        presigned_url=presigned_url
                    )

                elif file_type == "AUDIO":
                    InvestigationFileService._analyze_audio(
                        case_id=case_id,
                        analysis_id=analysis_id,
                        origin_name=origin_name,
                        presigned_url=presigned_url
                    )

                else:
                    print(f"   ⚠️ 지원하지 않는 file_type: {file_type}")

                print(f"   ✅ 분석 완료: {origin_name}")

            except Exception as e:
                print(f"   ❌ 분석 실패: {origin_name} - {e}")
                traceback.print_exc()

        # ============================================================
        # ✅ (추가) AUDIO 파일 2개 이상이면 교차 모순 탐지 + 콜백 전송
        # ============================================================
        try:
            InvestigationFileService._cross_audio_contradiction_analysis(case_id=case_id)
        except Exception as e:
            print(f"   ⚠️ 음성 교차 검증 실패(무시): {e}")
            traceback.print_exc()

        print("\n" + "=" * 70)
        print("🏁 백그라운드 분석 파이프라인 완료")
        print("=" * 70)

    # ============================================================
    # DOCUMENT / IMAGE 분석
    # ============================================================

    @staticmethod
    def _analyze_doc_img(
        case_id: str,
        analysis_id: str,
        file_type: str,
        origin_name: str,
        presigned_url: str,
        case_detail: dict
    ):
        """문서/이미지 분석 → SUMMARY 콜백"""
        from app.utils.file_downloader import download_from_presigned_url, cleanup_temp_file
        from app.services.analysis_service import document_analyzer, image_analyzer, extract_keywords, client

        file_path = download_from_presigned_url(presigned_url)

        try:
            if file_type == "DOCUMENT":
                print(f"   📄 문서 분석 중...")
                text = document_analyzer.extract(file_path)
                summary_text = document_analyzer.analyze_one(text, case_detail, client)
            else:
                print(f"   🖼️ 이미지 분석 중...")
                summary_text = image_analyzer.analyze_one(file_path, case_detail, client)

            keywords = extract_keywords(summary_text)

            result_data = {
                "stage": "SUMMARY",
                "payload": {
                    "summary": summary_text,
                    "confidence": 0.93,
                    "keywords": keywords
                }
            }

            print(f"   📝 요약: {summary_text[:80]}...")
            print(f"   🏷️ 키워드: {keywords}")

        except Exception as e:
            print(f"   ❌ 분석 오류: {e}")
            result_data = {
                "stage": "SUMMARY",
                "payload": {
                    "summary": f"분석 실패: {str(e)}",
                    "confidence": 0.0,
                    "keywords": []
                }
            }

        finally:
            cleanup_temp_file(file_path)

        # 콜백 전송
        AnalysisCallbackService.register_analysis_result(
            analysis_id=analysis_id,
            result_data={
                "case_id": case_id,
                "analysis_id": analysis_id,
                "file_type": file_type,
                "origin_name": origin_name,
                "status": "COMPLETED",
                "result_data": result_data
            }
        )

    # ============================================================
    # VIDEO 분석
    # ============================================================

    @staticmethod
    def _analyze_video(
        case_id: str,
        analysis_id: str,
        origin_name: str,
        presigned_url: str
    ):
        """영상 분석 → VIDEO_EVENT 콜백"""
        from app.utils.file_downloader import download_from_presigned_url, cleanup_temp_file
        from app.services.analysis_media_service import video_analyzer

        file_path = download_from_presigned_url(presigned_url)

        try:
            print(f"   🎥 영상 분석 중...")
            video_event = video_analyzer.analyze_video(file_path)
            result_data = [video_event]
        except Exception as e:
            print(f"   ❌ 영상 분석 오류: {e}")
            result_data = [{
                "stage": "VIDEO_EVENT",
                "payload": [{"start_time": 0.0, "end_time": 0.0, "event_type": "OTHER", "event_description": f"분석 실패: {str(e)}"}]
            }]
        finally:
            cleanup_temp_file(file_path)

        # 콜백 전송
        AnalysisCallbackService.register_analysis_result(
            analysis_id=analysis_id,
            result_data={
                "case_id": case_id,
                "analysis_id": analysis_id,
                "file_type": "VIDEO",
                "origin_name": origin_name,
                "status": "COMPLETED",
                "result_data": result_data
            }
        )

    # ============================================================
    # AUDIO 분석
    # ============================================================

    @staticmethod
    def _analyze_audio(
        case_id: str,
        analysis_id: str,
        origin_name: str,
        presigned_url: str
    ):
        """음성 분석 → TRANSCRIPT → KEY_STATEMENT → CONTRADICTION → QUESTION 콜백"""
        from app.utils.file_downloader import download_from_presigned_url, cleanup_temp_file
        from app.services.analysis_media_service import audio_analyzer, AnalysisMediaService

        file_path = download_from_presigned_url(presigned_url)

        try:
            print(f"   🎙️ 음성 분석 중...")
            stages, current_source = audio_analyzer.analyze_audio(
                file_path,
                previous_sources=AnalysisMediaService._audio_sources
            )
            AnalysisMediaService._audio_sources.append(current_source)
        except Exception as e:
            print(f"   ❌ 음성 분석 오류: {e}")
            stages = [{
                "stage": "TRANSCRIPT",
                "payload": {"content": [{"speaker": "시스템", "content": f"분석 실패: {str(e)}"}]}
            }]
        finally:
            cleanup_temp_file(file_path)

        # 콜백 전송
        AnalysisCallbackService.register_analysis_result(
            analysis_id=analysis_id,
            result_data={
                "case_id": case_id,
                "analysis_id": analysis_id,
                "file_type": "AUDIO",
                "origin_name": origin_name,
                "status": "COMPLETED",
                "result_data": stages
            }
        )

    # ============================================================
    # ✅ (추가) 다중 AUDIO 교차 검증
    # ============================================================

    @staticmethod
    def _cross_audio_contradiction_analysis(case_id: str):
        """
        AUDIO 파일 2개 이상일 때:
        - 각 파일의 KEY_STATEMENT 수집
        - 의미 기반 LLM 모순 탐지
        - 중복 제거
        - 각 파일의 CONTRADICTION / QUESTION에 '추가'
        - 추가분만 콜백 전송
        """

        audio_items: List[Dict[str, Any]] = []

        # ============================================================
        # 1️⃣ AUDIO + KEY_STATEMENT 수집
        # ============================================================
        for analysis_id, data in AnalysisCallbackService._analysis_results.items():

            if data.get("case_id") != case_id:
                continue

            if data.get("file_type") != "AUDIO":
                continue

            rd = data.get("result_data", [])
            if not isinstance(rd, list):
                continue

            key_statements = []

            for item in rd:
                if isinstance(item, dict) and item.get("stage") == "KEY_STATEMENT":
                    key_statements = item.get("payload", [])
                    break

            if not key_statements:
                continue

            audio_items.append({
                "analysis_id": analysis_id,
                "key_statements": key_statements
            })

        if len(audio_items) < 2:
            print("🔎 다중 음성 교차 검증: AUDIO 2개 미만 → 스킵")
            return

        print(f"🔎 다중 음성 교차 검증 시작: AUDIO {len(audio_items)}개")

        llm = OpenAI(api_key=settings.OPENAI_API_KEY)

        # ============================================================
        # 2️⃣ LLM 모순 탐지 (중복 방지 구조)
        # ============================================================

        seen_pairs = set()
        added_contradictions_by_aid: Dict[str, List[Dict[str, Any]]] = {}
        added_questions_by_aid: Dict[str, List[Dict[str, Any]]] = {}

        max_pair_checks = 800
        pair_checks = 0

        for a, b in itertools.combinations(audio_items, 2):

            a_id = a["analysis_id"]
            b_id = b["analysis_id"]

            for sa in a["key_statements"]:
                for sb in b["key_statements"]:

                    sa_temp = sa.get("temp_id")
                    sb_temp = sb.get("temp_id")

                    if not sa_temp or not sb_temp:
                        continue

                    pair_key = tuple(sorted([f"{a_id}:{sa_temp}", f"{b_id}:{sb_temp}"]))

                    # 🔥 이미 검사한 쌍이면 스킵
                    if pair_key in seen_pairs:
                        continue

                    seen_pairs.add(pair_key)

                    pair_checks += 1
                    if pair_checks > max_pair_checks:
                        print("⚠️ 교차 비교 상한 도달 → 중단")
                        break

                    prompt = f"""
아래 두 진술이 논리적으로 충돌하는지 판단하세요.

판단 기준:
- 시간 불일치
- 장소 불일치
- 행위자 불일치
- 원인/결과 모순
- 공모 여부 충돌

모순이면:
- type: TIME|LOCATION|ACTION|INTENT|OTHER
- description: 1문장 설명
- question: 추가 확인 질문 1개

모순이 아니면 빈 JSON 반환

진술 A:
{sa.get("content")}

진술 B:
{sb.get("content")}

반드시 JSON만:
{{
  "is_contradiction": true/false,
  "type": "...",
  "description": "...",
  "question": "..."
}}
"""

                    try:
                        resp = llm.chat.completions.create(
                            model="gpt-4o",
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0
                        )

                        raw = resp.choices[0].message.content.strip()

                        result = json.loads(raw)

                        if not result.get("is_contradiction"):
                            continue

                        contradiction_obj = {
                            "statement_temp_id": f"{a_id}:{sa_temp}",
                            "related_statement_id": f"{b_id}:{sb_temp}",
                            "description": result.get("description"),
                            "type": result.get("type", "OTHER")
                        }

                        question_obj = {
                            "statement_temp_id": f"{a_id}:{sa_temp}",
                            "question": result.get("question")
                        }

                        added_contradictions_by_aid.setdefault(a_id, []).append(contradiction_obj)
                        added_contradictions_by_aid.setdefault(b_id, []).append({
                            "statement_temp_id": f"{b_id}:{sb_temp}",
                            "related_statement_id": f"{a_id}:{sa_temp}",
                            "description": result.get("description"),
                            "type": result.get("type", "OTHER")
                        })

                        added_questions_by_aid.setdefault(a_id, []).append(question_obj)
                        added_questions_by_aid.setdefault(b_id, []).append({
                            "statement_temp_id": f"{b_id}:{sb_temp}",
                            "question": f"상대 진술({a_id}:{sa_temp})과 상충합니다. 설명해주시겠습니까?"
                        })

                    except Exception:
                        continue

                if pair_checks > max_pair_checks:
                    break

        # ============================================================
        # 3️⃣ 실제 stage에 "중복 없이" 추가
        # ============================================================

        for analysis_id, data in AnalysisCallbackService._analysis_results.items():

            if data.get("case_id") != case_id:
                continue

            if data.get("file_type") != "AUDIO":
                continue

            rd = data.get("result_data")
            if not isinstance(rd, list):
                continue

            new_contras = added_contradictions_by_aid.get(analysis_id, [])
            new_qs = added_questions_by_aid.get(analysis_id, [])

            if not new_contras and not new_qs:
                continue

            # 기존 payload 수집
            existing_contras = []
            existing_qs = []

            for item in rd:
                if item.get("stage") == "CONTRADICTION":
                    existing_contras = item.get("payload", [])
                if item.get("stage") == "QUESTION":
                    existing_qs = item.get("payload", [])

            # 🔥 중복 제거
            existing_ids = {
                (c.get("statement_temp_id"), c.get("related_statement_id"))
                for c in existing_contras
            }

            filtered_contras = [
                c for c in new_contras
                if (c.get("statement_temp_id"), c.get("related_statement_id")) not in existing_ids
            ]

            if filtered_contras:
                for item in rd:
                    if item.get("stage") == "CONTRADICTION":
                        item["payload"].extend(filtered_contras)
                        break
                else:
                    rd.append({"stage": "CONTRADICTION", "payload": filtered_contras})

                send_stage_callback_sync(
                    case_id=case_id,
                    analysis_id=analysis_id,
                    stage="CONTRADICTION",
                    payload=filtered_contras
                )

            if new_qs:
                for item in rd:
                    if item.get("stage") == "QUESTION":
                        item["payload"].extend(new_qs)
                        break
                else:
                    rd.append({"stage": "QUESTION", "payload": new_qs})

                send_stage_callback_sync(
                    case_id=case_id,
                    analysis_id=analysis_id,
                    stage="QUESTION",
                    payload=new_qs
                )

        print("✅ 다중 음성 교차 검증 완료")
