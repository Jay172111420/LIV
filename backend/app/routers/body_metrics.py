from fastapi import APIRouter, Query, Response, status

from app.deps import CurrentUser, DbSession
from app.models.enums import BodyMetricType
from app.schemas.body_metric import BodyMetricCreate, BodyMetricOut
from app.services import body_metric_service

router = APIRouter(prefix="/body-metrics", tags=["body-metrics"])


@router.get("", response_model=list[BodyMetricOut])
def list_metrics(user: CurrentUser, db: DbSession, metric_type: BodyMetricType | None = None,
                 limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    return body_metric_service.list_metrics(db, user.id, metric_type, limit, offset)


@router.post("", response_model=BodyMetricOut, status_code=status.HTTP_201_CREATED)
def create_metric(data: BodyMetricCreate, user: CurrentUser, db: DbSession):
    return body_metric_service.create_metric(db, user.id, data)


@router.delete("/{metric_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_metric(metric_id: int, user: CurrentUser, db: DbSession):
    body_metric_service.delete_metric(db, user.id, metric_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
