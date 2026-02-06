# <<<<<<< HEAD
# # app/services/legal_criteria_service.py
# # =========================
# # 수정 필요
# # =========================

# import json, re
# from datetime import datetime, timezone
# from typing import Any, Dict, List, Optional
# from openai import OpenAI
# from app.config import settings
# from app.core.embeddings import get_criminal_law_rag, get_precedent_index, fetch_precedent_from_law_api
# from app.models.legal_criteria_schema import (
#     LegalCriteriaRequest,
#     LegalCriteriaResponse,
#     LegalIssue,
#     LegalCriterion,
#     CriteriaEvaluation
# )
# # from app.models.legal_criteria_schema import LegalCriteriaRequest
# # from app.core.criminal_law_rag import CriminalLawRAG
# # from app.core.precedent_embedding import PrecedentIndex

# client = OpenAI(api_key=settings.OPENAI_API_KEY)


# def utc_now_iso() -> str:
#     return datetime.now(timezone.utc).isoformat()

# # ---------- 유틸 ----------
# def _clean_json(text: str) -> dict:
#     """GPT 응답에서 JSON 추출"""
# =======



# def _clean_json(text: str) -> dict:
# >>>>>>> 219b9b6 (feat: 사건 요약 및 쟁점 초기 평가)
#     text = re.sub(r"```json|```", "", text).strip()
#     try:
#         return json.loads(text)
#     except:
#         start = text.find("{")
#         end = text.rfind("}")
#         return json.loads(text[start:end+1])


# <<<<<<< HEAD
# class LegalCriteriaService:
#     @staticmethod
#     def analyze_legal_criteria(request: LegalCriteriaRequest) -> LegalCriteriaResponse:
#         """
#         법리 분석 파이프라인 (AI.ipynb의 analyze_legal_criteria_pipeline 이식)
#         """
#         print("\n" + "=" * 70)
#         print("⚖️ 법리 분석 파이프라인 시작")
#         print("=" * 70)
        
#         # 형법 RAG, 판례 인덱스 가져오기
#         criminal_law_rag = get_criminal_law_rag()
#         precedent_index = get_precedent_index()
        
#         if not criminal_law_rag:
#             print("❌ 형법 RAG 시스템이 없습니다.")
#             return LegalCriteriaResponse(legal_issues=[])
        
#         # CASE JSON 구성
#         case_json = {
#             "description": request.description,
#             "summary": request.summary.model_dump(),
#             "type": request.type,
#             "occurred_at": request.occurred_at,
#             "location": request.location
#         }
        
#         # 형법 조문 검색
#         law_results = criminal_law_rag.search(request.description, top_k=10)
#         articles_text = "\n\n".join(
#             [f"[{a['article']}]\n{a['text'][:600]}..." for a in law_results]
#         )
        
#         # ============================================================
#         # STEP 1: 법리 쟁점 도출
#         # ============================================================
#         print("\n📊 STEP 1: 법리 쟁점 도출")
        
#         issues = LegalCriteriaService._extract_legal_issues(
#             case_json, articles_text
#         )
        
#         print(f"✅ {len(issues)}개 쟁점 도출")
        
#         # ============================================================
#         # STEP 2~4: 각 쟁점별 기준 도출 + 판례 검색 + 평가
#         # ============================================================
#         legal_issues_response = []
        
#         for idx, issue in enumerate(issues, 1):
#             issue_name = issue.get("issue_name", "")
#             related_law = issue.get("related_law", "")
            
#             print(f"\n🔍 쟁점 {idx}: {issue_name}")
            
#             # STEP 2: 판단 기준 도출
#             criteria_items = LegalCriteriaService._extract_criteria(
#                 issue_name, related_law, case_json, criminal_law_rag
#             )
            
#             print(f"   ✅ {len(criteria_items)}개 기준 도출")
            
#             # STEP 3: 판례 검색
#             precedent_bodies = []
#             if precedent_index:
#                 precedent_bodies = LegalCriteriaService._search_precedents(
#                     issue_name, related_law, precedent_index
#                 )
#                 print(f"   ✅ {len(precedent_bodies)}개 판례 검색")
            
#             # STEP 4: 각 기준별 초기 평가 생성
#             legal_criteria_list = []
            
#             for i, criterion_text in enumerate(criteria_items):
#                 # 판례 연결 (순환 할당)
#                 if precedent_bodies:
#                     precedent_idx = i % len(precedent_bodies)
#                     selected_precedent = precedent_bodies[precedent_idx]
#                     precedent_case_no = selected_precedent["precedent_case_no"]
#                     precedent_decision_date = selected_precedent["precedent_decision_date"]
#                 else:
#                     precedent_case_no = None
#                     precedent_decision_date = None
                
