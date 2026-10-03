import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool, StaticPool, NullPool
from app.core.config import settings

logger = logging.getLogger("codesphere.database")

def normalize_db_url(url: str) -> str:
    """Ensures PostgreSQL URLs use the supported psycopg2 dialect driver."""
    if not url:
        return url
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://") and not url.startswith("postgresql+"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url

# Configure engine arguments based on database dialect
normalized_db_url = normalize_db_url(settings.DATABASE_URL)
is_sqlite = normalized_db_url.startswith("sqlite")
is_postgres = normalized_db_url.startswith("postgresql") or normalized_db_url.startswith("postgres")

if is_sqlite:
    if settings.ENVIRONMENT.lower() in ["production", "prod", "staging"]:
        raise RuntimeError(
            "FATAL CONFIGURATION ERROR: SQLite database cannot be used in a production or staging environment. "
            "Please configure a valid PostgreSQL connection in DATABASE_URL."
        )
    # Use NullPool for SQLite local development to prevent connection starvation
    engine_kwargs = {
        "connect_args": {"check_same_thread": False, "timeout": 30},
        "poolclass": NullPool,
    }
else:
    # Production PostgreSQL Connection Pooling
    engine_kwargs = {
        "poolclass": QueuePool,
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
        "pool_recycle": settings.DB_POOL_RECYCLE,
        "pool_pre_ping": settings.DB_POOL_PRE_PING,
    }

engine = create_engine(normalized_db_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def check_db_health() -> dict:
    """Verifies active database connectivity and returns latency and pool stats."""
    import time
    start_time = time.time()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        latency_ms = (time.time() - start_time) * 1000.0
        
        pool_stats = {}
        if hasattr(engine.pool, "size"):
            pool_stats = {
                "pool_size": engine.pool.size(),
                "checked_in": engine.pool.checkedin(),
                "checked_out": engine.pool.checkedout(),
                "overflow": engine.pool.overflow(),
            }
        
        return {
            "status": "HEALTHY",
            "dialect": engine.dialect.name,
            "latency_ms": round(latency_ms, 2),
            "pool": pool_stats
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "UNHEALTHY",
            "error": str(e),
            "dialect": engine.dialect.name
        }

def auto_migrate_db(target_engine=None):
    """
    Lightweight SQLite schema auto-migrator for new columns without dropping existing data.
    For PostgreSQL in production, Alembic migrations are used.
    """
    active_engine = target_engine or engine
    # Always ensure all tables are created
    Base.metadata.create_all(bind=active_engine)
    
    if active_engine.dialect.name != "sqlite":
        return
    
    with active_engine.connect() as conn:
        # Check users table columns
        try:
            result = conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()
            existing_user_cols = {row[1] for row in result}
            
            if "status" not in existing_user_cols and len(existing_user_cols) > 0:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN status VARCHAR(50) DEFAULT 'ACTIVE'")
            if "failed_login_attempts" not in existing_user_cols and len(existing_user_cols) > 0:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0")
            if "locked_until" not in existing_user_cols and len(existing_user_cols) > 0:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN locked_until DATETIME")
            if "last_login_at" not in existing_user_cols and len(existing_user_cols) > 0:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN last_login_at DATETIME")
            if "updated_at" not in existing_user_cols and len(existing_user_cols) > 0:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN updated_at DATETIME")
        except Exception as e:
            logger.warning(f"[DB Auto-Migrate] Warning on users table: {e}")

        # Check admin_allowlist table columns
        try:
            result = conn.exec_driver_sql("PRAGMA table_info(admin_allowlist)").fetchall()
            existing_admin_cols = {row[1] for row in result}
            if "assigned_role" not in existing_admin_cols and len(existing_admin_cols) > 0:
                conn.exec_driver_sql("ALTER TABLE admin_allowlist ADD COLUMN assigned_role VARCHAR(50) DEFAULT 'ADMIN'")
        except Exception as e:
            logger.warning(f"[DB Auto-Migrate] Warning on admin_allowlist table: {e}")

        # Check questions table columns
        try:
            result = conn.exec_driver_sql("PRAGMA table_info(questions)").fetchall()
            existing_q_cols = {row[1] for row in result}
            
            new_columns = [
                ("question_type", "VARCHAR(50) DEFAULT 'CODING'"),
                ("subject", "VARCHAR(100) DEFAULT 'Data Structures & Algorithms'"),
                ("topic", "VARCHAR(100)"),
                ("subtopic", "VARCHAR(100)"),
                ("blooms_level", "VARCHAR(50) DEFAULT 'APPLY'"),
                ("marks", "INTEGER DEFAULT 100"),
                ("negative_marks", "FLOAT DEFAULT 0.0"),
                ("time_estimate_minutes", "INTEGER DEFAULT 30"),
                ("learning_objective", "TEXT"),
                ("concept_tags", "JSON"),
                ("options", "JSON"),
                ("correct_answer", "TEXT"),
                ("explanation", "TEXT"),
                ("image_url", "VARCHAR(500)"),
                ("image_metadata", "JSON"),
                ("quality_score", "FLOAT DEFAULT 0.0"),
                ("quality_breakdown", "JSON"),
                ("similarity_hash", "VARCHAR(64)"),
                ("similarity_score", "FLOAT DEFAULT 0.0"),
                ("duplicate_of_id", "INTEGER"),
                ("version_number", "INTEGER DEFAULT 1"),
                ("parent_question_id", "INTEGER"),
                ("is_latest", "BOOLEAN DEFAULT 1"),
                ("change_summary", "VARCHAR(255)"),
                ("author_id", "INTEGER"),
                ("reviewer_id", "INTEGER"),
                ("reviewer_feedback", "TEXT"),
                ("reviewed_at", "DATETIME"),
                ("rejection_reason", "TEXT"),
                ("total_attempts", "INTEGER DEFAULT 0"),
                ("correct_attempts", "INTEGER DEFAULT 0"),
                ("average_time_seconds", "FLOAT DEFAULT 0.0"),
                ("experienced_difficulty", "FLOAT DEFAULT 5.0"),
                ("discrimination_index", "FLOAT"),
                ("skip_count", "INTEGER DEFAULT 0"),
            ]

            for col_name, col_def in new_columns:
                if col_name not in existing_q_cols and len(existing_q_cols) > 0:
                    conn.exec_driver_sql(f"ALTER TABLE questions ADD COLUMN {col_name} {col_def}")
        except Exception as e:
            logger.warning(f"[DB Auto-Migrate] Warning on questions table: {e}")

        # Check submissions table columns
        try:
            result = conn.exec_driver_sql("PRAGMA table_info(submissions)").fetchall()
            existing_sub_cols = {row[1] for row in result}
            if "status" not in existing_sub_cols and len(existing_sub_cols) > 0:
                conn.exec_driver_sql("ALTER TABLE submissions ADD COLUMN status VARCHAR(50) DEFAULT 'QUEUED'")
        except Exception as e:
            logger.warning(f"[DB Auto-Migrate] Warning on submissions table: {e}")

        # Check test_cases table columns
        try:
            result = conn.exec_driver_sql("PRAGMA table_info(test_cases)").fetchall()
            existing_tc_cols = {row[1] for row in result}
            if "category" not in existing_tc_cols and len(existing_tc_cols) > 0:
                conn.exec_driver_sql("ALTER TABLE test_cases ADD COLUMN category VARCHAR(50) DEFAULT 'NORMAL'")
        except Exception as e:
            logger.warning(f"[DB Auto-Migrate] Warning on test_cases table: {e}")
        
        conn.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


