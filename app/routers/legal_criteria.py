# app/routers/legal_criteria.py
# =========================
# 수정 필요
# =========================


# from openai import OpenAI
# from app.config import OPENAI_API_KEY, CRIMINAL_LAW_PATH, RAG_INDEX_PATH
from fastapi import APIRouter, HTTPException
from app.models.legal_criteria_schema import LegalCriteriaRequest, LegalCriteriaResponse
from app.services.legal_criteria_service import LegalCriteriaService
# from app.services.legal_criteria_service import analyze_legal_criteria_pipeline, enrich_criterion_text_with_law
# from app.core.criminal_law_rag import CriminalLawRAG
# from app.core.precedent_embedding import PrecedentIndex


router = APIRouter(prefix="/legal-criteria", tags=["Legal Criteria"])

# # ---------- 싱글톤 초기화 ----------
# client = OpenAI(api_key=OPENAI_API_KEY)

# criminal_law_rag = CriminalLawRAG(client=client)
# if RAG_INDEX_PATH.exists():
#     criminal_law_rag.load_index(str(RAG_INDEX_PATH))
# else:
#     criminal_law_rag.build_index(str(CRIMINAL_LAW_PATH))
#     criminal_law_rag.save_index(str(RAG_INDEX_PATH))

# precedent_index = PrecedentIndex()
# precedent_index.init_index()


@router.post("", response_model=LegalCriteriaResponse)
async def search_legal_criteria(request: LegalCriteriaRequest):
    """
    법률 기준 검색 및 분석
    
    - 벡터 검색으로 관련 법조문 추출
    - 법리 쟁점 도출
    - 판단 기준 생성
    - 판례 검색 및 연결
    """
    try:
        # ✅ 수정: analyze_legal_criteria 메서드 호출
        response = LegalCriteriaService.analyze_legal_criteria(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"법률 기준 검색 실패: {str(e)}")


# ---------- API ----------
@router.post("", response_model=LegalCriteriaResponse)
def create_legal_criteria(case: LegalCriteriaRequest):
    try:
        return analyze_legal_criteria_pipeline(
            client=client,
            criminal_law_rag=criminal_law_rag,
            precedent_index=precedent_index,
            case=case,
        )

        for issue in result["legal_issues"]:
            for c in issue["legal_criteria"]:
                c["criterion_text"] = enrich_criterion_text_with_law(
                    c["criterion_text"],
                    criminal_law_rag
                )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

