from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UTCDateTime
from app.models.enums import ExperienceLevel, WorkoutStatus, db_enum
from app.models.exercise import Exercise
from app.models.reference import Equipment, FitnessGoal

plan_equipment = Table(
    "plan_equipment",
    Base.metadata,
    Column("plan_id", ForeignKey("workout_plans.id", ondelete="CASCADE"), primary_key=True),
    Column("equipment_id", ForeignKey("equipment.id", ondelete="CASCADE"), primary_key=True),
)


class WorkoutPlan(Base, TimestampMixin):
    __tablename__ = "workout_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    goal_id: Mapped[int | None] = mapped_column(ForeignKey("fitness_goals.id"))
    days_per_week: Mapped[int | None] = mapped_column(SmallInteger)
    experience_level: Mapped[ExperienceLevel | None] = mapped_column(db_enum(ExperienceLevel))
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    goal: Mapped[FitnessGoal | None] = relationship()
    equipment: Mapped[list[Equipment]] = relationship(secondary=plan_equipment)


class WorkoutSession(Base, TimestampMixin):
    """One performed (or planned) workout on a given day."""

    __tablename__ = "workout_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("workout_plans.id", ondelete="SET NULL"))
    performed_on: Mapped[date] = mapped_column(Date, index=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[WorkoutStatus] = mapped_column(db_enum(WorkoutStatus), default=WorkoutStatus.planned)
    notes: Mapped[str | None] = mapped_column(Text)

    plan: Mapped[WorkoutPlan | None] = relationship()
    exercises: Mapped[list["WorkoutExercise"]] = relationship(
        cascade="all, delete-orphan", order_by="WorkoutExercise.position"
    )


class WorkoutExercise(Base):
    __tablename__ = "workout_exercises"
    __table_args__ = (UniqueConstraint("session_id", "position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("workout_sessions.id", ondelete="CASCADE"), index=True
    )
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"))
    position: Mapped[int] = mapped_column(SmallInteger)
    notes: Mapped[str | None] = mapped_column(Text)

    exercise: Mapped[Exercise] = relationship()
    sets: Mapped[list["WorkoutSet"]] = relationship(
        cascade="all, delete-orphan", order_by="WorkoutSet.set_number"
    )


class WorkoutSet(Base):
    __tablename__ = "workout_sets"
    __table_args__ = (UniqueConstraint("workout_exercise_id", "set_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    workout_exercise_id: Mapped[int] = mapped_column(
        ForeignKey("workout_exercises.id", ondelete="CASCADE"), index=True
    )
    set_number: Mapped[int] = mapped_column(SmallInteger)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    reps: Mapped[int | None] = mapped_column(SmallInteger)
    rpe: Mapped[float | None] = mapped_column(Float)  # rate of perceived exertion, 1-10
    rir: Mapped[int | None] = mapped_column(SmallInteger)  # reps in reserve
    rest_seconds: Mapped[int | None] = mapped_column(Integer)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
