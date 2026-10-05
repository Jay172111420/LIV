from sqlalchemy import Boolean, Column, ForeignKey, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import ExerciseType, ExperienceLevel, MovementPattern, db_enum
from app.models.reference import Equipment, MuscleGroup

# An exercise needs ALL of its linked equipment. No rows = no equipment needed.
exercise_equipment = Table(
    "exercise_equipment",
    Base.metadata,
    Column("exercise_id", ForeignKey("exercises.id", ondelete="CASCADE"), primary_key=True),
    Column("equipment_id", ForeignKey("equipment.id", ondelete="CASCADE"), primary_key=True),
)

exercise_secondary_muscles = Table(
    "exercise_secondary_muscles",
    Base.metadata,
    Column("exercise_id", ForeignKey("exercises.id", ondelete="CASCADE"), primary_key=True),
    Column("muscle_group_id", ForeignKey("muscle_groups.id", ondelete="CASCADE"), primary_key=True),
)


class Exercise(Base, TimestampMixin):
    """owner_user_id NULL = built-in library exercise; otherwise a user's private custom exercise."""

    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    primary_muscle_group_id: Mapped[int] = mapped_column(ForeignKey("muscle_groups.id"))
    movement_pattern: Mapped[MovementPattern] = mapped_column(db_enum(MovementPattern))
    difficulty: Mapped[ExperienceLevel] = mapped_column(db_enum(ExperienceLevel))
    exercise_type: Mapped[ExerciseType] = mapped_column(db_enum(ExerciseType))
    instructions: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    primary_muscle_group: Mapped[MuscleGroup] = relationship(foreign_keys=[primary_muscle_group_id])
    secondary_muscle_groups: Mapped[list[MuscleGroup]] = relationship(
        secondary=exercise_secondary_muscles
    )
    equipment: Mapped[list[Equipment]] = relationship(secondary=exercise_equipment)

    @property
    def is_custom(self) -> bool:
        return self.owner_user_id is not None
