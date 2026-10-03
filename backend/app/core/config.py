import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env", extra="ignore")

    PROJECT_NAME: str = "CodeSphere - USAR Coding Assessment & Placement Analytics Platform"
    API_V1_STR: str = "/api/v1"
    # Environment
    ENVIRONMENT: str = os.getenv("APP_ENV") or os.getenv("ENVIRONMENT", "development")

    # Authentication & JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "") if (os.getenv("APP_ENV") or os.getenv("ENVIRONMENT", "development")).lower() in ("production", "prod", "staging") else os.getenv("SECRET_KEY", "codesphere-usar-super-secret-jwt-key-2026-production-ready")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    PASSWORD_RESET_EXPIRE_MINUTES: int = int(os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", "30"))

    # Initial Admin Bootstrap (Zero hardcoding in production)
    INITIAL_ADMIN_EMAIL: str = os.getenv("INITIAL_ADMIN_EMAIL", "") if (os.getenv("APP_ENV") or os.getenv("ENVIRONMENT", "development")).lower() in ("production", "prod", "staging") else os.getenv("INITIAL_ADMIN_EMAIL", "placement@ipu.ac.in")
    INITIAL_ADMIN_PASSWORD: str = os.getenv("INITIAL_ADMIN_PASSWORD", "") if (os.getenv("APP_ENV") or os.getenv("ENVIRONMENT", "development")).lower() in ("production", "prod", "staging") else os.getenv("INITIAL_ADMIN_PASSWORD", "admin123")
    INITIAL_ADMIN_NAME: str = os.getenv("INITIAL_ADMIN_NAME", "Dr. A. K. Sharma (Placement Head)")

    # Security & Brute-Force Rate Limiting
    MAX_LOGIN_ATTEMPTS: int = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
    LOCKOUT_DURATION_MINUTES: int = int(os.getenv("LOCKOUT_DURATION_MINUTES", "15"))

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
    
    # Execution Isolation & Sandboxing
    CODESPHERE_EXECUTION_BACKEND: str = os.getenv("CODESPHERE_EXECUTION_BACKEND", "local")
    REQUIRE_DOCKER_SANDBOX: bool = os.getenv("REQUIRE_DOCKER_SANDBOX", "False").lower() in ("true", "1", "yes")
    ALLOW_LOCAL_PROCESS_FALLBACK: bool = os.getenv("ALLOW_LOCAL_PROCESS_FALLBACK", "True").lower() in ("true", "1", "yes")
    
    # Seeder Configuration
    SEED_DEMO_DATA: bool = os.getenv("SEED_DEMO_DATA", "False").lower() in ("true", "1", "yes")
    SEED_STUDENT_PASSWORD: str = os.getenv("SEED_STUDENT_PASSWORD", "student123")
    SEED_STAFF_PASSWORD: str = os.getenv("SEED_STAFF_PASSWORD", "faculty123")

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "*"
    ]

    def validate_production_security(self):
        """
        Validates production configuration fail-fast invariants.
        Raises RuntimeError if insecure defaults or missing secrets are detected.
        Never logs or prints secret values.
        """
        env_val = (os.getenv("APP_ENV") or self.ENVIRONMENT or "").strip().lower()
        is_prod = env_val in ("production", "prod", "staging")
        if not is_prod:
            return

        insecure_secrets = [
            "codesphere-usar-super-secret-jwt-key-2026-production-ready",
            "secret",
            "changeme",
            "password",
            "admin123",
            "123456",
            "replace-with-a-strong-random-32-char-secret-key-for-production"
        ]

        if not self.SECRET_KEY or not self.SECRET_KEY.strip() or self.SECRET_KEY.strip() in insecure_secrets or len(self.SECRET_KEY.strip()) < 32:
            raise RuntimeError(
                "FATAL CONFIGURATION ERROR: A strong, unique SECRET_KEY (at least 32 characters) "
                "must be configured via environment variables for production deployments."
            )

        if not self.INITIAL_ADMIN_EMAIL or not self.INITIAL_ADMIN_EMAIL.strip():
            raise RuntimeError(
                "FATAL CONFIGURATION ERROR: INITIAL_ADMIN_EMAIL is not configured."
            )

        insecure_passwords = [
            "admin123", "password", "123456", "admin", "codesphere",
            "password123", "changeme", "secret", "faculty123", "student123",
            "replace-with-secure-initial-admin-password"
        ]
        if not self.INITIAL_ADMIN_PASSWORD or not self.INITIAL_ADMIN_PASSWORD.strip():
            raise RuntimeError(
                "FATAL CONFIGURATION ERROR: INITIAL_ADMIN_PASSWORD is not configured."
            )

        if self.INITIAL_ADMIN_PASSWORD.strip() in insecure_passwords or len(self.INITIAL_ADMIN_PASSWORD.strip()) < 8:
            raise RuntimeError(
                "FATAL CONFIGURATION ERROR: Insecure INITIAL_ADMIN_PASSWORD detected in production. "
                "You must set a strong, unique initial password (at least 8 characters) via environment variables."
            )

        if self.DATABASE_URL.startswith("sqlite"):
            raise RuntimeError(
                "FATAL CONFIGURATION ERROR: SQLite database cannot be used in a production or staging environment. "
                "Please configure a valid PostgreSQL connection in DATABASE_URL."
            )

settings = Settings()
settings.validate_production_security()

