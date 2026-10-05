from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import NotFoundError
from app.models import BodyMetric
from app.models.base import utcnow
from app.models.enums import BodyMetricType
from app.schemas.body_metric import BodyMetricCreate

DEFAULT_UNITS = {
    BodyMetricType.weight: "kg",
    BodyMetricType.body_fat: "%",
}  # everything else defaults to cm


def create_metric(db: Session, user_id: int, data: BodyMetricCreate) -> BodyMetric:
    if data.metric_type == BodyMetricType.custom:
        unit = data.unit.strip()
        label = data.custom_label.strip()
    else:
        unit = DEFAULT_UNITS.get(data.metric_type, "cm")
        label = None
    metric = BodyMetric(
        user_id=user_id,
        metric_type=data.metric_type,
        custom_label=label,
        value=data.value,
        unit=unit,
        recorded_at=data.recorded_at or utcnow(),
    )
    db.add(metric)
    db.commit()
    return metric


def list_metrics(db: Session, user_id: int, metric_type: BodyMetricType | None,
                 limit: int, offset: int) -> list[BodyMetric]:
    stmt = select(BodyMetric).where(BodyMetric.user_id == user_id)
    if metric_type:
        stmt = stmt.where(BodyMetric.metric_type == metric_type)
    return list(db.scalars(stmt.order_by(BodyMetric.recorded_at.desc(), BodyMetric.id.desc())
                           .limit(limit).offset(offset)))


def delete_metric(db: Session, user_id: int, metric_id: int) -> None:
    metric = db.scalar(select(BodyMetric).where(BodyMetric.id == metric_id,
                                                BodyMetric.user_id == user_id))
    if metric is None:
        raise NotFoundError("Measurement not found.")
    db.delete(metric)
    db.commit()
