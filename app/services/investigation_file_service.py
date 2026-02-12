# app/services/investigation_file_service.py
# ✅ 영상/음성 분석에 CASE 정보 전달 적용
# ✅ 교차분석 콜백 페이로드 ID 체계 개편:
#    CONTRADICTION → ct-N (statement_id_1, statement_id_2 → ks-N)
#    QUESTION → q-N (contradiction_id → ct-N)

import traceback
import itertools
import json
import re
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
                        presigned_url=presigned_url,
                        case_detail=case_detail_dict
                    )

                elif file_type == "AUDIO":
                    InvestigationFileService._analyze_audio(
                        case_id=case_id,
                        analysis_id=analysis_id,
                        origin_name=origin_name,
                        presigned_url=presigned_url,
                        case_detail=case_detail_dict
                    )

                else:
                    print(f"   ⚠️ 지원하지 않는 file_type: {file_type}")

                print(f"   ✅ 분석 완료: {origin_name}")

            except Exception as e:
                print(f"   ❌ 분석 실패: {origin_name} - {e}")
                traceback.print_exc()

                # 🔥 실패 시에도 반드시 콜백 전송 (백엔드가 PENDING 상태로 무한 대기하지 않도록)
                try:
                    # file_type별 기본 stage 결정
                    if file_type in ("DOCUMENT", "IMAGE"):
                        fail_result_data = {
                            "stage": "SUMMARY",
                            "payload": {
                                "summary": f"분석 실패: {str(e)}",
                                "confidence": 0.0,
                                "keywords": []
                            }
                        }
                    elif file_type == "VIDEO":
                        fail_result_data = [{
                            "stage": "VIDEO_EVENT",
                            "payload": [{
                                "start_time": 0.0,
                                "end_time": 0.0,
                                "event_type": "OTHER",
                                "event_description": f"분석 실패: {str(e)}"
                            }]
                        }]
                    elif file_type == "AUDIO":
                        fail_result_data = [{
                            "stage": "TRANSCRIPT",
                            "payload": [{
                                "temp_id": "err-1",
                                "speaker": "시스템",
                                "content": f"분석 실패: {str(e)}"
                            }]
                        }]
                    else:
                        fail_result_data = {
                            "stage": "SUMMARY",
                            "payload": {
                                "summary": f"지원하지 않는 파일 유형({file_type}) 분석 실패: {str(e)}",
                                "confidence": 0.0,
                                "keywords": []
                            }
                        }

                    AnalysisCallbackService.register_analysis_result(
                        analysis_id=analysis_id,
                        result_data={
                            "case_id": case_id,
                            "analysis_id": analysis_id,
                            "file_type": file_type,
                            "origin_name": origin_name,
                            "status": "FAILED",
                            "result_data": fail_result_data
                        }
                    )
                    print(f"   📤 실패 콜백 전송 완료: {origin_name}")
                except Exception as cb_err:
                    print(f"   ⚠️ 실패 콜백 전송도 실패: {cb_err}")

        # ============================================================
        # AUDIO 파일 2개 이상이면 교차 모순 탐지 + 콜백 전송
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
                print(f"   📄 문서 분석 중... (CASE 연관 분석)")
                text = document_analyzer.extract(file_path)
                summary_text = document_analyzer.analyze_one(text, case_detail, client)
            else:
                print(f"   🖼️ 이미지 분석 중... (CASE 연관 분석)")
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
        presigned_url: str,
        case_detail: dict = None
    ):
        """영상 분석 → VIDEO_EVENT 콜백 + 프레임 저장"""
        from app.utils.file_downloader import download_from_presigned_url, cleanup_temp_file
        from app.services.analysis_media_service import video_analyzer

        file_path = download_from_presigned_url(presigned_url)
        stored_frames = []  # 챗봇용 프레임 저장

        try:
            print(f"   🎥 영상 분석 중... (CASE 연관 분석)")
            video_event = video_analyzer.analyze_video(file_path, case_json=case_detail)

            # 프레임을 별도 추출하여 보관 (챗봇 Vision 질의용)
            stored_frames = video_event.pop("frames", [])
            if stored_frames:
                print(f"   🖼️ {len(stored_frames)}개 프레임 저장 (챗봇 Vision 질의용)")

            result_data = [video_event]
        except Exception as e:
            print(f"   ❌ 영상 분석 오류: {e}")
            result_data = [{
                "stage": "VIDEO_EVENT",
                "payload": [{"start_time": 0.0, "end_time": 0.0, "event_type": "OTHER", "event_description": f"분석 실패: {str(e)}"}]
            }]
        finally:
            cleanup_temp_file(file_path)

        # 콜백 전송 (result_data에는 텍스트만, frames는 별도 필드)
        AnalysisCallbackService.register_analysis_result(
            analysis_id=analysis_id,
            result_data={
                "case_id": case_id,
                "analysis_id": analysis_id,
                "file_type": "VIDEO",
                "origin_name": origin_name,
                "status": "COMPLETED",
                "result_data": result_data,
                "video_frames": stored_frames  # 챗봇용 프레임 (콜백에는 전송 안 됨)
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
        presigned_url: str,
        case_detail: dict = None
    ):
        """음성 분석 → TRANSCRIPT → KEY_STATEMENT → CONTRADICTION → QUESTION 콜백"""
        from app.utils.file_downloader import download_from_presigned_url, cleanup_temp_file
        from app.services.analysis_media_service import audio_analyzer, AnalysisMediaService

        file_path = download_from_presigned_url(presigned_url)

        try:
            print(f"   🎙️ 음성 분석 중... (CASE 연관 분석)")
            stages, current_source = audio_analyzer.analyze_audio(
                file_path,
                previous_sources=AnalysisMediaService._audio_sources,
                case_json=case_detail
            )
            AnalysisMediaService._audio_sources.append(current_source)
        except Exception as e:
            print(f"   ❌ 음성 분석 오류: {e}")
            stages = [{
                "stage": "TRANSCRIPT",
                "payload": [{"temp_id": "err-1", "speaker": "시스템", "content": f"분석 실패: {str(e)}"}]
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
    # 다중 AUDIO 교차 검증
    # ✅ 새 ID 체계: ct-N (statement_id_1/2), q-N (contradiction_id)
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
        # 1️⃣ AUDIO + KEY_STATEMENT + TRANSCRIPT(발화자 맵) 수집
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
            speaker_map = {}  # temp_id → speaker 매핑

            for item in rd:
                if isinstance(item, dict) and item.get("stage") == "KEY_STATEMENT":
                    key_statements = item.get("payload", [])
                if isinstance(item, dict) and item.get("stage") == "TRANSCRIPT":
                    transcript_payload = item.get("payload", [])
                    if isinstance(transcript_payload, list):
                        for t in transcript_payload:
                            if isinstance(t, dict) and t.get("temp_id"):
                                speaker_map[t["temp_id"]] = t.get("speaker", "미상")

            if not key_statements:
                continue

            audio_items.append({
                "analysis_id": analysis_id,
                "key_statements": key_statements,
                "speaker_map": speaker_map
            })

        if len(audio_items) < 2:
            print("🔎 다중 음성 교차 검증: AUDIO 2개 미만 → 스킵")
            return

        print(f"🔎 다중 음성 교차 검증 시작: AUDIO {len(audio_items)}개")

        llm = OpenAI(api_key=settings.OPENAI_API_KEY)

        # ============================================================
        # 2️⃣ LLM 모순 탐지 (새 ID 체계)
        # ============================================================

        seen_pairs = set()
        # analysis_id별 교차 모순/질문 수집
        added_contradictions_by_aid: Dict[str, List[Dict[str, Any]]] = {}
        added_questions_by_aid: Dict[str, List[Dict[str, Any]]] = {}

        # analysis_id별 기존 ct/q 개수 추적 (ID 채번용)
        existing_ct_count_by_aid: Dict[str, int] = {}
        existing_q_count_by_aid: Dict[str, int] = {}

        for item in audio_items:
            aid = item["analysis_id"]
            rd = AnalysisCallbackService._analysis_results.get(aid, {}).get("result_data", [])
            ct_count = 0
            q_count = 0
            for stage_item in rd:
                if isinstance(stage_item, dict):
                    if stage_item.get("stage") == "CONTRADICTION":
                        ct_count = len(stage_item.get("payload", []))
                    if stage_item.get("stage") == "QUESTION":
                        q_count = len(stage_item.get("payload", []))
            existing_ct_count_by_aid[aid] = ct_count
            existing_q_count_by_aid[aid] = q_count

        # 전체 speaker_map 통합 (ks temp_id → speaker)
        # KEY_STATEMENT의 transcript_id → TRANSCRIPT의 speaker
        global_ks_speaker_map = {}
        for item in audio_items:
            sm = item.get("speaker_map", {})
            for ks in item["key_statements"]:
                tr_id = ks.get("transcript_id", "")
                if tr_id and tr_id in sm:
                    global_ks_speaker_map[ks["temp_id"]] = sm[tr_id]

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

                    if pair_key in seen_pairs:
                        continue

                    seen_pairs.add(pair_key)

                    pair_checks += 1
                    if pair_checks > max_pair_checks:
                        print("⚠️ 교차 비교 상한 도달 → 중단")
                        break

                    sa_content = sa.get("content", sa.get("statement_text", ""))
                    sb_content = sb.get("content", sb.get("statement_text", ""))

                    prompt = f"""
아래 두 진술이 논리적으로 충돌하는지 판단하세요.

판단 기준:
- 시간 불일치
- 장소 불일치
- 행위자 불일치
- 원인/결과 모순
- 공모 여부 충돌

모순이면:
- type: TIME|LOCATION|ACTION|INTENT|CROSS_FILE
- description: 두 진술이 어떻게 모순되는지 설명
- question_for_a: 진술 A 관련자에게 할 질문
- question_for_b: 진술 B 관련자에게 할 질문
- rationale: 질문 근거

모순이 아니면 is_contradiction: false만 반환

진술 A ({sa_temp}):
{sa_content}

진술 B ({sb_temp}):
{sb_content}

반드시 JSON만:
{{
  "is_contradiction": true/false,
  "type": "...",
  "description": "...",
  "question_for_a": "...",
  "question_for_b": "...",
  "rationale": "..."
}}
"""

                    try:
                        resp = llm.chat.completions.create(
                            model="gpt-4o",
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0
                        )

                        raw = resp.choices[0].message.content.strip()
                        raw = re.sub(r"```json|```", "", raw).strip() if "```" in raw else raw

                        result = json.loads(raw)

                        if not result.get("is_contradiction"):
                            continue

                        c_type = result.get("type", "CROSS_FILE")
                        description = result.get("description", "")

                        # ── CONTRADICTION 생성 (새 ID 체계) ──
                        # 양쪽 analysis_id 모두에 동일한 모순 항목 추가
                        for aid in [a_id, b_id]:
                            ct_next = existing_ct_count_by_aid.get(aid, 0) + len(added_contradictions_by_aid.get(aid, [])) + 1
                            # ct prefix 결정: 해당 파일의 기존 prefix 확인
                            rd = AnalysisCallbackService._analysis_results.get(aid, {}).get("result_data", [])
                            ct_prefix = "ct"
                            for stage_item in rd:
                                if isinstance(stage_item, dict) and stage_item.get("stage") == "CONTRADICTION":
                                    existing_payload = stage_item.get("payload", [])
                                    if existing_payload and existing_payload[0].get("temp_id"):
                                        # 기존 prefix 추출 (예: "ct-1" → "ct", "ctB-1" → "ctB")
                                        existing_id = existing_payload[0]["temp_id"]
                                        ct_prefix = existing_id.rsplit("-", 1)[0]
                                        break

                            ct_id = f"{ct_prefix}-{ct_next}"

                            contra = {
                                "temp_id": ct_id,
                                "statement_id_1": sa_temp,
                                "statement_id_2": sb_temp,
                                "description": description,
                                "type": c_type
                            }
                            added_contradictions_by_aid.setdefault(aid, []).append(contra)

                            # ── QUESTION 생성 (새 ID 체계) ──
                            sa_speaker = global_ks_speaker_map.get(sa_temp, "미상")
                            sb_speaker = global_ks_speaker_map.get(sb_temp, "미상")
                            rationale = result.get("rationale", "교차 모순 확인 필요")

                            q_prefix = "q"
                            for stage_item in rd:
                                if isinstance(stage_item, dict) and stage_item.get("stage") == "QUESTION":
                                    existing_payload = stage_item.get("payload", [])
                                    if existing_payload and existing_payload[0].get("temp_id"):
                                        existing_id = existing_payload[0]["temp_id"]
                                        q_prefix = existing_id.rsplit("-", 1)[0]
                                        break

                            q_base = existing_q_count_by_aid.get(aid, 0) + len(added_questions_by_aid.get(aid, []))

                            # 진술A 관련자에게 질문
                            question_a = result.get("question_for_a", "")
                            if question_a:
                                q_next = q_base + 1
                                added_questions_by_aid.setdefault(aid, []).append({
                                    "temp_id": f"{q_prefix}-{q_next}",
                                    "contradiction_id": ct_id,
                                    "target": sa_speaker,
                                    "question": question_a,
                                    "rationale": rationale
                                })

                            # 진술B 관련자에게 질문
                            question_b = result.get("question_for_b", "")
                            if question_b:
                                q_next = q_base + len(added_questions_by_aid.get(aid, [])) - (0 if not question_a else 0) + 1
                                # 재계산: 현재까지 추가된 수
                                q_next = existing_q_count_by_aid.get(aid, 0) + len(added_questions_by_aid.get(aid, []))  + 1
                                added_questions_by_aid.setdefault(aid, []).append({
                                    "temp_id": f"{q_prefix}-{q_next}",
                                    "contradiction_id": ct_id,
                                    "target": sb_speaker,
                                    "question": question_b,
                                    "rationale": rationale
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

            # 중복 제거 (statement_id_1 + statement_id_2 조합)
            existing_contra_keys = set()
            for c in existing_contras:
                key = tuple(sorted([c.get("statement_id_1", ""), c.get("statement_id_2", "")]))
                existing_contra_keys.add(key)

            filtered_contras = []
            for c in new_contras:
                key = tuple(sorted([c.get("statement_id_1", ""), c.get("statement_id_2", "")]))
                if key not in existing_contra_keys:
                    filtered_contras.append(c)
                    existing_contra_keys.add(key)

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