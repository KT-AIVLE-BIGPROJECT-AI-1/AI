# API 엔드포인트 매핑

이 문서는 요청하신 엔드포인트와 실제 구현된 파일 간의 매핑을 정리합니다.

## 📡 엔드포인트 목록

### 1. ANALYSIS_DOC → `/analysis/doc`
- **파일 위치**:
  - Router: `app/routers/analysis_document.py`
  - Service: `app/services/analysis_document_service.py`
  - Schema: `app/models/analysis_document_schema.py`

- **기능**: PDF, DOCX, XLSX, TXT 파일을 분석하여 사건과 관련된 핵심 정보를 추출

- **요청 예시**:
```http
POST /analysis/doc
Content-Type: application/json

{
  "file_id": "84b76f99-aee9-4a14-bcd7-a8d7958272fc",
  "file_path": "/path/to/document.pdf",
  "case_context": {
    "case_id": "2e6b7f2a-6b1d-4c9e-9e59-4c1b2a7f3d91",
    "title": "서울시 주택가 벽돌담 골목 스마트폰 강탈 사건"
  }
}
```

---

### 2. ANALYSIS_IMG → `/analysis/img`
- **파일 위치**:
  - Router: `app/routers/analysis_image.py`
  - Service: `app/services/analysis_image_service.py`
  - Schema: `app/models/analysis_image_schema.py`

- **기능**: 이미지 파일을 분석하여 시각적 정보 추출 (GPT Vision 사용)

- **요청 예시**:
```http
POST /analysis/img
Content-Type: application/json

{
  "file_id": "img-123-456",
  "file_path": "/path/to/image.jpg",
  "case_context": { ... }
}
```

---

### 3. INVESTIGATION_FILE → `/analysis/upload`
- **파일 위치**:
  - Router: `app/routers/investigation_file.py`
  - Service: `app/services/investigation_file_service.py`
  - Schema: `app/models/investigation_file_schema.py`

- **기능**: 증거 파일 업로드 및 자동 분류 (document/image/video/audio)

- **요청 예시**:
```http
POST /analysis/upload
Content-Type: multipart/form-data

case_id: "2e6b7f2a-6b1d-4c9e-9e59-4c1b2a7f3d91"
files: [file1.pdf, file2.jpg, ...]
```

---

### 4. CHAT_LOG → `/chat/respond`
- **파일 위치**:
  - Router: `app/routers/chat_log.py`
  - Service: `app/services/chat_log_service.py`
  - Schema: `app/models/chat_log_schema.py`

- **기능**: 사건 분석에 대한 AI 챗봇 질의응답

- **요청 예시**:
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

---

### 5-10. 통합 콜백 API → `/cases/{caseId}/analysis/{analysisId}/callback`

- **파일 위치**:
  - Router: `app/routers/analysis_callback.py`
  - Service: `app/services/analysis_callback_service.py`
  - Schema: `app/models/analysis_callback_schema.py`

- **기능**: 모든 분석 단계의 콜백을 하나의 엔드포인트로 통합 처리

- **지원하는 단계**:
  - `TRANSCRIPT`: 음성 전사
  - `KEY_STATEMENT`: 핵심 진술
  - `CONTRADICTION`: 모순 탐지
  - `QUESTION`: 추가 질문
  - `VIDEO_EVENT`: 비디오 이벤트
  - `SUMMARY`: 최종 요약

- **요청 예시**:

#### 5. TRANSCRIPT
```http
POST /cases/{caseId}/analysis/{analysisId}/callback
Content-Type: application/json

{
  "case_id": "2e6b7f2a-6b1d-4c9e-9e59-4c1b2a7f3d91",
  "analysis_id": "dfbde9f8-1234-5678-90ab-cdef12345678",
  "stage": "TRANSCRIPT",
  "payload": {
    "stage": "TRANSCRIPT",
    "content": [
      {
        "start": 1.0,
        "end": 5.5,
        "speaker": "SPEAKER_1",
        "text": "안녕하세요"
      }
    ]
  }
}
```

