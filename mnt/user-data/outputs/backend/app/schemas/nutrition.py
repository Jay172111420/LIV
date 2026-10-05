from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import DietaryPreference

_Label = Field(max_length=60)


class NutritionProfileUpdate(BaseModel):
    """Only fields present in the request are changed; an explicit null clears a field."""

    model_config = ConfigDict(extra="forbid")

    calorie_target: int | None = Field(None, ge=800, le=10000)
    protein_g: int | None = Field(None, ge=0, le=1000)
    carbs_g: int | None = Field(None, ge=0, le=1500)
    fat_g: int | None = Field(None, ge=0, le=600)
    dietary_preference: DietaryPreference | None = None
    allergies: list[str] | None = Field(None, max_length=30)
    restrictions: list[str] | None = Field(None, max_length=30)

    @field_validator("allergies", "restrictions")
    @classmethod
    def _clean(cls, v):
        if v is None:
            return v
        cleaned = []
        for item in v:
            item = item.strip()
            if not item:
                continue
            if len(item) > 60:
                raise ValueError("Each entry must be 60 characters or fewer.")
            if item.lower() not in {c.lower() for c in cleaned}:
                cleaned.append(item)
        return cleaned


class NutritionProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    calorie_target: int | None = None
    protein_g: int | None = None
    carbs_g: int | None = None
    fat_g: int | None = None
    dietary_preference: DietaryPreference = DietaryPreference.no_preference
    allergies: list[str] = []
    restrictions: list[str] = []
