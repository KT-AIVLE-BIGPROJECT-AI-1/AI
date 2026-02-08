# app/services/payload_mapper.py

def map_transcript_for_callback(transcripts: list) -> dict:
    if not transcripts:
        return {"content": ""}
    return {"content": transcripts[0]["text"]}

def map_key_statements_for_callback(key_statements: list) -> list:
    payload = []
    for i, ks in enumerate(key_statements):
        payload.append({
            "tempId": f"ks-{i+1}",
            "content": ks["description"]
        })
    return payload

def map_contradictions_for_callback(contradictions: list) -> list:
    payload = []
    for i, c in enumerate(contradictions):
        payload.append({
            "statementTempId": f"ks-{i+1}",
            "description": c["description"],
            "type": c["type"]
        })
    return payload

def map_questions_for_callback(questions: list) -> list:
    payload = []
    for i, q in enumerate(questions):
        payload.append({
            "statementTempId": f"ks-{i+1}",
            "question": q["question_text"]
        })
    return payload

def map_video_events_for_callback(video_events: list) -> list:
    payload = []
    for e in video_events:
        payload.append({
            "startTime": e["start_time"],
            "endTime": e["end_time"],
            "eventType": e["event_type"],
            "description": e["event_description"]
        })
    return payload
