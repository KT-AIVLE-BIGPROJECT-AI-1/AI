# app/main.py
# =========================
# 수정 필요
# =========================

<<<<<<< HEAD
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.config import settings
from app.core.embeddings import initialize_embeddings

#-----------------------------------------------------#
from openai import OpenAI

from app.routers import (
    cases, legal_criteria, criteria_evaluation, 
    analysis, analysis_doc, analysis_img,
    chat, final_analysis
    )
from app.routers.stt_video import router as stt_video_router   # ⭐ 추가


from app.core.criminal_law_rag import CriminalLawRAG
from app.core.precedent_embedding import PrecedentIndex
from app.config import (
    CRIMINAL_LAW_PATH,
    RAG_INDEX_PATH,
    PRECEDENT_CSV_PATH,
    PRECEDENT_EMBEDDING_CACHE,
    OPENAI_API_KEY
)
#-----------------------------------------------------#

# 라우터 임포트
from app.routers import (
    cases_router,
    legal_criteria_router,
    criteria_evaluation_router,
    investigation_files_router,
    analysis_document_router,
    analysis_image_router,
    analysis_media_router,
    analysis_callback_router,
    analysis_final_router,
    report_interim_router,
    report_final_router,
    report_decision_router,
    chat_router,
    reports_router,  # ✅ 추가
)


from app.routers import reports

app = FastAPI()




@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    앱 시작/종료 이벤트 핸들러
    """
    # 시작 시: 임베딩 초기화
    print("\n" + "=" * 70)
    print("🚀 FastAPI 서버 시작")
    print("=" * 70)
    
    initialize_embeddings()
    
    print("\n" + "=" * 70)
    print("✅ 모든 초기화 완료")
    print("=" * 70 + "\n")
    
    yield
    
    # 종료 시
    print("\n" + "=" * 70)
    print("🛑 FastAPI 서버 종료")
    print("=" * 70 + "\n")

    # ---------------------------------------------------------- #
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
    # ---------------------------------------------------------- #


# FastAPI 앱 생성
app = FastAPI(
    title="경찰 사건 분석 AI 시스템",
    description="AI.ipynb를 FastAPI로 변환한 경찰 수사 분석 시스템",
    version="1.0.0",
    lifespan=lifespan
)


# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 라우터 등록
app.include_router(cases_router)
app.include_router(legal_criteria_router)
app.include_router(criteria_evaluation_router)
app.include_router(investigation_files_router)
app.include_router(analysis_document_router)
app.include_router(analysis_image_router)
app.include_router(analysis_media_router)
app.include_router(analysis_callback_router)
app.include_router(analysis_final_router)
app.include_router(report_interim_router)
app.include_router(report_final_router)
app.include_router(report_decision_router)
app.include_router(chat_router)
app.include_router(reports_router)  # ✅ 추가


# 루트 엔드포인트
@app.get("/")
async def root():
    """
    API 상태 확인
    """
    return JSONResponse(content={
        "message": "경찰 사건 분석 AI 시스템",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "1. CASE": "POST /cases/summary",
            "2. LEGAL_CRITERIA": "POST /legal-criteria",
            "3. CRITERIA_EVALUATION": "POST /legal-criteria/evaluate",
            "4. ANALYSIS_DOC": "POST /analysis/doc",
            "5. ANALYSIS_IMG": "POST /analysis/img",
            "6. ANALYSIS_VDO": "POST /analysis/vdo",
            "7. ANALYSIS_STT": "POST /analysis/stt",
            "8. INVESTIGATE_FILE": "POST /analysis/upload",
            "9. CHAT_LOG": "POST /chat/respond",
            "10-15. CALLBACKS": "POST /cases/{case_id}/analysis/{analysis_id}/callback",
            "16. FINAL_ANALYSIS": "POST /analysis/final",
            "17. REPORTS": "POST /reports/interim-draft",
            "18. REPORT_A": "POST /reports/final-draft",
            "19. REPORT_B": "POST /reports/decision-draft"
        }
    })

# ==============================
# ✅ 핵심: lifespan 연결
# ==============================
app = FastAPI(
    title="AI Investigation Analysis Server",
    lifespan=lifespan
)


<<<<<<< HEAD
@app.get("/health")
async def health_check():
    """
    헬스 체크
    """
    return JSONResponse(content={
        "status": "healthy",
        "openai_configured": bool(settings.OPENAI_API_KEY),
        "gemini_configured": bool(settings.GOOGLE_API_KEY),
        "data_dir": str(settings.DATA_DIR),
        "reports_dir": str(settings.REPORTS_DIR)
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )


# # ---------라우터 연결-----------
# app.include_router(cases.router)
# app.include_router(legal_criteria.router)
# app.include_router(criteria_evaluation.router)  
# app.include_router(analysis.router)      # /analysis/upload
# app.include_router(stt_video_router)     # ⭐ /analysis/stt-video 추가
# app.include_router(analysis_doc.router)
# app.include_router(analysis_img.router)
# app.include_router(chat.router)
# app.include_router(final_analysis.router)
# app.include_router(reports.router)
