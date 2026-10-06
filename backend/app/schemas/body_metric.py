from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import BodyMetricType

# Plausible ranges per metric guard against typos (e.g. 700 kg).
VALUE_RANGES = {
    BodyMetricType.weight: (25, 400),
    BodyMetricType.body_fat: (2, 70),
    BodyMetricType.waist: (30, 250),
    BodyMetricType.chest: (40, 250),
    BodyMetricType.arm: (10, 100),
    BodyMetricType.thigh: (20, 150),
    BodyMetricType.hip: (40, 250),
    BodyMetricType.neck: (15, 80),
    BodyMetricType.custom: (0, 100000),
}


class BodyMetricCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_type: BodyMetricType
    value: float = Field(gt=0)
    custom_label: str | None = Field(None, max_length=60)
    unit: str | None = Field(None, max_length=16)
    recorded_at: datetime | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.metric_type == BodyMetricType.custom:
            if not (self.custom_label and self.custom_label.strip()):
                raise ValueError("A custom measurement needs a label.")
            if not (self.unit and self.unit.strip()):
                raise ValueError("A custom measurement needs a unit.")
        else:
            low, high = VALUE_RANGES[self.metric_type]
            if not low <= self.value <= high:
                raise ValueError(f"Value should be between {low} and {high}.")
        return self


class BodyMetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    metric_type: BodyMetricType
    custom_label: str | None = None
    value: float
    unit: str
    recorded_at: datetime
