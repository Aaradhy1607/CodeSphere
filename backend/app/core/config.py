import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env", extra="ignore")

    PROJECT_NAME: str = "CodeSphere - USAR Coding Assessment & Placement Analytics Platform"
    API_V1_STR: str = "/api/v1"
    # Authentication & JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "codesphere-usar-super-secret-jwt-key-2026-production-ready")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    PASSWORD_RESET_EXPIRE_MINUTES: int = int(os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", "30"))

    # Initial Admin Bootstrap (Zero hardcoding)
    INITIAL_ADMIN_EMAIL: str = os.getenv("INITIAL_ADMIN_EMAIL", "placement@ipu.ac.in")
    INITIAL_ADMIN_PASSWORD: str = os.getenv("INITIAL_ADMIN_PASSWORD", "admin123")
    INITIAL_ADMIN_NAME: str = os.getenv("INITIAL_ADMIN_NAME", "Dr. A. K. Sharma (Placement Head)")

    # Security & Brute-Force Rate Limiting
    MAX_LOGIN_ATTEMPTS: int = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
    LOCKOUT_DURATION_MINUTES: int = int(os.getenv("LOCKOUT_DURATION_MINUTES", "15"))
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # Database & Connection Pooling
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./codesphere.db")
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "20"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "40"))
    DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "1800"))
    DB_POOL_PRE_PING: bool = os.getenv("DB_POOL_PRE_PING", "True").lower() in ("true", "1", "yes")

    # Redis & Distributed Caching
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "True").lower() in ("true", "1", "yes")
    CACHE_DEFAULT_TTL: int = int(os.getenv("CACHE_DEFAULT_TTL", "60"))
    CACHE_PREFIX: str = os.getenv("CACHE_PREFIX", "codesphere:")

    # Distributed Rate Limiting
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "True").lower() in ("true", "1", "yes")
    RATE_LIMIT_DEFAULT_LIMIT: int = int(os.getenv("RATE_LIMIT_DEFAULT_LIMIT", "120"))
    RATE_LIMIT_DEFAULT_WINDOW: int = int(os.getenv("RATE_LIMIT_DEFAULT_WINDOW", "60"))

    # Code Execution Isolation & Concurrency Limit
    CODE_RUNNER_MAX_CONCURRENCY: int = int(os.getenv("CODE_RUNNER_MAX_CONCURRENCY", "8"))
    CODE_RUNNER_TIMEOUT_SECONDS: float = float(os.getenv("CODE_RUNNER_TIMEOUT_SECONDS", "5.0"))

    # Background Processing & Workers
    WORKER_CONCURRENCY: int = int(os.getenv("WORKER_CONCURRENCY", "4"))
    
    # Gemini AI
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    # Allowed College Email Domains
    STUDENT_EMAIL_DOMAIN: str = os.getenv("STUDENT_EMAIL_DOMAIN", "std.ggsipu.ac.in")
    ADMIN_EMAIL_DOMAIN: str = os.getenv("ADMIN_EMAIL_DOMAIN", "ipu.ac.in")
    
    # Google OAuth
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    
    # Judge0
    JUDGE0_API_URL: str = os.getenv("JUDGE0_API_URL", "https://judge0-ce.p.rapidapi.com")
    JUDGE0_API_KEY: str = os.getenv("JUDGE0_API_KEY", "")
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "*"
    ]

settings = Settings()

