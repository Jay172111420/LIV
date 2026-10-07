"""Turns stored workout data into recommendations, and records what the user does with them."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.engine import progression as eng
from app.engine.metrics import SetPerformance, same_weight, top_weight
from app.errors import AppError, NotFoundError
from app.models import (
    Exercise,
    ExerciseProgressionSetting,
    ProgressionRecommendation,
    UserIncrementPreference,
    UserProfile,
    WorkoutExercise,
    WorkoutSession,
    WorkoutSet,
)
from app.models.base import utcnow
from app.models.enums import (
    ProgressionStrategy,
    RecommendationAction,
    RecommendationChoice,
    UnitSystem,
    WorkoutStatus,
)
from app.schemas.progression import (
    IncrementPreferenceOut,
    ProgressionSettingsIn,
    ProgressionSettingsOut,
    RecommendationResponse,
)
from app.services.exercise_service import get_exercise
from app.services.performance_data import load_performances

MAX_SETS_PER_EXERCISE = 20


def _perf_json(perf) -> dict | None:
    if perf is None:
        return None
    return {"performed_on": perf.performed_on.isoformat(), "sets": [
        {"weight_kg": s.load, "reps": s.reps, "rir": s.rir, "rpe": s.rpe} for s in perf.valid_sets]}


class ProgressionService:
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.engine = eng.ProgressionEngine()
        unit = db.scalar(select(UserProfile.unit_preference).where(UserProfile.user_id == user_id))
        self.imperial = unit == UnitSystem.imperial
        self._prefs: dict[str, float] | None = None

    # ------------------------------------------------------------ settings and increments
    def _category_prefs(self) -> dict[str, float]:
        if self._prefs is None:
            self._prefs = {p.category: p.increment_kg for p in self.db.scalars(
                select(UserIncrementPreference).where(UserIncrementPreference.user_id == self.user_id))}
        return self._prefs

    def _setting(self, exercise_id: int) -> ExerciseProgressionSetting | None:
        return self.db.scalar(select(ExerciseProgressionSetting).where(
            ExerciseProgressionSetting.user_id == self.user_id,
            ExerciseProgressionSetting.exercise_id == exercise_id))

    def _category(self, exercise: Exercise) -> str:
        return eng.equipment_category(e.slug for e in exercise.equipment)

    def _increment(self, category: str, setting) -> float:
        if setting and setting.increment_kg:
            return setting.increment_kg
        return self._category_prefs().get(category) or eng.default_increment_kg(category, self.imperial)

    def get_settings(self, exercise_id: int) -> ProgressionSettingsOut:
        exercise = get_exercise(self.db, self.user_id, exercise_id)
        setting, category = self._setting(exercise_id), self._category(exercise)
        uses_weight = category not in eng.REP_PROGRESSION_CATEGORIES and not exercise.is_timed
        return ProgressionSettingsOut(
            strategy=setting.strategy if setting and setting.strategy else ProgressionStrategy.auto,
            increment_kg=setting.increment_kg if setting else None,
            effective_increment_kg=self._increment(category, setting) if uses_weight or category == "bodyweight" else None,
            default_increment_kg=eng.default_increment_kg(category, self.imperial),
            category=category, uses_weight=uses_weight)

    def update_settings(self, exercise_id: int, data: ProgressionSettingsIn) -> ProgressionSettingsOut:
        get_exercise(self.db, self.user_id, exercise_id)
        setting = self._setting(exercise_id)
        if setting is None:
            setting = ExerciseProgressionSetting(user_id=self.user_id, exercise_id=exercise_id)
            self.db.add(setting)
        setting.strategy = None if data.strategy in (None, ProgressionStrategy.auto) else data.strategy
        setting.increment_kg = data.increment_kg
        self.db.commit()
        return self.get_settings(exercise_id)

    def list_increments(self) -> list[IncrementPreferenceOut]:
        prefs = self._category_prefs()
        return [IncrementPreferenceOut(
            category=c, default_kg=eng.default_increment_kg(c, self.imperial), custom_kg=prefs.get(c),
            effective_kg=prefs.get(c) or eng.default_increment_kg(c, self.imperial))
            for c in eng.CONFIGURABLE_CATEGORIES]

    def set_increment(self, category: str, increment_kg: float | None) -> list[IncrementPreferenceOut]:
        if category not in eng.CONFIGURABLE_CATEGORIES:
            raise NotFoundError("Unknown equipment type.")
        row = self.db.get(UserIncrementPreference, (self.user_id, category))
        if increment_kg is None:
            if row:
                self.db.delete(row)
        elif row:
            row.increment_kg = increment_kg
        else:
            self.db.add(UserIncrementPreference(user_id=self.user_id, category=category, increment_kg=increment_kg))
        self.db.commit()
        self._prefs = None
        return self.list_increments()

    # ------------------------------------------------------------ recommending
    def recommend(self, exercise: Exercise, *, sets: int | None = None, rep_min: int | None = None,
                  rep_max: int | None = None, today: date | None = None,
                  exclude_session_id: int | None = None) -> tuple[eng.Recommendation, dict | None, int | None]:
        """(recommendation, last session snapshot, id of the session it's based on). Reads stored data only."""
        setting = self._setting(exercise.id)
        category = self._category(exercise)
        perfs = load_performances(self.db, self.user_id, exercise.id, limit=eng.DEFAULT_CONFIG.history_window,
                                  exclude_session_id=exclude_session_id)
        strategy = (eng.ProgressionStrategy(setting.strategy.value) if setting and setting.strategy
                    else eng.ProgressionStrategy.auto)
        inp = eng.ProgressionInput(
            sessions=perfs, rep_min=rep_min or exercise.rep_min, rep_max=rep_max or exercise.rep_max,
            sets=sets or exercise.recommended_sets, strategy=strategy, increment_kg=self._increment(category, setting),
            category=category, is_timed=exercise.is_timed, is_bodyweight=category in eng.REP_PROGRESSION_CATEGORIES,
            today=today or utcnow().date(), previous=self._previous_outcome(exercise.id, exclude_session_id),
            exercise_name=exercise.name)
        rec = self.engine.recommend(inp)
        last = perfs[0] if perfs else None
        return rec, _perf_json(last), last.session_id if last else None

    def last_prescription(self, exercise_id: int) -> tuple[int | None, int | None, int | None]:
        """(sets, rep_min, rep_max) from the user's most recent completed workout with this exercise.

        Used for previews, so the suggestion matches how the user actually trains it, not the library default.
        """
        we = self.db.scalar(
            select(WorkoutExercise).join(WorkoutSession, WorkoutSession.id == WorkoutExercise.session_id)
            .where(WorkoutSession.user_id == self.user_id, WorkoutSession.status == WorkoutStatus.completed,
                   WorkoutExercise.exercise_id == exercise_id)
            .order_by(WorkoutSession.performed_on.desc(), WorkoutSession.id.desc())
            .options(selectinload(WorkoutExercise.sets)).limit(1))
        if we is None:
            return None, None, None
        done = [s for s in we.sets if s.is_completed]
        lows = [s.target_reps_min for s in done if s.target_reps_min]
        highs = [s.target_reps_max for s in done if s.target_reps_max]
        return (len(done) or None), (lows[0] if lows else None), (highs[0] if highs else None)

    def _previous_outcome(self, exercise_id: int, exclude_session_id: int | None) -> eng.PreviousOutcome | None:
        row = self.db.scalar(
            select(ProgressionRecommendation)
            .join(WorkoutExercise, WorkoutExercise.id == ProgressionRecommendation.workout_exercise_id)
            .join(WorkoutSession, WorkoutSession.id == WorkoutExercise.session_id)
            .where(ProgressionRecommendation.user_id == self.user_id,
                   ProgressionRecommendation.exercise_id == exercise_id,
                   WorkoutSession.status == WorkoutStatus.completed,
                   ProgressionRecommendation.performed_weight_kg.is_not(None))
            .order_by(WorkoutSession.performed_on.desc(), WorkoutSession.id.desc()).limit(1))
        if row is None:
            return None
        return eng.PreviousOutcome(row.action.value, row.weight_kg, row.performed_weight_kg, row.user_choice.value)

    def build_for_session(self, session: WorkoutSession) -> list[tuple[WorkoutExercise, ProgressionRecommendation]]:
        """A recommendation for each exercise in a freshly started workout. Reads only; the caller attaches them."""
        built = []
        for we in session.exercises:
            first = we.sets[0] if we.sets else None
            rec, last, basis_id = self.recommend(
                we.exercise, sets=len(we.sets) or None,
                rep_min=first.target_reps_min if first else None, rep_max=first.target_reps_max if first else None,
                today=session.performed_on, exclude_session_id=session.id)
            built.append((we, ProgressionRecommendation(
                user_id=self.user_id, exercise_id=we.exercise_id, strategy=ProgressionStrategy(rec.strategy.value),
                action=RecommendationAction(rec.action.value), weight_kg=rec.weight_kg, rep_min=rec.rep_min,
                rep_max=rec.rep_max, reps_goal=rec.reps_goal, sets=rec.sets, increment_kg=rec.increment_kg,
                reason=rec.reason, confidence=rec.confidence, basis=rec.basis, last_session=last,
                basis_session_id=basis_id,
                flags=[{"code": f.code, "message": f.message, "level": f.level, "detail": f.detail}
                       for f in rec.flags])))
        return built

    # ------------------------------------------------------------ user response
    def respond(self, session: WorkoutSession, workout_exercise_id: int, data: RecommendationResponse) -> None:
        we = next((e for e in session.exercises if e.id == workout_exercise_id), None)
        if we is None:
            raise NotFoundError("Exercise not found in this workout.")
        rec = we.recommendation
        if rec is None:
            raise AppError("There's no recommendation for this exercise.", code="no_recommendation")

        weight = reps = None
        if data.choice == "accepted":
            weight, reps = rec.weight_kg, rec.reps_goal
            self._match_set_count(we, rec.sets)
        elif data.choice == "edited":
            weight, reps = data.weight_kg, data.reps
        if data.choice != "ignored":
            for s in we.sets:
                if s.is_completed:
                    continue
                if weight is not None:
                    s.weight_kg = round(weight, 2)
                if reps is not None:
                    s.reps = reps

        rec.user_choice = RecommendationChoice(data.choice)
        rec.chosen_weight_kg = None if weight is None else round(weight, 2)
        rec.chosen_reps = reps
        rec.responded_at = utcnow()
        self.db.commit()

    @staticmethod
    def _match_set_count(we: WorkoutExercise, target: int) -> None:
        """Accepting a recommendation may change the set count (e.g. a deload). Never touches completed sets."""
        target = max(1, min(MAX_SETS_PER_EXERCISE, target))
        while len(we.sets) > target and not we.sets[-1].is_completed and len(we.sets) > 1:
            we.sets.remove(we.sets[-1])
        last = we.sets[-1] if we.sets else None
        while len(we.sets) < target:
            we.sets.append(WorkoutSet(
                set_number=max((s.set_number for s in we.sets), default=0) + 1,
                weight_kg=last.weight_kg if last else None, reps=last.reps if last else None,
                rest_seconds=last.rest_seconds if last else we.rest_seconds,
                target_reps_min=last.target_reps_min if last else None,
                target_reps_max=last.target_reps_max if last else None))

    @staticmethod
    def finalize(session: WorkoutSession) -> None:
        """When a workout is finished, record what was actually lifted next to what was suggested."""
        for we in session.exercises:
            rec = we.recommendation
            if rec is None:
                continue
            done = [s for s in we.sets if s.is_completed and s.reps]
            top = top_weight(SetPerformance(s.weight_kg, s.reps) for s in done)
            rec.performed_weight_kg = top
            if rec.weight_kg is not None:
                rec.followed = top is not None and same_weight(top, rec.weight_kg)
