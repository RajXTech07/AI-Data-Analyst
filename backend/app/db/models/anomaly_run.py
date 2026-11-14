from datetime import datetime, timezone
from typing import Any
import uuid
from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class AnomalyRun(Base):
    __tablename__ = "anomaly_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("datasets.id", ondelete="CASCADE"), index=True, nullable=False)
    column: Mapped[str] = mapped_column(String(255), nullable=False)
    method: Mapped[str] = mapped_column(String(64), nullable=False)  # iqr, zscore, mad, percentile, rolling, seasonal, isolation_forest, lof, rule_based
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    flagged_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_evaluated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    results: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    dataset: Mapped["Dataset"] = relationship("Dataset")
