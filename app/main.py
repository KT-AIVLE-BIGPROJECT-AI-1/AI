# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.config import settings
from app.core.embeddings import initialize_embeddings


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n" + "=" * 70)
    print("🚀 FastAPI 서버 시작")
    print("=" * 70)
    initialize_embeddings()
    print("\n" + "=" * 70)
    print("✅ 모든 초기화 완료")
    print("=" * 70)
    yield
    print("\n" + "=" * 70)
    print("🛑 FastAPI 서버 종료")
    print("=" * 70 + "\n")


from app.routers import (
    cases_router,
    legal_criteria_router,
    criteria_evaluation_router,
    investigation_files_router,
    analysis_callback_router,
    analysis_final_router,
    report_interim_router,
    report_final_router,
    report_decision_router,
    chat_router,
    reports_router,
)


app = FastAPI(
    title="AI Investigation System",
    description="AI 기반 경찰 수사 지원 시스템",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cases_router)
app.include_router(legal_criteria_router)
app.include_router(criteria_evaluation_router)
app.include_router(investigation_files_router)
app.include_router(analysis_callback_router)
app.include_router(analysis_final_router)
app.include_router(report_interim_router)
app.include_router(report_final_router)
app.include_router(report_decision_router)
app.include_router(chat_router)
app.include_router(reports_router)


@app.get("/")
async def root():
    return JSONResponse(content={
        "message": "AI Investigation System API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "1. CASE": "POST /cases/summary",
            "2. LEGAL_CRITERIA": "POST /legal-criteria",
            "3. CRITERIA_EVALUATION": "POST /legal-criteria/evaluate",
            "4. UPLOAD + 분석": "POST /analysis/upload",
            "5. CALLBACK": "POST /cases/{case_id}/analysis/{analysis_id}/callback",
            "6. FINAL_ANALYSIS": "POST /analysis/final",
            "7. CHAT": "POST /chat/respond",
            "8. REPORT_INTERIM": "POST /reports/interim",
            "9. REPORT_FINAL": "POST /reports/final",
            "10. REPORT_DECISION": "POST /reports/decision"
        }
    })


@app.get("/health")
async def health_check():
    return JSONResponse(content={
        "status": "healthy",
        "openai_configured": bool(settings.OPENAI_API_KEY),
        "gemini_configured": bool(settings.GOOGLE_API_KEY),
        "data_dir": str(settings.DATA_DIR),
        "reports_dir": str(settings.REPORTS_DIR)
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)