from datetime import datetime, timezone
import uuid
from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("analyses.id", ondelete="CASCADE"), index=True, nullable=False)
    format: Mapped[str] = mapped_column(String(32), nullable=False)  # pdf, html
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="reports")
