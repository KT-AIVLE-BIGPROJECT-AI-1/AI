"""
환경 변수 및 경로 관리
"""
from pydantic_settings import BaseSettings
from pathlib import Path
from functools import lru_cache


class Settings(BaseSettings):
    """애플리케이션 설정"""
    
    # API Keys
    OPENAI_API_KEY: str
    HUGGINGFACEHUB_API_TOKEN: str
    GOOGLE_API_KEY: str
    
    # 서버 설정
    APP_NAME: str = "AI Legal Analysis API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # AI 모델 설정
    GPT_MODEL: str = "gpt-4o-mini"
    VISION_MODEL: str = "gpt-4o-mini"
    WHISPER_MODEL: str = "large-v3"
    
    # 파일 업로드 설정
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    UPLOAD_DIR: Path = Path("/tmp/uploads")
    
    # 벡터 DB 설정
    CHROMA_PERSIST_DIR: Path = Path("./chroma_db")
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    
    # 형법/판례 경로
    CRIMINAL_LAW_PDF: Path = Path("app/data/criminal_law.pdf")
    PRECEDENTS_JSON: Path = Path("app/data/precedents.json")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """설정 싱글톤 인스턴스 반환"""
    return Settings()


# 경로 관리
class PathManager:
    """파일 경로 관리 클래스"""
    
    @staticmethod
    def get_upload_path(filename: str) -> Path:
        """업로드 파일 경로 생성"""
        settings = get_settings()
        settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        return settings.UPLOAD_DIR / filename
    
    @staticmethod
    def get_temp_path(filename: str) -> Path:
        """임시 파일 경로 생성"""
        temp_dir = Path("/tmp/ai_analysis")
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir / filename
