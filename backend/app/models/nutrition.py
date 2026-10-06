from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import DietaryPreference, RestrictionKind, db_enum
from app.models.user import User


class NutritionProfile(Base, TimestampMixin):
    """Targets and constraints only. The calculation engine arrives in a later phase."""

    __tablename__ = "nutrition_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    calorie_target: Mapped[int | None] = mapped_column(Integer)
    protein_g: Mapped[int | None] = mapped_column(Integer)
    carbs_g: Mapped[int | None] = mapped_column(Integer)
    fat_g: Mapped[int | None] = mapped_column(Integer)
    dietary_preference: Mapped[DietaryPreference] = mapped_column(
        db_enum(DietaryPreference), default=DietaryPreference.no_preference
    )

    user: Mapped[User] = relationship(back_populates="nutrition_profile")
    items: Mapped[list["NutritionRestriction"]] = relationship(
        cascade="all, delete-orphan", order_by="NutritionRestriction.id"
    )

    @property
    def allergies(self) -> list[str]:
        return [i.label for i in self.items if i.kind == RestrictionKind.allergy]

    @property
    def restrictions(self) -> list[str]:
        return [i.label for i in self.items if i.kind == RestrictionKind.restriction]


class NutritionRestriction(Base):
    __tablename__ = "nutrition_restrictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    nutrition_profile_id: Mapped[int] = mapped_column(
        ForeignKey("nutrition_profiles.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[RestrictionKind] = mapped_column(db_enum(RestrictionKind))
    label: Mapped[str] = mapped_column(String(60))
