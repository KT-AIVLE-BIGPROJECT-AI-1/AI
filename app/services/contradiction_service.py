import json, uuid
from datetime import datetime, timezone

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def detect_contradictions(client, key_statements):
    if len(key_statements) < 2:
        return []

    numbered = "\n".join(
        f"[{i+1}] {ks['transcript']}" for i, ks in enumerate(key_statements)
    )

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":numbered}],
        temperature=0.0,
        response_format={"type":"json_object"}
    )

    raw = json.loads(resp.choices[0].message.content)["contradictions"]

    results = []
    for c in raw:
        ks1 = key_statements[c["statement_1_index"]-1]
        ks2 = key_statements[c["statement_2_index"]-1]

        results.append({
            "contradiction_id": str(uuid.uuid4()),
            "analysis_id": ks1["analysis_id"],
            "statement_id_1": ks1["statement_id"],
            "statement_id_2": ks2["statement_id"],
            "type": c["type"],
            "description": c["description"],
            "created_at": utc_now()
        })
    return results
