from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    APP_NAME: str = "Real-Time Transcription System"
    DEBUG: bool = True
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173", 
        "http://localhost:8000", 
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000"
    ]
    WS_PING_INTERVAL: float = 20.0
    WS_PING_TIMEOUT: float = 20.0
    
    class Config:
        env_file = ".env"

settings = Settings() 