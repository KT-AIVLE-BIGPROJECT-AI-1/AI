from fastapi import APIRouter, HTTPException
from openai import OpenAI

from app.config import OPENAI_API_KEY, CRIMINAL_LAW_PATH, RAG_INDEX_PATH
from app.models.legal_criteria_schema import (
    LegalCriteriaRequest, LegalCriteriaResponse
)
from app.services.legal_criteria_service import analyze_legal_criteria_pipeline
from app.core.criminal_law_rag import CriminalLawRAG
from app.core.precedent_embedding import PrecedentIndex

router = APIRouter(prefix="/legal-criteria", tags=["Legal Criteria"])

# ---------- 싱글톤 초기화 ----------
client = OpenAI(api_key=OPENAI_API_KEY)

criminal_law_rag = CriminalLawRAG(client=client)
if RAG_INDEX_PATH.exists():
    criminal_law_rag.load_index(str(RAG_INDEX_PATH))
else:
    criminal_law_rag.build_index(str(CRIMINAL_LAW_PATH))
    criminal_law_rag.save_index(str(RAG_INDEX_PATH))

precedent_index = PrecedentIndex()
precedent_index.init_index()

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))