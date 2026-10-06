from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, SmallInteger, String, Table, Text
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
    __table_args__ = (
        CheckConstraint("rep_min >= 1 AND rep_max >= rep_min", name="ck_exercise_rep_range"),
        CheckConstraint("recommended_sets BETWEEN 1 AND 10", name="ck_exercise_sets"),
    )

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
    # Lowest experience level the generator will prescribe this for (difficulty is how hard it is).
    min_experience_level: Mapped[ExperienceLevel] = mapped_column(
        db_enum(ExperienceLevel), default=ExperienceLevel.beginner, server_default="beginner"
    )
    # Compound = multi-joint. Stored explicitly so cardio/plyometric moves can still be classified.
    is_compound: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # Timed exercises (plank, wall sit) use the rep range as seconds.
    is_timed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    rep_min: Mapped[int] = mapped_column(SmallInteger, default=8, server_default="8")
    rep_max: Mapped[int] = mapped_column(SmallInteger, default=12, server_default="12")
    recommended_sets: Mapped[int] = mapped_column(SmallInteger, default=3, server_default="3")

    primary_muscle_group: Mapped[MuscleGroup] = relationship(foreign_keys=[primary_muscle_group_id])
    secondary_muscle_groups: Mapped[list[MuscleGroup]] = relationship(
        secondary=exercise_secondary_muscles
    )
    equipment: Mapped[list[Equipment]] = relationship(secondary=exercise_equipment)

    @property
    def is_custom(self) -> bool:
        return self.owner_user_id is not None
