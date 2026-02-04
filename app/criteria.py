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

    EXCLUDE_KEYWORDS = [
    "분리조치", "응급조치", "가정폭력", "적법", 
    "큰 소리", "고성", "언행", "수사", "절차",
    "영장", "현수막", "과도", "탄원", "반성"
    ]

    CRIME_EXCLUDE = [
        "상해", "절도", "강도", "침입", "방화", "사기", "횡령", "배임"
    ]

    for p in reranked:
        prompt = f"""
당신은 판례에서 **구성요건 판단에 필요한 사실요소만 추출하고,
사건 특정 표현은 반드시 일반화(추상화)** 한다.

🚫 절대 금지:
- 금액, 모델명, 장소명, 도구명, 날짜 등 사건 고유 정보
- 양형 사유(전과, 반성, 합의, 탄원)
- 수사 절차 적법성(출동, 분리조치, 영장 등)
- 특별법 논점(가정폭력처벌법, 도로교통법 등)

✅ 반드시 일반화할 것:
예)
- ❌ “155만 원 휴대전화를 바닥에 던졌는지”
- ✅ “타인의 재물을 물리적으로 훼손하는 행위가 있었는지”

허용 프레임(이 네 가지만):
1) 행위: 피의자가 무엇을 했는지(물리적 행위)
2) 객체: 그 행위의 대상이 무엇인지
3) 결과: 구체적 피해·침해가 있었는지
4) 인식: 피의자가 결과를 인식했는지

📌 형식 규칙:
- 반드시 체크리스트 문장
- “~였는지 확인”
- “~가 있었는지 검토”
- “~가 인정되는지 확인”
만 허용

JSON:
{{ "criteria": [] }}

[법리 쟁점]
{legal_issue["issue_name"]}
{legal_issue["related_law"]}

[판례 본문]
{p["판결이유"]}
"""


        res = call_llm_json(prompt)

        # === 🔍 디버그용 (필요하면 켜두세요) ===
        print(f"DEBUG criteria from case {p['precedent_case_no']}: {res}")

        for c in res.get("criteria", []):
            text = _safe_text(c).strip()

            # 빈 값 스킵
            if not text:
                continue

            if any(k in text for k in EXCLUDE_KEYWORDS):
                continue

            # 블랙리스트 필터
            if any(b in text for b in BLACKLIST):
                continue
            
            # 범죄 혼입 방지 필터
            if any(c in text for c in CRIME_EXCLUDE):
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

def expand_criteria_from_anchor(common_criteria, case_summary, legal_issue, case_types):
    anchor_texts = [
        c["criterion_text"]
        for c in common_criteria.get("common_criteria", [])
        if isinstance(c, dict) and c.get("criterion_text")
    ]

    prompt = f"""
당신은 경찰 수사 실무용 체크리스트 생성 AI이다.

아래는 판례에서 검증된 핵심 판단 기준(anchor)이다:
{anchor_texts}

아래 사건을 판단할 때,
**오직 아래 법리 쟁점과 직접 관련된 사실 확인 기준만**
3~5개 생성하라.

🚫 절대 금지:
- 범죄 유형을 임의로 바꾸지 말 것
- '정당성', '적법성', '책임', '양형' 개념 사용 금지
- 절차(출동, 영장, 분리조치) 금지
- 사건 세부 물건명(지갑, 차량, 현수막 등) 고정 금지

✅ 필수 형식 (중 하나만 사용):
• "~였는지 확인"
• "~가 있었는지 검토"
• "~가 인정되는지 확인"


[현재 사건 요약]
{case_summary}

[사건 유형]
{case_types}

[법리 쟁점]
{legal_issue["issue_name"]}
{legal_issue["related_law"]}

출력(JSON):
{{ "expanded_criteria": [] }}
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
                if str(pb.get("precedent_case_no")) == str(case_no):
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
        # None 제거하고 실제 날짜만 남김
        clean_dates = [d for d in date_list if d]

        # 전부 비어 있으면 null, 아니면 리스트 유지
        clean_dates = clean_dates if clean_dates else None
        

        row = {
            "criterion_text": v["criterion_text"],
            "precedent_case_no": case_no_list if case_no_list else None,
            "precedent_decision_date": clean_dates
        }


        rows.append(row)

    return rows
