from typing import Any, Dict

def build_case_context(case_json: Dict[str, Any], client=None) -> str:
    """
    문서/영상/음성 분석 시 공통으로 쓰는 사건 컨텍스트 생성 함수
    """

    if not case_json:
        return "[사건 정보 없음]"

    case_id = case_json.get("case_id", "")
    title = case_json.get("title", "")
    description = case_json.get("description", "")

    summary = case_json.get("summary", {})
    summary_text = "\n".join([
        f"- action: {summary.get('action','')}",
        f"- object: {summary.get('object','')}",
        f"- interaction: {summary.get('interaction','')}",
        f"- place: {summary.get('place','')}",
        f"- time: {summary.get('time','')}",
        f"- result: {summary.get('result','')}",
    ])

    context = f"""
[사건 기본 정보]
- case_id: {case_id}
- title: {title}

[사건 요약]
{summary_text}

[사건 설명]
{description}
"""

    return context.strip()
