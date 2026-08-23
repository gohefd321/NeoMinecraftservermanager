"""
config.py - Master Node Configuration Settings
"""
import os

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    class Settings(BaseSettings):
        model_config = SettingsConfigDict(case_sensitive=True)

        PROJECT_NAME: str = "NextGen MC Cloud Platform"
        VERSION: str = "2.0.0"
        API_V1_STR: str = "/api/v1"

        # Security
        JWT_SECRET: str = os.getenv("JWT_SECRET", "super-secret-production-key-change-me-123456789")
        JWT_ALGORITHM: str = "HS256"
        ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
        CLUSTER_SECRET: str = os.getenv("MASTER_SECRET", "cluster-master-secret-token")

        # Databases
        REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        POSTGRES_DSN: str = os.getenv("POSTGRES_DSN", "postgresql://mcadmin:mcpassword@localhost:5432/mchosting")

        # Modpack APIs
        CURSEFORGE_API_KEY: str = os.getenv("CURSEFORGE_API_KEY", "")
        
        # Local LLM Endpoint (TabbyAPI / Llama-server)
        LOCAL_LLM_URL: str = os.getenv("LOCAL_LLM_URL", "http://localhost:8080/v1/chat/completions")
        LOCAL_LLM_MODEL: str = os.getenv("LOCAL_LLM_MODEL", "qwen-2.5-32b-instruct")

    settings = Settings()
except ImportError:
    class Settings:
        PROJECT_NAME: str = "NextGen MC Cloud Platform"
        VERSION: str = "2.0.0"
        API_V1_STR: str = "/api/v1"
        JWT_SECRET: str = os.getenv("JWT_SECRET", "super-secret-production-key-change-me-123456789")
        JWT_ALGORITHM: str = "HS256"
        ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
        CLUSTER_SECRET: str = os.getenv("MASTER_SECRET", "cluster-master-secret-token")
        REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        POSTGRES_DSN: str = os.getenv("POSTGRES_DSN", "postgresql://mcadmin:mcpassword@localhost:5432/mchosting")
        CURSEFORGE_API_KEY: str = os.getenv("CURSEFORGE_API_KEY", "")
        LOCAL_LLM_URL: str = os.getenv("LOCAL_LLM_URL", "http://localhost:8080/v1/chat/completions")
        LOCAL_LLM_MODEL: str = os.getenv("LOCAL_LLM_MODEL", "qwen-2.5-32b-instruct")

    settings = Settings()
