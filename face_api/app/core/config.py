from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # AWS Configuration
    aws_id: str
    aws_secret: str
    aws_s3_bucket: str
    region: str = "us-east-1"
    
    # Database Configuration
    database_url: str = "sqlite:///./faces.db"
    
    # API Configuration
    api_title: str = "Face Detection API"
    api_version: str = "1.0.0"
    debug: bool = False
    
    # File Upload Configuration
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: list = [".jpg", ".jpeg", ".png", ".bmp"]
    
    # Face Detection Configuration
    similarity_threshold: float = 0.3
    face_model_name: str = "Facenet"  # Renamed to avoid conflict
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "protected_namespaces": ('settings_',)
    }


settings = Settings()