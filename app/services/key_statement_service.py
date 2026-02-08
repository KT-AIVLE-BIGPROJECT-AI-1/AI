import json, uuid
from datetime import datetime, timezone

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def extract_key_statements(client, transcript_rows):
    conversation = "\n".join(
        f"[{t['speaker']}] {t['text']}" for t in transcript_rows
    )

    prompt = "녹취에서 수사상 핵심 진술을 추출하라."

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":conversation}],
        temperature=0.0,
        response_format={"type":"json_object"}
    )

    statements = json.loads(resp.choices[0].message.content)["statements"]

    key_statements = []
    for s in statements:
        matched = transcript_rows[0]
        key_statements.append({
            "statement_id": str(uuid.uuid4()),
            "analysis_id": matched["analysis_id"],
            "transcript_id": matched["transcript_id"],
            "transcript": matched["text"],
            "description": s["description"],
            "created_at": utc_now()
        })

    return key_statements
