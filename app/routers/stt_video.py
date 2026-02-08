# app/routers/stt_video.py

from fastapi import APIRouter, BackgroundTasks
import uuid, requests
from openai import OpenAI

from app.core.callback_sender import send_callback
from app.services.stt_service import download_file, stt_only, gpt_segment_speakers, build_transcript
from app.services.key_statement_service import extract_key_statements
from app.services.contradiction_service import detect_contradictions
from app.services.question_service import generate_questions
from app.services.video_event_service import download_video, CrimeDetector
from app.services.summary_service import make_gpt_summary
from app.services.payload_mapper import (
    map_transcript_for_callback,
    map_key_statements_for_callback,
    map_contradictions_for_callback,
    map_questions_for_callback,
    map_video_events_for_callback
)
from app.models.analysis_schema import AnalysisUploadRequest
from app.services.video_event_service import download_video, CrimeDetector


router = APIRouter(prefix="/analysis", tags=["STT-Video"])
client = OpenAI()

def run_stt_video_background(req: AnalysisUploadRequest):

    case_id = req.case_detail.case_id

    for f in req.investigation_files:
        analysis_id = f.job_id  # BE가 준 ID 사용

        if f.file_type == "AUDIO":
            audio_path = download_file(f.presigned_url)

            # 1) STT + 화자분리
            segments = stt_only(audio_path)
            dialogue = gpt_segment_speakers(client, segments)
            transcripts = build_transcript(analysis_id, dialogue)

            send_callback(
                case_id, analysis_id, "TRANSCRIPT",
                map_transcript_for_callback(transcripts)
            )

            # 2) KEY_STATEMENT
            key_statements = extract_key_statements(client, transcripts)
            send_callback(
                case_id, analysis_id, "KEY_STATEMENT",
                map_key_statements_for_callback(key_statements)
            )

            # 3) CONTRADICTION
            contradictions = detect_contradictions(client, key_statements)
            send_callback(
                case_id, analysis_id, "CONTRADICTION",
                map_contradictions_for_callback(contradictions)
            )

            # 4) QUESTION
            questions = generate_questions(client, contradictions, key_statements)
            send_callback(
                case_id, analysis_id, "QUESTION",
                map_questions_for_callback(questions)
            )

            # 5) SUMMARY (종합 요약)
            summary = make_gpt_summary(
                client=client,
                stt_result={
                    "transcripts": transcripts,
                    "key_statements": key_statements,
                    "contradictions": contradictions,
                    "questions": questions
                }
            )

            send_callback(case_id, analysis_id, "SUMMARY", summary)

        elif f.file_type == "VIDEO":
            video_path = download_video(f.presigned_url)
            detector = CrimeDetector(client)
            video_events = detector.analyze(video_path, f.origin_name, req.case_detail.dict())

            send_callback(
                case_id, analysis_id, "VIDEO_EVENT",
                map_video_events_for_callback(video_events)
            )

            summary = make_gpt_summary(
                client=client,
                vdo_result={"video_events": video_events}
            )
            send_callback(case_id, analysis_id, "SUMMARY", summary)

@router.post("/stt-video")
def analyze_stt_video(req: AnalysisUploadRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_stt_video_background, req)
    return {"status": "STARTED"}
