from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UTCDateTime, utcnow
from app.models.enums import BodyMetricType, db_enum


class BodyMetric(Base, TimestampMixin):
    """One measurement per row, so history and new/custom metric types need no schema change.

    Canonical units: weight kg, body_fat %, circumferences cm.
    """

    __tablename__ = "body_metrics"
    __table_args__ = (Index("ix_body_metrics_user_type_time", "user_id", "metric_type", "recorded_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    metric_type: Mapped[BodyMetricType] = mapped_column(db_enum(BodyMetricType))
    custom_label: Mapped[str | None] = mapped_column(String(60))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16))
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
