import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    llm_proxy_url: str = "http://llm-proxy:11435"
    redis_url: str = "redis://redis:6379"
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"

settings = Settings()