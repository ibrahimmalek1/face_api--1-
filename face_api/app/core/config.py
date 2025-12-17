from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # AWS Configuration
    aws_id: str
    aws_secret: str
    aws_s3_bucket: str
    region: str = "us-east-1"
    
    # --- NEW: MySQL Database Configuration ---
    # These match the variables used in FaceService
    mysql_host: str = "localhost"
    mysql_user: str = "root"
    mysql_password: str = ""   # Put your password here or in .env
    mysql_db: str = "face_db"
    mysql_port: int = 3306
    # -----------------------------------------
    
    # API Configuration
    api_title: str = "Face Detection API"
    api_version: str = "1.0.0"
    debug: bool = False
    
    # File Upload Configuration
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: list = [".jpg", ".jpeg", ".png", ".bmp"]
    
    # Face Detection Configuration
    similarity_threshold: float = 0.3
    face_model_name: str = "Facenet"
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "protected_namespaces": ('settings_',)
    }

settings = Settings()