from datetime import datetime, timezone
from typing import Any
import uuid
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("analyses.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    observation: Mapped[str] = mapped_column(Text, nullable=False)
    statistical_evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    interpretation: Mapped[str] = mapped_column(Text, nullable=False)
    limitations: Mapped[str] = mapped_column(Text, nullable=False)
    hypothesis_status: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="findings")
    evidence_links: Mapped[list["FindingEvidence"]] = relationship("FindingEvidence", back_populates="finding", cascade="all, delete-orphan")
    charts: Mapped[list["Chart"]] = relationship("Chart", back_populates="finding")


class FindingEvidence(Base):
    __tablename__ = "finding_evidence"

    finding_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("findings.id", ondelete="CASCADE"), primary_key=True
    )
    tool_execution_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tool_executions.id", ondelete="CASCADE"), primary_key=True
    )

    finding: Mapped["Finding"] = relationship("Finding", back_populates="evidence_links")
    tool_execution: Mapped["ToolExecution"] = relationship("ToolExecution", back_populates="finding_links")
