# app/web_scraper/db.py

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional

from dotenv import load_dotenv
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    create_engine,
    DateTime,
    String,
    Text,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)

from app.web_scraper.embedding_config import EMBEDDING_DIMENSION

load_dotenv()


# ============================================================
# DATABASE URL
# ============================================================

KNOWLEDGEBASE_URL = os.getenv("KNOWLEDGEBASE_URL")

if not KNOWLEDGEBASE_URL:
    raise RuntimeError("KNOWLEDGEBASE_URL is missing from .env")


if KNOWLEDGEBASE_URL.startswith("postgres://"):
    KNOWLEDGEBASE_URL = KNOWLEDGEBASE_URL.replace(
        "postgres://",
        "postgresql+psycopg2://",
        1,
    )
elif KNOWLEDGEBASE_URL.startswith("postgresql://"):
    KNOWLEDGEBASE_URL = KNOWLEDGEBASE_URL.replace(
        "postgresql://",
        "postgresql+psycopg2://",
        1,
    )


# ============================================================
# ENGINE
# ============================================================

engine = create_engine(
    KNOWLEDGEBASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=False,
)


# ============================================================
# SESSION FACTORY
# ============================================================

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


# ============================================================
# BASE MODEL
# ============================================================

class Base(DeclarativeBase):
    pass


# ============================================================
# SCRAPED POST TABLE SCHEMA
# ============================================================

class ScrapedPost(Base):
    __tablename__ = "scraped_posts"

    post_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        index=True,
    )

    post_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    post_img_url: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )

    embedding: Mapped[Optional[list[float]]] = mapped_column(
        Vector(EMBEDDING_DIMENSION),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


Index("idx_scraped_posts_metadata", ScrapedPost.metadata_, postgresql_using="gin")
Index("idx_scraped_posts_created_at", ScrapedPost.created_at)


# ============================================================
# SESSION HELPER
# ============================================================

@contextmanager
def get_db_session() -> Iterator[Session]:
    db = SessionLocal()

    try:
        yield db
        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# ============================================================
# CREATE / MIGRATE TABLES
# ============================================================

def init_db() -> None:
    """
    Creates table for fresh DB.

    Also handles existing table by adding embedding column if missing,
    because SQLAlchemy create_all() does not alter existing tables.
    """

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        conn.execute(
            text(
                f"""
                ALTER TABLE scraped_posts
                ADD COLUMN IF NOT EXISTS embedding vector({EMBEDDING_DIMENSION})
                """
            )
        )