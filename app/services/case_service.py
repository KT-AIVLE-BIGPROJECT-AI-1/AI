import json
from openai import OpenAI

def generate_case_summary(case_json: dict, client: OpenAI) -> dict:
    prompt = f"""다음 사건 정보를 분석하여 요약 정보를 추출하십시오.

사건 제목: {case_json.get('title', '')}
사건 유형: {case_json.get('type', '')}
발생 일시: {case_json.get('occurred_at', '')}
발생 장소: {case_json.get('location', '')}

사건 설명:
{case_json.get('description', '')}

위 정보를 바탕으로 다음 항목을 추출하여 JSON으로 응답하십시오:

{{
  "action": "범행 행위 설명",
  "object": "범행 대상/물품",
  "interaction": "상호작용",
  "place": "범행 장소 상세",
  "time": "범행 시간 정보",
  "result": "범행 결과"
}}

주의사항:
- 문서에 명시된 정보만 사용할 것
- 정보가 없으면 빈 문자열로 표시
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content.strip()
        summary = json.loads(content)
        return summary

    except Exception as e:
        print(f"❌ summary 생성 실패: {e}")
        return {
            "action": "",
            "object": "",
            "interaction": "",
            "place": "",
            "time": "",
            "result": ""
        }


def summarize_case(body: dict, client: OpenAI) -> dict:
    summary = generate_case_summary(body, client)
    return {"summary": summary}