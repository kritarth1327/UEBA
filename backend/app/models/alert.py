from datetime import date, datetime, timezone
from sqlalchemy import Integer, Float, Date, DateTime, String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)

    # CRITICAL, HIGH, MEDIUM, LOW
    severity: Mapped[str] = mapped_column(String(16), index=True)
    # OPEN, INVESTIGATING, RESOLVED, DISMISSED
    status: Mapped[str] = mapped_column(String(24), default="OPEN", index=True)

    reason: Mapped[str] = mapped_column(String(255))
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Serialized JSON containing detailed evidence, anomalies, activity summary
    evidence_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    detected_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    user = relationship("User", back_populates="alerts")
