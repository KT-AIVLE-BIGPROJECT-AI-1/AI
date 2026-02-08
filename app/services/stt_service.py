import json, uuid, requests
from datetime import datetime, timezone
from app.core.whisper_client import whisper
from openai import OpenAI

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def download_file(url: str) -> str:
    path = f"/tmp/{uuid.uuid4()}.wav"
    data = requests.get(url).content
    with open(path, "wb") as f:
        f.write(data)
    return path

def stt_only(audio_path: str):
    segments, _ = whisper.transcribe(
        audio_path, language="ko", vad_filter=False, beam_size=5
    )
    out = []
    for s in segments:
        if s.text:
            out.append({
                "start": round(float(s.start), 2),
                "end": round(float(s.end), 2),
                "text": s.text.strip()
            })
    return out

def gpt_segment_speakers(client: OpenAI, stt_segments):
    lines = [f"[{s['start']}~{s['end']}] {s['text']}" for s in stt_segments]

    system_prompt = """
    수사관=SPEAKER_1, 피의자=SPEAKER_2로 구분하여 의미 단위로 분리하라.
    """

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "\n".join(lines)}
        ],
        temperature=0.0,
        response_format={"type": "json_object"}
    )

    return json.loads(resp.choices[0].message.content)["dialogue"]

def build_transcript(analysis_id: str, dialogue: list):
    transcripts = []
    for d in dialogue:
        transcripts.append({
            "transcript_id": str(uuid.uuid4()),
            "analysis_id": analysis_id,
            "speaker": d.get("speaker",""),
            "text": d.get("text",""),
            "created_at": utc_now()
        })
    return transcripts
