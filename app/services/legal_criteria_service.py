# app/services/legal_criteria_service.py

import json
import re
from typing import Dict, Any, List
from openai import OpenAI
from app.config import settings
from app.core.embeddings import get_criminal_law_rag, get_precedent_index  # ✅ getter 함수 사용
from app.core.moleg_api import search_precedent_by_case_number
from app.models.legal_criteria_schema import (
    LegalCriteriaRequest,
    LegalCriteriaResponse
)

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def _clean_json(text: str) -> Dict:
    """GPT 응답에서 JSON 추출"""
    text = re.sub(r"```json|```", "", text).strip()
    try:
        return json.loads(text)
    except:
        start = text.find("{")
        end = text.rfind("}")
        return json.loads(text[start:end+1])


def generate_precedent_search_keywords(issue: Dict[str, str]) -> str:
    """법리 쟁점 → 판례 검색 키워드 생성"""
    prompt = f"""법리 쟁점을 판례 검색용 키워드로 변환하십시오.

쟁점: {issue['issue_name']}
관련 법률: {issue['related_law']}

규칙:
- 핵심 법률 개념만 추출 (예: "폭행", "협박", "재물강취")
- 2~5단어
- 띄어쓰기 포함

키워드만 출력:
"""
    
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0
    )
    
    return resp.choices[0].message.content.strip()


