from datetime import datetime, timezone
from typing import Any
import uuid
from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("datasets.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    plan: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="analyses")
    user: Mapped["User"] = relationship("User", back_populates="analyses")
    tool_executions: Mapped[list["ToolExecution"]] = relationship(
        "ToolExecution", back_populates="analysis", cascade="all, delete-orphan", order_by="ToolExecution.seq"
    )
    findings: Mapped[list["Finding"]] = relationship(
        "Finding", back_populates="analysis", cascade="all, delete-orphan", order_by="Finding.rank"
    )
    charts: Mapped[list["Chart"]] = relationship("Chart", back_populates="analysis", cascade="all, delete-orphan")
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="analysis", cascade="all, delete-orphan")
    reports: Mapped[list["Report"]] = relationship("Report", back_populates="analysis", cascade="all, delete-orphan")
