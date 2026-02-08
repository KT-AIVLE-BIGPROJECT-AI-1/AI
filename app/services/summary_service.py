import json
from openai import OpenAI

def make_gpt_summary(client: OpenAI,
                     stt_result=None,
                     vdo_result=None,
                     doc_result=None,
                     img_result=None):

    combined = {
        "AUDIO": stt_result or {},
        "VIDEO": vdo_result or {},
        "DOCUMENT": doc_result or {},
        "IMAGE": img_result or {}
    }

    prompt = f"""
    아래는 동일 사건에 대한 여러 증거 분석 결과이다.

    {json.dumps(combined, ensure_ascii=False, indent=2)}

    다음 형식의 JSON만 생성하라:

    {{
      "summary": "증거 중심의 종합 요약 (4~6문장)",
      "confidence": 0.90~0.98 사이의 실수,
      "keywords": ["핵심 키워드 3~6개"]
    }}

    - 법적 판단 금지
    - 추정은 반드시 '추정' 명시
    """

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        response_format={"type": "json_object"}
    )

    return json.loads(resp.choices[0].message.content)


