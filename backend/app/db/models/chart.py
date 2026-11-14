from typing import Any
import uuid
from sqlalchemy import ForeignKey, Integer, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Chart(Base):
    __tablename__ = "charts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("analyses.id", ondelete="CASCADE"), index=True, nullable=False)
    dataset_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=True)
    finding_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("findings.id", ondelete="SET NULL"), nullable=True)
    tool_execution_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("tool_executions.id", ondelete="SET NULL"), nullable=True)
    chart_type: Mapped[str] = mapped_column(String(64), nullable=False)
    spec: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="charts")
    finding: Mapped["Finding | None"] = relationship("Finding", back_populates="charts")
    versions: Mapped[list["ChartVersion"]] = relationship("ChartVersion", back_populates="chart", cascade="all, delete-orphan", order_by="ChartVersion.version")
