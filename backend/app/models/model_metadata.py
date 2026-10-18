from datetime import datetime, timezone
from sqlalchemy import Integer, Float, DateTime, String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class ModelMetadata(Base):
    __tablename__ = "model_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(64), index=True)
    model_version: Mapped[str] = mapped_column(String(32), default="v1.0.0")
    is_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    artifact_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    dataset_split: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # JSON containing precision, recall, f1, roc_auc, pr_auc, accuracy
    metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON containing confusion matrix [[TN, FP], [FN, TP]]
    confusion_matrix_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)

    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
