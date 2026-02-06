"""
FastAPI 메인 애플리케이션
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import get_settings
from app.core.vector_store import get_vector_store

# Routers
from app.routers import (
    analysis_document,
    analysis_image,
    investigation_file,
    chat_log,
    analysis_callback
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작/종료 이벤트"""
    # 시작 시
    print("=" * 70)
    print("🚀 FastAPI 서버 시작")
    print("=" * 70)
    
    # 벡터 DB 초기화
    try:
        print("\n📊 벡터 데이터베이스 초기화 중...")
        vector_store = get_vector_store()
        
        # 형법 임베딩 초기화
        vector_store.initialize_criminal_law()
        
        # 판례 임베딩 초기화
        vector_store.initialize_precedents()
        
        print("✅ 벡터 데이터베이스 초기화 완료\n")
    except Exception as e:
        print(f"⚠️ 벡터 DB 초기화 실패: {e}\n")
    
    print("=" * 70)
    print("✅ 서버 준비 완료")
    print("=" * 70)
    
    yield
    
    # 종료 시
    print("\n" + "=" * 70)
    print("🛑 FastAPI 서버 종료")
    print("=" * 70)


# FastAPI 앱 생성
settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI 기반 법률 분석 시스템 API",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인만 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(analysis_document.router)
app.include_router(analysis_image.router)
app.include_router(investigation_file.router)
app.include_router(chat_log.router)
app.include_router(analysis_callback.router)


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "message": "AI Legal Analysis API",
        "version": settings.APP_VERSION,
        "endpoints": {
            "문서 분석": "POST /analysis/doc",
            "이미지 분석": "POST /analysis/img",
            "파일 업로드": "POST /analysis/upload",
            "채팅": "POST /chat/respond",
            "분석 콜백": "POST /cases/{caseId}/analysis/{analysisId}/callback"
        }
    }


@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
