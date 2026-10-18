from datetime import date, datetime, timezone
from sqlalchemy import Integer, Float, Date, DateTime, String, ForeignKey, UniqueConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class ModelPrediction(Base):
    __tablename__ = "model_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)

    ml_threat_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ann_anomaly_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_deviation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    hybrid_risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(16), default="LOW", index=True)

    # Contributing behavioral signals and explanation payload
    contributing_factors_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str] = mapped_column(String(32), default="v1.0.0")

    evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_user_date_prediction"),
    )

    user = relationship("User", back_populates="predictions")
