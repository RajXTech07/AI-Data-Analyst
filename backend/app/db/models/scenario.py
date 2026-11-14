from datetime import datetime, timezone
from typing import Any
import uuid
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("datasets.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    dataset: Mapped["Dataset"] = relationship("Dataset")
    operations: Mapped[list["ScenarioOperation"]] = relationship(
        "ScenarioOperation", back_populates="scenario", cascade="all, delete-orphan", order_by="ScenarioOperation.seq"
    )

class ScenarioOperation(Base):
    __tablename__ = "scenario_operations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    scenario_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("scenarios.id", ondelete="CASCADE"), index=True, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    op_type: Mapped[str] = mapped_column(String(64), nullable=False)  # "filter", "exclude_rows", "override_value", "threshold", "imputation", "merge_groups", "unit_conversion"
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="operations")
