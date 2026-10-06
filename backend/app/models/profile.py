from sqlalchemy import Column, Float, ForeignKey, Integer, SmallInteger, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import (
    ActivityLevel,
    ExperienceLevel,
    Sex,
    TrainingLocation,
    UnitSystem,
    db_enum,
)
from app.models.reference import Equipment, FitnessGoal
from app.models.user import User

profile_equipment = Table(
    "profile_equipment",
    Base.metadata,
    Column("profile_id", ForeignKey("user_profiles.id", ondelete="CASCADE"), primary_key=True),
    Column("equipment_id", ForeignKey("equipment.id", ondelete="CASCADE"), primary_key=True),
)


class UserProfile(Base, TimestampMixin):
    """Every field except the ids is optional: a profile is filled in gradually."""

    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    age: Mapped[int | None] = mapped_column(SmallInteger)
    # Measurements are always stored metric; unit_preference only affects display.
    height_cm: Mapped[float | None] = mapped_column(Float)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    sex: Mapped[Sex | None] = mapped_column(db_enum(Sex))
    experience_level: Mapped[ExperienceLevel | None] = mapped_column(db_enum(ExperienceLevel))
    goal_id: Mapped[int | None] = mapped_column(ForeignKey("fitness_goals.id"))
    activity_level: Mapped[ActivityLevel | None] = mapped_column(db_enum(ActivityLevel))
    training_location: Mapped[TrainingLocation | None] = mapped_column(db_enum(TrainingLocation))
    training_days_per_week: Mapped[int | None] = mapped_column(SmallInteger)
    preferred_workout_minutes: Mapped[int | None] = mapped_column(Integer)
    unit_preference: Mapped[UnitSystem] = mapped_column(
        db_enum(UnitSystem), default=UnitSystem.metric
    )

    user: Mapped[User] = relationship(back_populates="profile")
    goal: Mapped[FitnessGoal | None] = relationship()
    equipment: Mapped[list[Equipment]] = relationship(secondary=profile_equipment)
    training_days: Mapped[list["UserTrainingDay"]] = relationship(
        cascade="all, delete-orphan", order_by="UserTrainingDay.weekday"
    )

    @property
    def preferred_training_days(self) -> list[int]:
        return [d.weekday for d in self.training_days]


class UserTrainingDay(Base):
    """A preferred training weekday (0 = Monday ... 6 = Sunday)."""

    __tablename__ = "user_training_days"

    profile_id: Mapped[int] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    weekday: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
