로컬 실행(Local Development)

1) 사전 준비
	•	Python 3.11+ (권장: 3.12)
	•	(선택) curl 또는 Postman

2) 가상환경 생성 및 활성화

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

3) 의존성 설치

```bash
pip install -r requirements.txt
```

4) 환경변수 설정

.env.example을 복사해서 .env를 만들고 값을 채웁니다.

```bash
cp .env.example .env
```

예시(.env)

```
ENV=local

SPRING_BASE_URL=http://localhost:8080
SPRING_TIMEOUT_SECONDS=5

LLM_PROVIDER=openai
OPENAI_API_KEY=YOUR_KEY
LLM_TIMEOUT_SECONDS=30
```

.env는 .gitignore에 포함되어 Git에 커밋되지 않습니다.

5) 서버 실행
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

	•	API Base URL: http://localhost:8000
	•	Swagger UI: http://localhost:8000/docs

6) 헬스 체크
```bash
curl http://localhost:8000/api/v1/health
```

예상 응답:
```json
{"status":"ok"}
```

7) (선택) 예시 요청

```bash
curl -X POST "http://localhost:8000/api/v1/generate" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test-user","message":"hello"}'
```
