from datetime import date, datetime, timezone
from sqlalchemy import Integer, Float, Date, DateTime, String, ForeignKey, UniqueConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class DailyBehaviorProfile(Base):
    __tablename__ = "daily_behavior_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)

    logon_count: Mapped[int] = mapped_column(Integer, default=0)
    after_hours_logons: Mapped[int] = mapped_column(Integer, default=0)
    file_access_count: Mapped[int] = mapped_column(Integer, default=0)
    file_copied_removable: Mapped[int] = mapped_column(Integer, default=0)
    email_count: Mapped[int] = mapped_column(Integer, default=0)
    email_external_count: Mapped[int] = mapped_column(Integer, default=0)
    email_attachment_count: Mapped[int] = mapped_column(Integer, default=0)
    http_request_count: Mapped[int] = mapped_column(Integer, default=0)
    http_after_hours_count: Mapped[int] = mapped_column(Integer, default=0)
    removable_device_events: Mapped[int] = mapped_column(Integer, default=0)
    total_session_duration: Mapped[float] = mapped_column(Float, default=0.0)

    # Provenance and (where the source has them) event-level label counts. Labels are NEVER model inputs.
    dataset_source: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    event_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anomalous_event_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # JSON or serialized text for rich multi-source features
    features_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_user_daily_behavior"),
    )

    user = relationship("User", back_populates="daily_profiles")