#                 # 초기 평가 (INSUFFICIENT)
#                 evaluation = CriteriaEvaluation(
#                     status="INSUFFICIENT",
#                     reason=f"{criterion_text}을(를) 판단하기 위한 증거가 현재 분석되지 않았습니다. 증거 분석 후 평가가 필요합니다.",
#                     evidence_gap=f"{criterion_text}에 대한 구체적인 증거 자료가 필요합니다."
#                 )
                
#                 legal_criteria_list.append(LegalCriterion(
#                     criterion_text=criterion_text,
#                     precedent_case_no=precedent_case_no,
#                     precedent_decision_date=precedent_decision_date,
#                     evaluation=evaluation
#                 ))
            
#             print(f"   ✅ {len(legal_criteria_list)}개 기준 생성 완료")
            
#             legal_issues_response.append(LegalIssue(
#                 issue_name=issue_name,
#                 related_law=related_law,
#                 legal_criteria=legal_criteria_list
#             ))
        
#         print("\n" + "=" * 70)
#         print(f"✅ 법리 분석 완료: {len(legal_issues_response)}개 쟁점")
#         print("=" * 70)
        
#         return LegalCriteriaResponse(legal_issues=legal_issues_response)
    
#     @staticmethod
#     def _extract_legal_issues(case_json: dict, articles_text: str) -> list:
#         """법리 쟁점 도출"""
#         prompt_issue = f"""당신은 형법 전문 검토 AI입니다.
# =======
# # ---------- ① 법리 쟁점 ----------
# def infer_legal_issues_with_criminal_law_api(
#     client: OpenAI,
#     case_json: dict,
#     criminal_law_rag: CriminalLawRAG,
#     top_k: int = 10,
# ):
#     law_results = criminal_law_rag.search(case_json["description"], top_k=top_k)

#     articles_text = "\n\n".join(
#         [f"[{a['article']}]\n{a['text'][:600]}..." for a in law_results]
#     )

#     prompt = f"""
# 당신은 형법 전문 검토 AI입니다.
# >>>>>>> 219b9b6 (feat: 사건 요약 및 쟁점 초기 평가)

# 사건 사실:
# {case_json["description"]}

# 구조화 요약:

# {json.dumps(case_json.get("summary", {}), ensure_ascii=False, indent=2)}

# 사건 유형:
# {case_json.get("type", "미지정")}
# # =======
# # {json.dumps(case_json["summary"], ensure_ascii=False, indent=2)}

# # 사건 유형:
# # {case_json["type"]}


# 검색된 형법 조문:
# {articles_text}

# 규칙:
# <<<<<<< HEAD
# - 각 쟁점은 반드시 "~죄 성립 여부" 형식
# =======

# >>>>>>> 219b9b6 (feat: 사건 요약 및 쟁점 초기 평가)
# - 2~4개 생성
# - 각 쟁점마다 하나의 related_law 필수

# JSON만 출력:
# {{
#   "issues": [
#     {{"issue_name": "", "related_law": ""}}
#   ]
# }}
# """
# <<<<<<< HEAD
        
#         response = client.chat.completions.create(
#             model="gpt-4o",
#             messages=[{"role": "user", "content": prompt_issue}],
#             temperature=0.2
#         )
        
#         issues_data = _clean_json(response.choices[0].message.content)
#         return issues_data.get("issues", [])

#             resp = client.chat.completions.create(
#         model="gpt-4o",
#         messages=[{"role": "user", "content": prompt}],
#         temperature=0.2,
#     )

#     parsed = _clean_json(resp.choices[0].message.content)
#     return parsed.get("issues", [])
    
#     @staticmethod
#     def _extract_criteria(issue_name: str, related_law: str, case_json: dict, criminal_law_rag) -> list:
#         """판단 기준 도출"""
#         law_details = criminal_law_rag.search(related_law, top_k=3)
#         law_context = "\n\n".join([f"[{a['article']}]\n{a['text']}" for a in law_details])
        
#         prompt_criteria = f"""법리 쟁점: {issue_name}
# 관련 법률: {related_law}
# =======




# # ---------- ② 법리 기준 ----------
# def derive_legal_criteria_with_criminal_law_api(
#     client: OpenAI,
#     legal_issue: Dict[str, Any],
#     criminal_law_rag: CriminalLawRAG,
#     precedent_index: PrecedentIndex,
#     case_json: dict,
# ):
#     law_details = criminal_law_rag.search(legal_issue["related_law"], top_k=3)
#     law_context = "\n\n".join([f"[{a['article']}]\n{a['text']}" for a in law_details])

#     prompt = f"""
# 법리 쟁점: {legal_issue['issue_name']}
# 관련 법률: {legal_issue['related_law']}
# >>>>>>> 219b9b6 (feat: 사건 요약 및 쟁점 초기 평가)

# 형법 조문:
# {law_context}

# 사건 요약:
# <<<<<<< HEAD
# {json.dumps(case_json.get('summary', {}), ensure_ascii=False)}
# # {json.dumps(case_json['summary'], ensure_ascii=False)}

