from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import Equipment, FitnessGoal, User, UserProfile, UserTrainingDay
from app.schemas.profile import ProfileOut, ProfileUpdate

ONBOARDING_FIELDS = (
    "age", "height_cm", "weight_kg", "sex", "experience_level", "goal_id",
    "training_location", "training_days_per_week", "preferred_workout_minutes",
)


def is_onboarding_complete(profile: UserProfile) -> bool:
    return all(getattr(profile, f) is not None for f in ONBOARDING_FIELDS)


def to_out(profile: UserProfile) -> ProfileOut:
    out = ProfileOut.model_validate(profile)
    out.onboarding_complete = is_onboarding_complete(profile)
    return out


def load_equipment(db: Session, ids: list[int]) -> list[Equipment]:
    """Returns active equipment for the given ids, or raises if any id is unknown."""
    if not ids:
        return []
    found = list(db.scalars(select(Equipment).where(Equipment.id.in_(ids), Equipment.is_active)))
    missing = set(ids) - {e.id for e in found}
    if missing:
        raise AppError("One or more equipment items don't exist.", code="invalid_equipment",
                       details=sorted(missing))
    return found


def get_profile(user: User) -> UserProfile:
    return user.profile


def update_profile(db: Session, user: User, data: ProfileUpdate) -> UserProfile:
    profile = user.profile
    changes = data.model_dump(exclude_unset=True)

    equipment_ids = changes.pop("equipment_ids", None)
    weekdays = changes.pop("preferred_training_days", None)

    if "goal_id" in changes and changes["goal_id"] is not None:
        if not db.scalar(select(FitnessGoal.id).where(FitnessGoal.id == changes["goal_id"],
                                                      FitnessGoal.is_active)):
            raise AppError("That fitness goal doesn't exist.", code="invalid_goal")
    if changes.get("unit_preference", "x") is None:
        changes.pop("unit_preference")  # unit preference can't be cleared, only changed

    for field, value in changes.items():
        setattr(profile, field, value)
    if equipment_ids is not None:
        profile.equipment = load_equipment(db, equipment_ids)
    if weekdays is not None:
        profile.training_days = [UserTrainingDay(weekday=d) for d in weekdays]

    db.commit()
    db.refresh(profile)
    return profile
