# # app/criteria.py
# from typing import List, Dict, Any
# from app.llm_utils import call_llm_json

# def extract_and_filter_criteria(reranked, case_summary, legal_issue, keywords):
#     all_criteria=[]
#     for p in reranked:
#         prompt=f"""
# 판례에서 판단 요소 추출
# JSON: {{"criteria":[]}}
# 본문:{p["body"]}
# """
#         res=call_llm_json(prompt)
#         for c in res.get("criteria",[]):
#             all_criteria.append({
#                 "precedent_case_no": p["precedent_case_no"],
#                 "criterion_text": str(c)
#             })
#     return all_criteria

# def derive_common_criteria(all_criteria):
#     prompt=f"""
# 공통 기준 통합
# JSON: {{"common_criteria":[]}}
# 목록:{all_criteria}
# """
#     return call_llm_json(prompt)

# def expand_criteria_from_anchor(common_criteria, case_summary, legal_issue):
#     prompt=f"""
# anchor 기준 확장
# JSON: {{"expanded_criteria":[]}}
# """
#     return call_llm_json(prompt).get("expanded_criteria",[])

# # def make_criteria_rows(common_criteria, precedent_bodies, expanded):
# #     rows=[]
# #     for c in common_criteria.get("common_criteria",[]):
# #         rows.append({
# #             "criterion_text": c.get("criterion_text"),
# #             "precedent_case_no": c.get("precedent_case_nos",[None])[0],
# #             "precedent_decision_date": None
# #         })
# #     for e in expanded:
# #         rows.append({
# #             "criterion_text": e,
# #             "precedent_case_no": None,
# #             "precedent_decision_date": None
# #         })
# #     return rows

# # app/criteria.py

# # app/criteria.py

# # app/criteria.py

# from collections import defaultdict

# def make_criteria_rows(common_criteria, precedent_bodies, expanded):

#     temp_map = defaultdict(lambda: {
#         "criterion_text": None,
#         "precedent_case_no": [],
#         "precedent_decision_date": []
#     })

#     # ==============================
#     # ① anchor 기준 처리
#     # ==============================
#     for c in common_criteria.get("common_criteria", []):

#         # 혹시 str이 섞여 있으면 안전 처리
#         if isinstance(c, str):
#             key = c
#             temp_map[key]["criterion_text"] = key
#             continue

#         text = c.get("criterion_text")
#         key = text

#         temp_map[key]["criterion_text"] = text

#         case_nos = c.get("precedent_case_nos", [])

#         if case_nos:
#             for case_no in case_nos:
#                 # 선고일자 찾기
#                 decision_date = None
#                 for pb in precedent_bodies:
#                     if pb.get("precedent_case_no") == case_no:
#                         decision_date = pb.get("precedent_decision_date")
#                         break

#                 temp_map[key]["precedent_case_no"].append(case_no)
#                 temp_map[key]["precedent_decision_date"].append(decision_date)

#     # ==============================
#     # ② expanded 기준 처리 (문자열)
#     # ==============================
#     for e in expanded:
#         if not isinstance(e, str):
#             continue

#         key = e
#         temp_map[key]["criterion_text"] = key
#         # expanded 기준은 판례번호 없음 → 빈 리스트 유지

#     # ==============================
#     # ③ 최종 정리 (빈 리스트 → null 처리)
#     # ==============================
#     rows = []
#     for v in temp_map.values():

#         row = {
#             "criterion_text": v["criterion_text"],
#             "precedent_case_no": v["precedent_case_no"] if v["precedent_case_no"] else None,
#             "precedent_decision_date": v["precedent_decision_date"] if v["precedent_decision_date"] else None
#         }

#         rows.append(row)

#     return rows

# app/criteria.py
from typing import List, Dict, Any, Optional
from collections import defaultdict
from app.llm_utils import call_llm_json


# ======================================================
# 0️⃣ 공통 유틸: criterion_text 안전 추출
# ======================================================

def _safe_text(obj: Any) -> str:
    """
    어떤 타입이 와도 반드시 문자열을 반환
    """
    if obj is None:
        return ""

    if isinstance(obj, dict):
        return str(obj.get("criterion_text"))

    # Pydantic 객체 가능성
    if hasattr(obj, "criterion_text"):
        return str(getattr(obj, "criterion_text"))

    # fallback
    return str(obj)


# ======================================================
# 1️⃣ 판례별 기준 추출
# ======================================================

# def extract_and_filter_criteria(reranked, case_summary, legal_issue, keywords):
#     all_criteria = []

#     for p in reranked:
#         prompt = f"""
#         판례에서 판단 요소 추출
#         JSON: {{"criteria": []}}
#         본문: {p["body"]}
#         """
#         res = call_llm_json(prompt)

#         for c in res.get("criteria", []):
#             all_criteria.append({
#                 "precedent_case_no": p["precedent_case_no"],
#                 "criterion_text": _safe_text(c)
#             })

            

