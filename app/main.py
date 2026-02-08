from fastapi import FastAPI
from contextlib import asynccontextmanager
from openai import OpenAI

from app.routers import cases, legal_criteria, criteria_evaluation
from app.core.criminal_law_rag import CriminalLawRAG
from app.core.precedent_embedding import PrecedentIndex
from app.config import (
    CRIMINAL_LAW_PATH,
    RAG_INDEX_PATH,
    PRECEDENT_CSV_PATH,
    OPENAI_API_KEY
)

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     print("🚀 서버 시작 → 초기 데이터 로드")

#     # 1) 형법 RAG
#     client = OpenAI(api_key=OPENAI_API_KEY)
#     rag = CriminalLawRAG(client)

#     if RAG_INDEX_PATH.exists():
#         rag.load_index(str(RAG_INDEX_PATH))
#     else:
#         rag.build_index(str(CRIMINAL_LAW_PATH))
#         rag.save_index(str(RAG_INDEX_PATH))

#     # 2) 판례 임베딩
#     precedent_index = PrecedentIndex()
#     precedent_index.init_index()

#     # 전역 저장
#     app.state.client = client
#     app.state.criminal_law_rag = rag
#     app.state.precedent_index = precedent_index

#     print("초기화 완료-서버 준비됨")

#     yield
#     print("🛑 서버 종료")

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 서버 시작 → 초기 데이터 로드")

    client = OpenAI(api_key=OPENAI_API_KEY)

    # ===== 형법 RAG =====
    rag = CriminalLawRAG(client)

    if RAG_INDEX_PATH.exists():
        print("📂 기존 RAG 인덱스 로드")
        rag.load_index(str(RAG_INDEX_PATH))
    else:
        print("⚠️ RAG 캐시 없음 → 최초 1회만 생성")
        rag.build_index(str(CRIMINAL_LAW_PATH))
        rag.save_index(str(RAG_INDEX_PATH))

    # ===== 판례 임베딩 =====
    precedent_index = PrecedentIndex()

    if PRECEDENT_EMBEDDING_CACHE.exists():
        print("📂 기존 판례 임베딩 로드")
        precedent_index.load_cache()
    else:
        print("⚠️ 판례 임베딩 없음 → 최초 1회만 생성")
        precedent_index.load_precedent_csv()
        precedent_index.build_embeddings()
        precedent_index.save_cache()

    app.state.criminal_law_rag = rag
    app.state.precedent_index = precedent_index

    yield
    print("🛑 서버 종료")


app = FastAPI(title="My API")

@app.get("/health")
def health():
    return {"status": "ok"}

# ---------라우터 연결-----------
app.include_router(cases.router)
app.include_router(legal_criteria.router)
app.include_router(criteria_evaluation.router)  