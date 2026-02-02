# AI 기반 수사 분석 시스템

## 구조

```
└── app/
   ├── main.py                  # FastAPI 진입점
   ├── config.py                # 환경변수 (LAW_API_KEY 포함)
   ├── core/                    # 임베딩, 벡터스토어
   ├── services/                # 비즈니스 로직 (14개)
   ├── models/                  # Pydantic 스키마 (14개)
   ├── routers/                 # API 엔드포인트 (14개)
   └── data/                    # 형법, 판례
```

## 로컬 실행(Local Development)



### 1) 사전 준비 

•	Python 3.11+ (권장: 3.12) <br>
•	(선택) curl 또는 Postman <br>

---
### 2) 가상환경 생성 및 활성화

```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

---

### 3) 의존성 설치

```bash
pip install -r requirements.txt
```
---

### 4) 환경변수 설정

.env.example을 복사해서 .env를 만들고 값을 채웁니다.

```bash
cp .env.example .env
```
---

5) 서버 실행

```bash
uvicorn app.main:app --reload
```

## API 문서

http://localhost:8000/docs