# app/main.py

import json
import time
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.core.embeddings import initialize_embeddings


# ============================================================
# 요청/응답 로깅 미들웨어 (422 디버깅용)
# ============================================================

class RequestResponseLoggingMiddleware(BaseHTTPMiddleware):
    """
    모든 요청·응답의 핵심 정보를 로깅합니다.
    - 요청: method, path, body (POST/PUT/PATCH)
    - 응답: status_code, body (4xx/5xx 에러 시)
    422 Validation Error 발생 시 요청 body와 에러 detail을 함께 출력하여
    어떤 필드가 누락/타입 불일치인지 즉시 확인할 수 있습니다.
    """

    BODY_LOG_MAX = 3000  # body 로그 최대 길이 (너무 긴 body 잘림 방지)

    async def dispatch(self, request: Request, call_next):
        start = time.time()
        method = request.method
        path = request.url.path
        query = str(request.query_params) if request.query_params else ""

        # ── 요청 body 읽기 (POST/PUT/PATCH만) ──
        req_body_text = ""
        if method in ("POST", "PUT", "PATCH"):
            try:
                raw = await request.body()
                req_body_text = raw.decode("utf-8", errors="replace")
                if len(req_body_text) > self.BODY_LOG_MAX:
                    req_body_text = req_body_text[:self.BODY_LOG_MAX] + "...(truncated)"
            except Exception:
                req_body_text = "(body 읽기 실패)"

        # 요청 로그 출력
        log_line = f"📥 REQUEST  {method} {path}"
        if query:
            log_line += f"?{query}"
        print(log_line)

        if req_body_text:
            # JSON 정렬 출력 시도
            try:
                pretty = json.dumps(json.loads(req_body_text), ensure_ascii=False, indent=2)
                if len(pretty) > self.BODY_LOG_MAX:
                    pretty = pretty[:self.BODY_LOG_MAX] + "...(truncated)"
                print(f"   📦 Body:\n{pretty}")
            except Exception:
                print(f"   📦 Body (raw): {req_body_text}")

        # ── 응답 처리 ──
        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed = time.time() - start
            print(f"📤 RESPONSE {method} {path} → 💥 500 INTERNAL ERROR ({elapsed:.2f}s)")
            print(f"   ❌ Exception: {exc}")
            traceback.print_exc()
            return JSONResponse(
                status_code=500,
                content={"detail": f"Internal Server Error: {str(exc)}"}
            )

        elapsed = time.time() - start
        status = response.status_code

        # ── 응답 body 읽기 (에러 상태일 때만 상세 출력) ──
        if status >= 400:
            # StreamingResponse에서 body 추출
            body_parts = []
            async for chunk in response.body_iterator:
                if isinstance(chunk, bytes):
                    body_parts.append(chunk)
                else:
                    body_parts.append(chunk.encode("utf-8"))
            resp_body = b"".join(body_parts)
            resp_text = resp_body.decode("utf-8", errors="replace")

            emoji = "⚠️" if status < 500 else "💥"
            print(f"📤 RESPONSE {method} {path} → {emoji} {status} ({elapsed:.2f}s)")

            # 422 Validation Error 상세 출력
            if status == 422:
                print(f"   🔴 422 VALIDATION ERROR 상세:")
                try:
                    detail = json.loads(resp_text)
                    for err in detail.get("detail", []):
                        loc = " → ".join(str(l) for l in err.get("loc", []))
                        msg = err.get("msg", "")
                        err_type = err.get("type", "")
                        print(f"      ❌ [{loc}] {msg} (type: {err_type})")
                except Exception:
                    print(f"      Raw: {resp_text[:1000]}")
            else:
                print(f"   📦 Error Response: {resp_text[:1000]}")

            # body를 다시 Response로 감싸서 반환
            return Response(
                content=resp_body,
                status_code=status,
                headers=dict(response.headers),
                media_type=response.media_type
            )

        # 정상 응답 (간단 로그)
        print(f"📤 RESPONSE {method} {path} → ✅ {status} ({elapsed:.2f}s)")

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n" + "=" * 70)
    print("🚀 FastAPI 서버 시작")
    print("=" * 70)
    initialize_embeddings()

    # ✅ 저장된 분석 결과 복원 (챗봇 서버 재시작 대응)
    from app.services.analysis_callback_service import AnalysisCallbackService
    AnalysisCallbackService.load_from_disk()

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

# ✅ 로깅 미들웨어 등록 (CORS보다 먼저 등록해야 모든 요청 캡처)
app.add_middleware(RequestResponseLoggingMiddleware)

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