from sqlalchemy.orm import Session

from app.models import NutritionProfile, NutritionRestriction, User
from app.models.enums import RestrictionKind
from app.schemas.nutrition import NutritionProfileUpdate


def update_nutrition_profile(db: Session, user: User, data: NutritionProfileUpdate) -> NutritionProfile:
    profile = user.nutrition_profile
    changes = data.model_dump(exclude_unset=True)
    allergies = changes.pop("allergies", None)
    restrictions = changes.pop("restrictions", None)
    if changes.get("dietary_preference", "x") is None:
        changes.pop("dietary_preference")  # can't be cleared, only changed

    for field, value in changes.items():
        setattr(profile, field, value)

    if allergies is not None or restrictions is not None:
        current = {RestrictionKind.allergy: profile.allergies,
                   RestrictionKind.restriction: profile.restrictions}
        if allergies is not None:
            current[RestrictionKind.allergy] = allergies
        if restrictions is not None:
            current[RestrictionKind.restriction] = restrictions
        profile.items = [NutritionRestriction(kind=kind, label=label)
                         for kind, labels in current.items() for label in labels]

    db.commit()
    db.refresh(profile)
    return profile
