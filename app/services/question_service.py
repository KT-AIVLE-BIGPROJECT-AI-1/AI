import json, uuid
from datetime import datetime, timezone

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def generate_questions(client, contradictions, key_statements):
    questions = []
    ks_map = {ks["statement_id"]: ks for ks in key_statements}

    for contra in contradictions:
        ks1 = ks_map.get(contra["statement_id_1"])
        ks2 = ks_map.get(contra["statement_id_2"])

        prompt = f"""
        다음 두 진술의 모순에 대한 질문 3개 생성:
        1) {ks1['transcript']}
        2) {ks2['transcript']}
        """

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}],
            temperature=0.0,
            response_format={"type":"json_object"}
        )

        qlist = json.loads(resp.choices[0].message.content)["questions"]

        for q in qlist:
            questions.append({
                "question_id": str(uuid.uuid4()),
                "contradiction_id": contra["contradiction_id"],
                "question_text": q["question_text"],
                "rationale": q["rationale"],
                "created_at": utc_now()
            })

    return questions