class LegalCriteriaService:
    """
    법리 기준 생성 서비스
    - AI.ipynb의 analyze_legal_criteria_pipeline 기반
    - 실제 API 스펙에 100% 맞춤
    """
    
    @staticmethod
    def analyze_legal_criteria(request: LegalCriteriaRequest) -> LegalCriteriaResponse:
        """
        전체 법리 분석 파이프라인 실행
        STEP 1: 쟁점 도출 
        STEP 2: 기준 도출 
        STEP 3: 판례 검색
        STEP 4: 초기 evaluation 생성
        """
        print("\n" + "=" * 70)
        print("⚖️ 법리 분석 파이프라인 실행")
        print("=" * 70)
        
        # 요청 데이터를 dict로 변환
        case_json = {
            "description": request.description,
            "summary": request.summary.model_dump() if request.summary else {},
            "type": request.type,
            "occurred_at": request.occurred_at,
            "location": request.location
        }
        
        # ✅ getter 함수로 RAG 인스턴스 가져오기
        criminal_law_rag = get_criminal_law_rag()
        precedent_index = get_precedent_index()
        
        # 형법 조문 검색
        print("\n🔍 형법 조문 검색 중...")
        law_results = criminal_law_rag.search(case_json["description"], top_k=10)
        articles_text = "\n\n".join(
            [f"[{a['article']}]\n{a['text'][:600]}..." for a in law_results]
        )
        print(f"✅ {len(law_results)}개 조문 검색 완료")
        
        # ============================================================
        # STEP 1: 법리 쟁점 도출
        # ============================================================
        print("\n📊 STEP 1: 법리 쟁점 도출")
        
        prompt_issue = f"""당신은 형법 전문 검토 AI입니다.

사건 사실:
{case_json["description"]}

구조화 요약:
{json.dumps(case_json.get("summary", {}), ensure_ascii=False, indent=2)}

사건 유형:
{case_json.get("type", "미지정")}

검색된 형법 조문:
{articles_text}

규칙:
- 각 쟁점은 반드시 "~죄 성립 여부" 형식
- 2~4개 생성
- 각 쟁점마다 하나의 related_law 필수
- 입력된 사건 사실과 형법 조문에 없는 내용을 절대로 생성하지 마십시오
- 사건 사실에서 확인할 수 없는 범죄 유형을 추측하여 추가하지 마십시오

JSON만 출력:
{{
  "issues": [
    {{"issue_name": "", "related_law": ""}}
  ]
}}
"""
        
        resp = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt_issue}],
            temperature=0.0,
        )
        
        issues_data = _clean_json(resp.choices[0].message.content)
        issues = issues_data.get("issues", [])
        print(f"✅ {len(issues)}개 쟁점 도출")
        
        # ============================================================
        # 각 쟁점별로 STEP 2, 3, 4 진행
        # ============================================================
        legal_issues_response = []
        
        for idx, issue in enumerate(issues, 1):
            issue_name = issue.get("issue_name", "")
            related_law = issue.get("related_law", "")
            
            print(f"\n🔍 쟁점 {idx}: {issue_name}")
            
            # ============================================================
            # STEP 2: 법리 판단 기준 도출
            # ============================================================
            print(f"   📋 STEP 2: 판단 기준 도출")
            
            law_details = criminal_law_rag.search(related_law, top_k=3)
            law_context = "\n\n".join([f"[{a['article']}]\n{a['text']}" for a in law_details])
            
            prompt_criteria = f"""법리 쟁점: {issue_name}
관련 법률: {related_law}

형법 조문:
{law_context}

사건 요약:
{json.dumps(case_json.get('summary', {}), ensure_ascii=False)}

규칙:
- 각 항목 "~ 여부" 형식
- 5~8개
- criterion_text에 조문 번호 포함
- 제공된 형법 조문과 사건 요약에 없는 기준을 절대로 생성하지 마십시오

JSON만 출력:
{{
  "criteria": ["항목1", "항목2"]
}}
"""
            
            resp_criteria = client.chat.completions.create(
                model="gpt-4.1",
                messages=[{"role": "user", "content": prompt_criteria}],
                temperature=0.0,
            )
            
            criteria_data = _clean_json(resp_criteria.choices[0].message.content)
            criteria_items = criteria_data.get("criteria", [])
            
            print(f"   ✅ {len(criteria_items)}개 기준 도출")
            
            # ============================================================
            # STEP 3: 판례 검색
            # ============================================================
            print(f"   📖 STEP 3: 관련 판례 검색")
            
            # 3-1. 키워드 생성
            keywords = generate_precedent_search_keywords(
                {"issue_name": issue_name, "related_law": related_law}
            )
            print(f"   키워드: {keywords}")
            
            # 3-2. 판례 임베딩 검색
            precedent_results = precedent_index.search_similar_by_title(keywords, top_k=10)
            print(f"   ✅ {len(precedent_results)}개 판례 검색")
            
            # 3-3. 판례 메타데이터만 수집
            precedents_metadata = []
            for prec in precedent_results[:3]:
                precedents_metadata.append({
                    "precedent_case_no": prec["precedent_id"],
                    "precedent_decision_date": prec["decision_date"].replace(".", "-")
                })
            
            print(f"   ✅ {len(precedents_metadata)}개 판례 메타데이터 수집 완료")
            
            # ============================================================
            # STEP 4: 각 기준별로 evaluation 생성
            # ============================================================
            print(f"   🔗 STEP 4: 기준-판례 연결 중...")
            
            legal_criteria_list = []
            
            for crit_idx, criterion_text in enumerate(criteria_items):
                # 판례 할당 (순환 방식)
                if precedents_metadata:
                    assigned_precedent = precedents_metadata[crit_idx % len(precedents_metadata)]
                else:
                    # 판례가 없으면 기본값
                    assigned_precedent = {
                        "precedent_case_no": "000000",
                        "precedent_decision_date": "0000-00-00"
                    }
                
                # ✅ API 스펙 준수
                legal_criteria_list.append({
                    "criterion_text": criterion_text,
                    "precedent_case_no": assigned_precedent["precedent_case_no"],
                    "precedent_decision_date": assigned_precedent["precedent_decision_date"],
                    "evaluation": {
                        "status": "INSUFFICIENT",
                        "reason": f"{criterion_text}을 판단하기 위한 증거가 불충분합니다.",
                        "evidence_gap": f"{criterion_text}을 확인할 수 있는 증거가 필요합니다."
                    }
                })
            
            print(f"   ✅ {len(legal_criteria_list)}개 기준 완료")
            
            # 쟁점별 결과 저장
            legal_issues_response.append({
                "issue_name": issue_name,
                "related_law": related_law,
                "legal_criteria": legal_criteria_list
            })
        
        print("\n" + "=" * 70)
        print(f"✅ 법리 분석 완료: {len(legal_issues_response)}개 쟁점")
        print("=" * 70)
        
        return LegalCriteriaResponse(legal_issues=legal_issues_response)