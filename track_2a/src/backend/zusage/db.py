"""Persistence: SQLModel over SQLite (default) or PostgreSQL.

SQLite keeps the on-premise story simple - one file in a Docker volume, no
extra service - while ``ZUSAGE_DATABASE_URL=postgresql+psycopg://...`` moves
a cantonal deployment onto a managed database without code changes.

Data minimisation is built into the schema: students need no e-mail address,
only a username; transcripts live inside ``Interview.state`` and are purged
after ``transcript_retention_days`` while scores (needed for progress) stay.
"""

from __future__ import annotations

import secrets
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlalchemy.pool import StaticPool
from sqlmodel import Field, Session, SQLModel, create_engine


def new_id() -> str:
    return uuid.uuid4().hex[:16]


def utcnow() -> datetime:
    return datetime.now(UTC)


def aware(value: datetime | None) -> datetime | None:
    """Treat naive datetimes (e.g. from a browser date picker) as UTC."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def join_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I confusion for 14-year-olds
    return "".join(secrets.choice(alphabet) for _ in range(6))


class User(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    username: str = Field(index=True, unique=True)
    display_name: str
    email: str = ""
    password_hash: str
    role: str = "student"  # student | teacher | admin
    ui_lang: str = "en"
    class_id: str | None = Field(default=None, index=True)
    consent_share: bool = False  # student opts in to share transcripts with their teacher
    onboarded: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class Classroom(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    name: str
    school: str = ""
    teacher_id: str = Field(index=True)
    code: str = Field(default_factory=join_code, index=True, unique=True)
    created_at: datetime = Field(default_factory=utcnow)


class StudentProfile(SQLModel, table=True):
    user_id: str = Field(primary_key=True)
    data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=utcnow)


class Application(SQLModel, table=True):
    """A Lehrstelle the student is pursuing - the tracker card (OfferLoop DNA)."""

    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(index=True)
    company: str
    occupation_id: str = ""
    title: str = ""
    town: str = ""
    posting: str = ""
    status: str = "interested"  # interested | schnupper | applied | interview | offer | rejected
    history: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    interview_at: datetime | None = None
    contact_name: str = ""
    notes: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    deleted_at: datetime | None = None


class Interview(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(index=True)
    application_id: str | None = Field(default=None, index=True)
    occupation_id: str
    language: str
    persona_id: str
    mode: str = "training"  # training | real | drill
    length: str = "full"
    status: str = "active"  # active | completed | abandoned
    state: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    report: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    overall: int | None = None
    confidence_before: int | None = None
    confidence_after: int | None = None
    llm_calls: int = 0
    answers: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    model: str = ""
    created_at: datetime = Field(default_factory=utcnow, index=True)
    completed_at: datetime | None = None


class Drill(SQLModel, table=True):
    """A spaced-repetition practice card (Leitner box system)."""

    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(index=True)
    question_id: str
    occupation_id: str = ""
    criterion: str = ""
    box: int = 1
    due_at: datetime = Field(default_factory=utcnow, index=True)
    last_score: float | None = None
    best_score: float | None = None
    reps: int = 0
    source_interview_id: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Workspace(SQLModel, table=True):
    user_id: str = Field(primary_key=True)
    data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


def make_engine(url: str):
    if url.startswith("sqlite"):
        kwargs: dict[str, Any] = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
        engine = create_engine(url, **kwargs)
    else:
        engine = create_engine(url, pool_pre_ping=True)
    SQLModel.metadata.create_all(engine)
    return engine


def session_scope(engine) -> Iterator[Session]:
    with Session(engine) as session:
        yield session