# 규칙:
# - 각 항목 "~ 여부" 형식
# =======


# >>>>>>> 219b9b6 (feat: 사건 요약 및 쟁점 초기 평가)
# - 5~8개
# - criterion_text에 조문 번호 포함

# JSON만 출력:
# {{
#   "criteria": ["항목1", "항목2"]
# }}
# """
# <<<<<<< HEAD
        
#         response = client.chat.completions.create(
#             model="gpt-4o",
#             messages=[{"role": "user", "content": prompt_criteria}],
#             temperature=0.2
#         )
        
#         criteria_data = _clean_json(response.choices[0].message.content)
#         return criteria_data.get("criteria", [])
    
#     @staticmethod
#     def _search_precedents(issue_name: str, related_law: str, precedent_index) -> list:
#         """판례 검색 + 법제처 API 조회"""
#         # 키워드 생성
#         keywords = f"{issue_name} {related_law}"
        
#         # 유사 판례 검색
#         similar_precedents = precedent_index.search_similar(keywords, top_k=5)
        
#         # 법제처 API로 전문 조회
#         precedent_bodies = []
        
#         for p in similar_precedents[:3]:
#             if settings.LAW_API_KEY:
#                 parsed = fetch_precedent_from_law_api(p["precedent_id"])
#                 decision_date = parsed.get("precedent_decision_date")
#             else:
#                 decision_date = None
            
#             if not decision_date:
#                 csv_date = str(p.get("decision_date", ""))
#                 if len(csv_date) == 8:
#                     decision_date = f"{csv_date[:4]}-{csv_date[4:6]}-{csv_date[6:]}"
#                 else:
#                     decision_date = None
            
#             precedent_bodies.append({
#                 "precedent_case_no": str(p["precedent_id"]),
#                 "precedent_decision_date": decision_date
#             })
        
#         return precedent_bodies
# =======

#     resp = client.chat.completions.create(
#         model="gpt-4o",
#         messages=[{"role": "user", "content": prompt}],
#         temperature=0.2,
#     )

#     parsed = _clean_json(resp.choices[0].message.content)
#     items = parsed.get("criteria", [])

#     # 판례 연결
#     precedents = precedent_index.search_similar(legal_issue["issue_name"], top_k=3)

#     results = []
#     for i, text in enumerate(items):
#         p = precedents[i % len(precedents)] if precedents else {}
#         results.append({
#             "criterion_text": text,
#             "precedent_case_no": p.get("precedent_id"),
#             "precedent_decision_date": p.get("decision_date"),
#         })
#     return results


# # ---------- ③ 사건 정보 기준 평가 ----------
# def evaluate_criterion_with_case_info(
#     client: OpenAI,
#     criterion: dict,
#     case_json: dict,
# ):
#     prompt = f"""
# 법리 기준:
# {criterion['criterion_text']}

# 사건 사실:
# {case_json['description']}

# 구조화 요약:
# {json.dumps(case_json['summary'], ensure_ascii=False)}

# 아래 JSON만 출력:
# {{
#   "status": "SATISFIED | NOT_SATISFIED | INSUFFICIENT",
#   "reason": "2~3문장",
#   "evidence_gap": "필요 증거 또는 null"
# }}
# """

#     resp = client.chat.completions.create(
#         model="gpt-4o",
#         messages=[{"role": "user", "content": prompt}],
#         temperature=0.2,
#     )

#     parsed = _clean_json(resp.choices[0].message.content)
#     return parsed


# # ---------- ④ 전체 파이프라인 ----------
# def analyze_legal_criteria_pipeline(
#     client: OpenAI,
#     criminal_law_rag: CriminalLawRAG,
#     precedent_index: PrecedentIndex,
#     case: LegalCriteriaRequest,
# ):
#     case_json = case.model_dump()

#     issues = infer_legal_issues_with_criminal_law_api(
#         client, case_json, criminal_law_rag
#     )

#     response_issues = []

#     for issue in issues:
#         criteria = derive_legal_criteria_with_criminal_law_api(
#             client, issue, criminal_law_rag, precedent_index, case_json
#         )

#         evaluated = []
#         for c in criteria:
#             evaluation = evaluate_criterion_with_case_info(
#                 client, c, case_json
#             )
#             evaluated.append({
#                 "criterion_text": c["criterion_text"],
#                 "precedent_case_no": c.get("precedent_case_no"),
#                 "precedent_decision_date": c.get("precedent_decision_date"),
#                 "evaluation": evaluation,
#             })

#         response_issues.append({
#             "issue_name": issue["issue_name"],
#             "related_law": issue["related_law"],
#             "legal_criteria": evaluated,
#         })

#     return {"legal_issues": response_issues}
# >>>>>>> 219b9b6 (feat: 사건 요약 및 쟁점 초기 평가)
