from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UTCDateTime
from app.models.enums import (
    ExperienceLevel,
    PlanKind,
    SplitType,
    TrainingLocation,
    WorkoutStatus,
    db_enum,
)
from app.models.exercise import Exercise
from app.models.progression import PersonalRecord, ProgressionRecommendation
from app.models.reference import Equipment, FitnessGoal

plan_equipment = Table(
    "plan_equipment",
    Base.metadata,
    Column("plan_id", ForeignKey("workout_plans.id", ondelete="CASCADE"), primary_key=True),
    Column("equipment_id", ForeignKey("equipment.id", ondelete="CASCADE"), primary_key=True),
)


class WorkoutPlan(Base, TimestampMixin):
    """A generated weekly plan (many days) or a custom workout (exactly one day)."""

    __tablename__ = "workout_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[PlanKind] = mapped_column(
        db_enum(PlanKind), default=PlanKind.custom, server_default="custom"
    )
    split_type: Mapped[SplitType | None] = mapped_column(db_enum(SplitType))
    goal_id: Mapped[int | None] = mapped_column(ForeignKey("fitness_goals.id"))
    days_per_week: Mapped[int | None] = mapped_column(SmallInteger)
    experience_level: Mapped[ExperienceLevel | None] = mapped_column(db_enum(ExperienceLevel))
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    training_location: Mapped[TrainingLocation | None] = mapped_column(db_enum(TrainingLocation))
    # Generator warnings, one per line (e.g. "No biceps exercise matched your equipment").
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    goal: Mapped[FitnessGoal | None] = relationship()
    equipment: Mapped[list[Equipment]] = relationship(
        secondary=plan_equipment, order_by="Equipment.id"
    )
    days: Mapped[list["PlanDay"]] = relationship(
        cascade="all, delete-orphan", order_by="PlanDay.day_index"
    )

    @property
    def workout_count(self) -> int:
        return sum(1 for d in self.days if not d.is_rest)

    @property
    def exercise_count(self) -> int:
        return sum(len(d.exercises) for d in self.days)

    @property
    def start_day_id(self) -> int | None:
        """The first training day, which is what a one-day custom workout starts from."""
        return next((d.id for d in self.days if not d.is_rest and d.exercises), None)

    @property
    def warnings(self) -> list[str]:
        return [line for line in (self.notes or "").split("\n") if line]


class PlanDay(Base):
    """One slot in the weekly cycle (1 = first day). A rest day has no exercises."""

    __tablename__ = "plan_days"
    __table_args__ = (UniqueConstraint("plan_id", "day_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("workout_plans.id", ondelete="CASCADE"), index=True
    )
    day_index: Mapped[int] = mapped_column(SmallInteger)
    name: Mapped[str] = mapped_column(String(120))
    focus: Mapped[str | None] = mapped_column(String(160))
    is_rest: Mapped[bool] = mapped_column(Boolean, default=False)

    exercises: Mapped[list["PlanExercise"]] = relationship(
        cascade="all, delete-orphan", order_by="PlanExercise.position"
    )

    @property
    def estimated_minutes(self) -> int | None:
        if self.is_rest or not self.exercises:
            return None
        from app.engine.prescription import estimate_seconds  # engine stays ORM-free

        total = sum(
            estimate_seconds(e.sets, e.rep_min, e.rep_max, e.rest_seconds, e.exercise.is_timed)
            for e in self.exercises
        )
        return max(1, round(total / 60))


class PlanExercise(Base):
    """An exercise with its prescription (sets, rep range, rest) inside a plan day."""

    __tablename__ = "plan_exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_day_id: Mapped[int] = mapped_column(
        ForeignKey("plan_days.id", ondelete="CASCADE"), index=True
    )
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"))
    position: Mapped[int] = mapped_column(SmallInteger)
    sets: Mapped[int] = mapped_column(SmallInteger)
    rep_min: Mapped[int] = mapped_column(SmallInteger)
    rep_max: Mapped[int] = mapped_column(SmallInteger)
    rest_seconds: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(String(500))

    exercise: Mapped[Exercise] = relationship()


class WorkoutSession(Base, TimestampMixin):
    """One performed (or planned) workout on a given day."""

    __tablename__ = "workout_sessions"
    __table_args__ = (
        # At most one workout in progress per user, enforced by the database.
        Index("uq_one_active_session", "user_id", unique=True,
              sqlite_where=text("status = 'in_progress'"),
              postgresql_where=text("status = 'in_progress'")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("workout_plans.id", ondelete="SET NULL"))
    plan_day_id: Mapped[int | None] = mapped_column(
        ForeignKey("plan_days.id", ondelete="SET NULL")
    )
    name: Mapped[str | None] = mapped_column(String(120))
    performed_on: Mapped[date] = mapped_column(Date, index=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[WorkoutStatus] = mapped_column(db_enum(WorkoutStatus), default=WorkoutStatus.planned)
    notes: Mapped[str | None] = mapped_column(Text)

    plan: Mapped[WorkoutPlan | None] = relationship()
    exercises: Mapped[list["WorkoutExercise"]] = relationship(
        cascade="all, delete-orphan", order_by="WorkoutExercise.position"
    )
    # Phase 2: personal records achieved in this workout.
    records: Mapped[list["PersonalRecord"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="PersonalRecord.id")


class WorkoutExercise(Base):
    __tablename__ = "workout_exercises"
    __table_args__ = (UniqueConstraint("session_id", "position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("workout_sessions.id", ondelete="CASCADE"), index=True
    )
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"))
    position: Mapped[int] = mapped_column(SmallInteger)
    rest_seconds: Mapped[int | None] = mapped_column(Integer)  # prescribed rest between sets
    notes: Mapped[str | None] = mapped_column(Text)

    exercise: Mapped[Exercise] = relationship()
    # Phase 2: the suggestion shown for this exercise when the workout started (null for older workouts).
    recommendation: Mapped[ProgressionRecommendation | None] = relationship(
        uselist=False, cascade="all, delete-orphan")
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
    target_reps_min: Mapped[int | None] = mapped_column(SmallInteger)  # from the plan
    target_reps_max: Mapped[int | None] = mapped_column(SmallInteger)
    notes: Mapped[str | None] = mapped_column(String(500))
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
