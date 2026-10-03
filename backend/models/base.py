"""SQLAlchemy ORM models. SQLite: run index, alert history, chat log, control state."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Run(Base):
    __tablename__ = "runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    origin_time: Mapped[str] = mapped_column(String(40), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="complete")
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (Index("ix_runs_origin", "origin_time"),)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("runs.run_id"), index=True)
    type: Mapped[str] = mapped_column(String(24))
    severity: Mapped[str] = mapped_column(String(12))
    level: Mapped[str] = mapped_column(String(16))
    entity_id: Mapped[str] = mapped_column(String(32))
    window_start: Mapped[str] = mapped_column(String(40))
    window_end: Mapped[str] = mapped_column(String(40))
    value: Mapped[float] = mapped_column(Float)
    threshold: Mapped[float] = mapped_column(Float)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ChatLog(Base):
    __tablename__ = "chat_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    used_llm: Mapped[bool] = mapped_column(Boolean, default=False)


class ControlState(Base):
    __tablename__ = "control_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
