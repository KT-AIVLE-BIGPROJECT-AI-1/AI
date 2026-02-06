# AI Legal Analysis API

AI 기반 범죄 수사 분석 시스템의 FastAPI 백엔드

## 📁 프로젝트 구조

```
app/
├── main.py                  # FastAPI 진입점 + startup(임베딩)
├── config.py                # 환경변수 + 경로 관리
│
├── core/                    # 공통 인프라
│   ├── __init__.py
│   ├── embeddings.py        # 형법/판례 임베딩 초기화
│   └── vector_store.py      # Chroma 관리
│
├── services/                # 실제 AI 비즈니스 로직
│   ├── __init__.py
│   ├── analysis_document_service.py
│   ├── analysis_image_service.py
│   ├── investigation_file_service.py
│   ├── chat_log_service.py
│   └── analysis_callback_service.py
│
├── models/                  # 요청/응답 스키마(Pydantic)
│   ├── __init__.py
│   ├── analysis_document_schema.py
│   ├── analysis_image_schema.py
│   ├── investigation_file_schema.py
│   ├── chat_log_schema.py
│   └── analysis_callback_schema.py
│
├── routers/                 # API 엔드포인트
│   ├── __init__.py
│   ├── analysis_document.py
│   ├── analysis_image.py
│   ├── investigation_file.py
│   ├── chat_log.py
│   └── analysis_callback.py
│
└── data/                    # AI 전용 정적 데이터
    ├── criminal_law.pdf     # 형법
    └── precedents.json      # 판례 목록
```

## 🚀 시작하기

### 1. 환경 설정

```bash
# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt
```

### 2. 환경 변수 설정

```bash
# .env 파일 생성
cp .env.example .env

# .env 파일 편집하여 API 키 설정
# OPENAI_API_KEY=your_key_here
# HUGGINGFACEHUB_API_TOKEN=your_token_here
# GOOGLE_API_KEY=your_key_here
```

### 3. 형법/판례 데이터 준비

```bash
# app/data/ 폴더에 다음 파일 배치:
# - criminal_law.pdf (형법 PDF)
# - precedents.json (판례 목록 JSON)
```

### 4. 서버 실행

```bash
# 개발 서버 (자동 재시작)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 프로덕션 서버
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 📡 API 엔드포인트

### 1. 문서 분석
```http
POST /analysis/doc
Content-Type: application/json

{
  "file_id": "84b76f99-aee9-4a14-bcd7-a8d7958272fc",
  "file_path": "/path/to/document.pdf",
  "case_context": { ... }
}
```

### 2. 이미지 분석
```http
POST /analysis/img
Content-Type: application/json

{
  "file_id": "img-123-456",
  "file_path": "/path/to/image.jpg",
  "case_context": { ... }
}
```

### 3. 파일 업로드
```http
POST /analysis/upload
Content-Type: multipart/form-data

case_id: "2e6b7f2a-6b1d-4c9e-9e59-4c1b2a7f3d91"
files: [file1, file2, ...]
```

### 4. 채팅
```http
POST /chat/respond
Content-Type: application/json

{
  "case_id": "2e6b7f2a-6b1d-4c9e-9e59-4c1b2a7f3d91",
  "message": "범행 준비의 증거 시간은 어디가 수상한거야?",
  "video_events": [ ... ],
  "case_context": { ... }
}
```

### 5. 분석 콜백 (통합)
```http
POST /cases/{caseId}/analysis/{analysisId}/callback
Content-Type: application/json

{
  "case_id": "2e6b7f2a-6b1d-4c9e-9e59-4c1b2a7f3d91",
  "analysis_id": "dfbde9f8-1234-5678-90ab-cdef12345678",
  "stage": "TRANSCRIPT",
  "payload": { ... }
}
```

**지원하는 콜백 단계:**
- `TRANSCRIPT`: 음성 전사
- `KEY_STATEMENT`: 핵심 진술
- `CONTRADICTION`: 모순 탐지
- `QUESTION`: 추가 질문
- `VIDEO_EVENT`: 비디오 이벤트
- `SUMMARY`: 최종 요약

## 📚 API 문서

서버 실행 후 다음 URL에서 자동 생성된 API 문서를 확인할 수 있습니다:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🔧 개발

### 코드 구조

- **routers/**: API 엔드포인트 정의 (라우팅만)
- **services/**: 비즈니스 로직 구현 (AI 분석 등)
- **models/**: Pydantic 스키마 (요청/응답 검증)
- **core/**: 공통 인프라 (임베딩, 벡터 DB)

### 새 엔드포인트 추가 방법

1. `models/`에 스키마 정의
2. `services/`에 비즈니스 로직 구현
3. `routers/`에 API 엔드포인트 추가
4. `main.py`에 라우터 등록

## 📝 라이센스

MIT License
