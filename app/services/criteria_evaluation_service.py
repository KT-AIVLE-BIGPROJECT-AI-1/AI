import json, re
from openai import OpenAI

def evaluate_criterion_with_single_evidence(
    client: OpenAI,
    criterion_text: str,
    single_evidence: dict
) -> dict:

    prompt = f"""
당신은 형법 구성요건 충족 여부를 평가하는 법무 보조 AI입니다.

[단일 증거 분석 결과]
{json.dumps(single_evidence, ensure_ascii=False, indent=2)}

[법리 판단 기준]
{criterion_text}

=== 출력 규칙 ===
아래 JSON만 출력:

{{
  "status": "SATISFIED | UNSATISFIED | INSUFFICIENT",
  "reason": "2~3문장",
  "evidence_gap": "필요 증거 또는 null"
}}
"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=800
    )

    raw = (resp.choices[0].message.content or "").strip()
    raw = re.sub(r"```(?:json)?|```", "", raw).strip()

    try:
        parsed = json.loads(raw)
    except:
        return {
            "status": "INSUFFICIENT",
            "reason": raw,
            "evidence_gap": "AI 출력 파싱 실패"
        }

    return {
        "status": parsed.get("status", "INSUFFICIENT"),
        "reason": parsed.get("reason", ""),
        "evidence_gap": parsed.get("evidence_gap")
    }