#### 6. KEY_STATEMENT
```http
POST /cases/{caseId}/analysis/{analysisId}/callback
Content-Type: application/json

{
  "case_id": "2e6b7f2a-6b1d-4c9e-9e59-4c1b2a7f3d91",
  "analysis_id": "dfbde9f8-1234-5678-90ab-cdef12345678",
  "stage": "KEY_STATEMENT",
  "payload": {
    "stage": "KEY_STATEMENT",
    "tempId": "ks-1",
    "transcript_id": "trans-123",
    "transcript": "피해 금액은 약 155만 원입니다.",
    "description": "피해자는 사건으로 인해 약 155만 원 상당의 스마트폰을 강탈당했다."
  }
}
```

#### 7. CONTRADICTION
```http
POST /cases/{caseId}/analysis/{analysisId}/callback
Content-Type: application/json

{
  "case_id": "2e6b7f2a-6b1d-4c9e-9e59-4c1b2a7f3d91",
  "analysis_id": "dfbde9f8-1234-5678-90ab-cdef12345678",
  "stage": "CONTRADICTION",
  "payload": {
    "stage": "CONTRADICTION",
    "statementTempId_1": "ks-1",
    "statementTempId_2": "ks-5",
    "type": "TIME",
    "description": "시간적 모순이 발견되었습니다...",
    "status": "ONGOING"
  }
}
```

#### 8. QUESTION
```http
POST /cases/{caseId}/analysis/{analysisId}/callback
Content-Type: application/json

{
  "case_id": "2e6b7f2a-6b1d-4c9e-9e59-4c1b2a7f3d91",
  "analysis_id": "dfbde9f8-1234-5678-90ab-cdef12345678",
  "stage": "QUESTION",
  "payload": {
    "stage": "QUESTION",
    "contradictionTempId": "contra-1",
    "question": "정확한 범행 시각은 언제입니까?"
  }
}
```

#### 9. VIDEO_EVENT
```http
POST /cases/{caseId}/analysis/{analysisId}/callback
Content-Type: application/json

{
  "case_id": "2e6b7f2a-6b1d-4c9e-9e59-4c1b2a7f3d91",
  "analysis_id": "dfbde9f8-1234-5678-90ab-cdef12345678",
  "stage": "VIDEO_EVENT",
  "payload": {
    "stage": "VIDEO_EVENT",
    "event_id": "evt-123",
    "origin_name": "cam02_robbery.mp4",
    "start_time": 7.7,
    "end_time": 9.34,
    "event_type": "ASSAULT",
    "event_description": "남성이 피해자에게 접근하여 물리적 접촉 발생"
  }
}
```

#### 10. SUMMARY
```http
POST /cases/{caseId}/analysis/{analysisId}/callback
Content-Type: application/json

{
  "case_id": "2e6b7f2a-6b1d-4c9e-9e59-4c1b2a7f3d91",
  "analysis_id": "dfbde9f8-1234-5678-90ab-cdef12345678",
  "stage": "SUMMARY",
  "payload": {
    "stage": "SUMMARY",
    "summary": "본 사건은 주택가 골목길에서 발생한 강도치상 사건으로...",
    "key_findings": [
      "스마트폰 강탈",
      "피해자 찰과상",
      "CCTV 증거 확보"
    ]
  }
}
```

---

## 🔍 콜백 데이터 조회

저장된 콜백 데이터를 조회할 수 있습니다:

```http
GET /cases/{caseId}/analysis/{analysisId}/callback/{stage}

예시:
GET /cases/2e6b7f2a-6b1d-4c9e-9e59-4c1b2a7f3d91/analysis/dfbde9f8-1234/callback/TRANSCRIPT
```

---

## 📚 추가 엔드포인트

### 헬스 체크
```http
GET /health
```

### 루트 (API 정보)
```http
GET /
```

### 채팅 히스토리 초기화
```http
POST /chat/reset/{case_id}
```

---

## 🎯 사용 흐름 예시

1. **파일 업로드**
   ```
   POST /analysis/upload
   → file_id 반환
   ```

2. **문서/이미지 분석**
   ```
   POST /analysis/doc (또는 /analysis/img)
   → analysis_id 반환
   ```

3. **콜백 처리** (분석 결과를 단계별로 전송)
   ```
   POST /cases/{caseId}/analysis/{analysisId}/callback
   - stage: TRANSCRIPT
   - stage: KEY_STATEMENT
   - stage: CONTRADICTION
   - stage: VIDEO_EVENT
   - stage: SUMMARY
   ```

4. **챗봇 질의응답**
   ```
   POST /chat/respond
   ```
