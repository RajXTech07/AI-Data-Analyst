from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import settings
from app.db.base import Base

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.APP_ENV == "development" and False,  # disable verbose SQL echoing by default
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db() -> None:
    # Import all models to ensure they are registered with Base.metadata
    from app.db import models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # Lightweight schema auto-migration for SQLite
    if settings.DATABASE_URL.startswith("sqlite"):
        from sqlalchemy import text
        with engine.begin() as conn:
            try:
                result = conn.execute(text("PRAGMA table_info(charts)"))
                columns = [row[1] for row in result.fetchall()]
                if columns:
                    if "dataset_id" not in columns:
                        conn.execute(text("ALTER TABLE charts ADD COLUMN dataset_id VARCHAR(36)"))
                    if "current_version" not in columns:
                        conn.execute(text("ALTER TABLE charts ADD COLUMN current_version INTEGER DEFAULT 1"))
            except Exception:
                pass
