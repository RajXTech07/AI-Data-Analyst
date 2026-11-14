from datetime import datetime, timezone
import uuid
from sqlalchemy import DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    datasets: Mapped[list["Dataset"]] = relationship("Dataset", back_populates="user", cascade="all, delete-orphan")
    analyses: Mapped[list["Analysis"]] = relationship("Analysis", back_populates="user", cascade="all, delete-orphan")
