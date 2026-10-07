"""Phase 2 tables: stored recommendations (with the user's response), PR events, progression settings."""
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, Float, ForeignKey, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UTCDateTime
from app.models.enums import (
    ProgressionStrategy,
    RecommendationAction,
    RecommendationChoice,
    RecordType,
    db_enum,
)


class ProgressionRecommendation(Base, TimestampMixin):
    """What Liv suggested for one exercise in one workout, frozen when the workout started.

    Frozen on purpose: the suggestion and its explanation must not shift while the user is mid-workout.
    `user_choice` and `chosen_*` record what the user did with it; `performed_*` is filled in when the
    workout is finished.
    """

    __tablename__ = "progression_recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    workout_exercise_id: Mapped[int] = mapped_column(
        ForeignKey("workout_exercises.id", ondelete="CASCADE"), unique=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"), index=True)

    strategy: Mapped[ProgressionStrategy] = mapped_column(db_enum(ProgressionStrategy))
    action: Mapped[RecommendationAction] = mapped_column(db_enum(RecommendationAction))
    weight_kg: Mapped[float | None] = mapped_column(Float)
    rep_min: Mapped[int] = mapped_column(SmallInteger)
    rep_max: Mapped[int] = mapped_column(SmallInteger)
    reps_goal: Mapped[int | None] = mapped_column(SmallInteger)
    sets: Mapped[int] = mapped_column(SmallInteger)
    increment_kg: Mapped[float | None] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(String(10), default="low")
    basis: Mapped[str | None] = mapped_column(String(40))
    flags: Mapped[list] = mapped_column(JSON, default=list)
    # The previous session as the recommendation saw it: {"performed_on", "sets": [{weight_kg, reps, rir, rpe}]}
    last_session: Mapped[dict | None] = mapped_column(JSON)
    basis_session_id: Mapped[int | None] = mapped_column(ForeignKey("workout_sessions.id", ondelete="SET NULL"))

    user_choice: Mapped[RecommendationChoice] = mapped_column(
        db_enum(RecommendationChoice), default=RecommendationChoice.pending, server_default="pending")
    chosen_weight_kg: Mapped[float | None] = mapped_column(Float)
    chosen_reps: Mapped[int | None] = mapped_column(SmallInteger)
    responded_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    performed_weight_kg: Mapped[float | None] = mapped_column(Float)
    followed: Mapped[bool | None] = mapped_column(Boolean)  # did the top weight match the suggestion?


class PersonalRecord(Base):
    """One PR event. Rebuilt from workout history, so it is always consistent with the logged sets."""

    __tablename__ = "personal_records"
    __table_args__ = (UniqueConstraint("session_id", "exercise_id", "record_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"), index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("workout_sessions.id", ondelete="CASCADE"), index=True)
    record_type: Mapped[RecordType] = mapped_column(db_enum(RecordType))
    value: Mapped[float] = mapped_column(Float)  # kg for weight, reps for reps, kg for volume
    weight_kg: Mapped[float | None] = mapped_column(Float)
    reps: Mapped[int | None] = mapped_column(SmallInteger)
    previous_value: Mapped[float | None] = mapped_column(Float)
    achieved_on: Mapped[date] = mapped_column(Date, index=True)

    exercise = relationship("Exercise")

    @property
    def exercise_name(self) -> str:
        return self.exercise.name


class ExerciseProgressionSetting(Base):
    """A user's override for one exercise. NULL fields fall back to automatic behaviour and defaults."""

    __tablename__ = "exercise_progression_settings"
    __table_args__ = (UniqueConstraint("user_id", "exercise_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id", ondelete="CASCADE"))
    strategy: Mapped[ProgressionStrategy | None] = mapped_column(db_enum(ProgressionStrategy))
    increment_kg: Mapped[float | None] = mapped_column(Float)


class UserIncrementPreference(Base):
    """A user's weight step for an equipment category (e.g. machines: 5 kg)."""

    __tablename__ = "user_increment_preferences"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    category: Mapped[str] = mapped_column(String(20), primary_key=True)
    increment_kg: Mapped[float] = mapped_column(Float)
