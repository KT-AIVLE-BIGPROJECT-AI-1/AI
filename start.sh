#!/bin/bash

echo "================================"
echo "AI Legal Analysis API 서버 시작"
echo "================================"
echo ""

# 환경 변수 확인
if [ ! -f .env ]; then
    echo "⚠️  .env 파일이 없습니다."
    echo "📝 .env.example을 복사하여 .env 파일을 생성하고 API 키를 설정하세요."
    echo ""
    echo "cp .env.example .env"
    echo ""
    exit 1
fi

# 패키지 설치 확인
if [ ! -d "venv" ]; then
    echo "📦 가상환경이 없습니다. 설치를 진행합니다..."
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

echo "✅ 환경 설정 완료"
echo ""

# 서버 실행
echo "🚀 서버를 시작합니다..."
echo "📡 http://localhost:8000"
echo "📚 API 문서: http://localhost:8000/docs"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