#     return all_criteria
def extract_and_filter_criteria(reranked, case_summary, legal_issue, keywords):
    all_criteria = []

    # 🚫 절대 들어오면 안 되는 기준들 (양형/개인사/무관 요소)
    BLACKLIST = [
        "범죄 경력", "전과", "동종전과", "초범",
        "음주운전", "음주 여부",
        "양형", "반성", "합의", "선처", "탄원", "피해회복",
        "직업", "가정사", "성격"
    ]

    for p in reranked:
        prompt = f"""
당신은 형사 판례에서 **구성요건 판단에 직접 쓰인 사실요소만** 추출한다.

허용 범위(이것만 뽑을 것):
- 행위: 어떤 유형력을 행사했는지
- 객체: 타인의 재물인지 여부
- 결과: 손괴 또는 효용 침해가 있었는지
- 인식/고의: 손괴 의사 또는 인식이 있었는지
- 인과: 행위와 결과의 연결관계

절대 금지(하나라도 포함 시 해당 항목 삭제):
- 전과/범죄경력/음주 관련 요소
- 양형 사유(반성, 합의, 선처, 탄원 등)
- 다른 범죄(폭행, 음주운전 등)의 판단요소
- 인적사항(직업, 가정사, 성격 등)

출력은 **체크리스트가 아니라**
“판례에서 드러난 사실요소 문장”만 간단히 나열.

JSON:
{{ "criteria": [] }}

[법리 쟁점]
{legal_issue["issue_name"]}
{legal_issue["related_law"]}

[판례 본문]
{p["body"]}
"""
        res = call_llm_json(prompt)

        # === 🔍 디버그용 (필요하면 켜두세요) ===
        print(f"DEBUG criteria from case {p['precedent_case_no']}: {res}")

        for c in res.get("criteria", []):
            text = _safe_text(c).strip()

            # 빈 값 스킵
            if not text:
                continue

            # 블랙리스트 필터
            if any(b in text for b in BLACKLIST):
                continue

            all_criteria.append({
                "precedent_case_no": p["precedent_case_no"],
                "criterion_text": text
            })

    print("DEBUG all_criteria:", all_criteria)
    return all_criteria



# ======================================================
# 2️⃣ 공통 기준 통합
# ======================================================

def derive_common_criteria(all_criteria):
    prompt = f"""
다음은 여러 판례에서 각각 추출된 판단 요소 목록이다.

작업:
1. 서로 다른 표현이라도 동일한 의미면 통합
2. 반드시 판례번호를 함께 유지
3. 아래 JSON 형식을 **반드시 따를 것**

⚠️ 필수 형식 규칙:
- common_criteria는 반드시 리스트
- 각 항목은 반드시:
  {{
    "criterion_text": "...",
    "precedent_case_nos": []
  }}
- 판례번호가 없으면 빈 리스트

출력(JSON):
{{
  "common_criteria": [
    {{
      "criterion_text": "",
      "precedent_case_nos": []
    }}
  ]
}}

[판례별 판단 요소 목록]
{all_criteria}
"""
    return call_llm_json(prompt)



# ======================================================
# 3️⃣ anchor 기준 확장
# ======================================================

def expand_criteria_from_anchor(common_criteria, case_summary, legal_issue):
    prompt = f"""
anchor 기준 확장
JSON: {{"expanded_criteria": []}}
"""
    result = call_llm_json(prompt)
    return result.get("expanded_criteria", [])


# ======================================================
# 4️⃣ 🔥 핵심: 최종 출력 고정형 변환 함수
# ======================================================

def make_criteria_rows(common_criteria, precedent_bodies, expanded):
    """
    최종 출력 형태를 '항상 고정'하는 함수

    출력 규칙:
    {
      "criterion_text": str,
      "precedent_case_no": [str] | null,
      "precedent_decision_date": [str] | null
    }
    """

    temp_map = defaultdict(lambda: {
        "criterion_text": None,
        "precedent_case_no": [],
        "precedent_decision_date": []
    })

    # --------------------------------------------------
    # ① anchor 기준 처리
    # --------------------------------------------------
    for c in common_criteria.get("common_criteria", []):

        # criterion_text 안전 추출
        text = _safe_text(c)
        key = str(text)   # 🔥 반드시 문자열 키

        temp_map[key]["criterion_text"] = text

        # 판례번호 리스트
        case_nos = []

        if isinstance(c, dict):
            case_nos = (
                c.get("precedent_case_nos")
                or c.get("precedent_case_no")
                or c.get("precedent_ids")
                or []
            )

        # 문자열 하나만 온 경우 리스트로 감싸기
        if isinstance(case_nos, str):
            case_nos = [case_nos]


        for case_no in case_nos:

            # 선고일자 찾기
            decision_date = None
            for pb in precedent_bodies:
                if pb.get("precedent_case_no") == case_no:
                    decision_date = pb.get("precedent_decision_date")
                    break

            temp_map[key]["precedent_case_no"].append(str(case_no))
            temp_map[key]["precedent_decision_date"].append(decision_date)

    # --------------------------------------------------
    # ② expanded 기준 처리 (문자열)
    # --------------------------------------------------
    for e in expanded:
        text = _safe_text(e)
        key = str(text)
        temp_map[key]["criterion_text"] = text
        # expanded 기준은 판례번호 없음 → 빈 리스트 유지

    # --------------------------------------------------
    # ③ 최종
    # --------------------------------------------------
    rows = []

    for v in temp_map.values():

        # 빈 리스트 → null로 통일
        case_no_list = v["precedent_case_no"]
        date_list = v["precedent_decision_date"]

        # 날짜 리스트 정리 (🔥 핵심 로직)
        if not date_list or any(d is None for d in date_list):
            clean_dates = None
        else:
            clean_dates = date_list

        row = {
            "criterion_text": v["criterion_text"],
            "precedent_case_no": case_no_list if case_no_list else None,
            "precedent_decision_date": clean_dates
        }


        rows.append(row)

    return rows
