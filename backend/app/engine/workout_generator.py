"""Turns (goal, experience, days, duration, equipment, location) into a structured weekly plan."""
from collections import Counter
from collections.abc import Iterable

from app.engine.equipment_filter import EquipmentFilter
from app.engine.exercise_selector import ExerciseSelector
from app.engine.prescription import (
    GOAL_RULES,
    MIN_REST,
    WARMUP_MINUTES,
    estimate_seconds,
    kind_of,
    prescribe,
)
from app.engine.split_generator import CONDITIONING, DayTemplate, SplitGenerator, Slot
from app.engine.types import (
    ExerciseInfo,
    GeneratedPlan,
    GenerationInput,
    PlannedDay,
    PlannedExercise,
    level_index,
)

MIN_EXERCISES = 3
MAX_EXERCISES = 10
MAX_ISOLATION_STRENGTH = 2  # strength days stay focused on the big lifts
GAP_FILL_TARGET = 4  # if a day comes up short (limited equipment), try to top it up to this many
EXTRA_PRIORITY = 100


class WorkoutGenerator:
    def __init__(self, exercises: Iterable[ExerciseInfo], splits: SplitGenerator | None = None):
        self.exercises = list(exercises)
        self.splits = splits or SplitGenerator()

    # ------------------------------------------------------------------ public
    def generate(self, inp: GenerationInput) -> GeneratedPlan:
        self._validate(inp)
        goal = inp.goal if inp.goal in GOAL_RULES else "general_fitness"
        equipment = EquipmentFilter(inp.equipment, inp.location)
        selector = ExerciseSelector(self.exercises, equipment, inp.experience, goal)

        warnings: list[str] = []
        if equipment.ignored:
            names = ", ".join(sorted(s.replace("_", " ") for s in equipment.ignored))
            warnings.append(f"Your training location is home (bodyweight), so {names} was left out.")
        if inp.days_per_week == 7:
            warnings.append("Training 7 days a week leaves no full rest day. Consider 5 or 6 for recovery.")

        if inp.split_preference == "custom":
            if not inp.custom_days:
                raise ValueError("A custom split needs custom_days.")
            split_key, templates = "custom", list(inp.custom_days)
            positions = self.splits.layout(len(templates))
        else:
            split_key, split_warnings = self.splits.choose(
                inp.days_per_week, goal, inp.experience, inp.split_preference)
            warnings += split_warnings
            templates = self.splits.build(split_key, inp.days_per_week)
            positions = self.splits.layout(inp.days_per_week)

        budget_seconds = max(0, inp.duration_minutes - WARMUP_MINUTES) * 60
        plan_use: Counter = Counter()
        by_position: dict[int, PlannedDay] = {}
        for position, template in zip(positions, templates):
            day = self._build_day(position, template, selector, goal, inp, budget_seconds, plan_use)
            by_position[position] = day
            for ex in day.exercises:
                plan_use[ex.exercise_id] += 1
            if len(day.exercises) < MIN_EXERCISES:
                warnings.append(
                    f"{day.name} has only {len(day.exercises)} exercise(s): not enough match your equipment "
                    "and experience.")

        days = [
            by_position.get(p) or PlannedDay(p, "Rest", "Recovery", True)
            for p in range(1, 8)
        ]
        warnings += self._coverage_warnings(templates, days, selector)
        label = self.splits.spec(split_key).label if split_key != "custom" else "Custom split"
        return GeneratedPlan(name=label, split=split_key, goal=goal, days=days,
                             equipment=equipment.available, warnings=warnings)

    # ------------------------------------------------------------------ one day
    def _build_day(self, position: int, template: DayTemplate, selector: ExerciseSelector, goal: str,
                   inp: GenerationInput, budget_seconds: int, plan_use: Counter) -> PlannedDay:
        slots = list(template.slots)
        if goal == "fat_loss":
            slots.insert(min(4, len(slots)), CONDITIONING)
        elif goal == "general_fitness":
            slots.append(CONDITIONING)

        used: set[int] = set()
        picked: list[tuple[int, Slot, ExerciseInfo]] = []
        for priority, slot in enumerate(slots):
            ex = selector.select(slot, used, plan_use)
            if ex is not None:
                used.add(ex.id)
                picked.append((priority, slot, ex))

        if goal == "strength":
            kept, isolation_seen = [], 0
            for item in picked:
                if kind_of(item[2]) == "isolation":
                    isolation_seen += 1
                    if isolation_seen > MAX_ISOLATION_STRENGTH:
                        continue
                kept.append(item)
            picked = kept

        # Limited equipment can leave holes: top the day up from the muscles it already trains.
        template_muscles = {s.muscle for s in template.slots}
        extra_priority = EXTRA_PRIORITY
        while len(picked) < GAP_FILL_TARGET:
            ex = selector.select(Slot("", "isolation"), used, plan_use, muscles=template_muscles)
            if ex is None:
                break
            used.add(ex.id)
            picked.append((extra_priority, Slot(ex.primary_muscle, kind_of(ex)), ex))
            extra_priority += 1

        planned = self._prescribe_all(picked, goal, inp.experience)
        planned = self._fit(planned, budget_seconds, {ex.id: ex for _, _, ex in picked})
        planned.sort(key=self._presentation_key)
        timed = {ex.id: ex.is_timed for _, _, ex in picked}
        seconds = sum(estimate_seconds(p.sets, p.rep_min, p.rep_max, p.rest_seconds, timed[p.exercise_id])
                      for p in planned)
        return PlannedDay(position, template.name, template.focus, False, planned,
                          round(seconds / 60) if planned else None)

    @staticmethod
    def _prescribe_all(picked, goal: str, experience: str) -> list[PlannedExercise]:
        planned, lead_given = [], False
        for priority, slot, ex in sorted(picked, key=lambda t: t[0]):
            lead = kind_of(ex) == "compound" and not lead_given
            lead_given = lead_given or lead
            rx = prescribe(ex, goal, experience, lead_compound=lead)
            planned.append(PlannedExercise(ex.id, ex.name, ex.primary_muscle, rx.sets, rx.rep_min,
                                           rx.rep_max, rx.rest_seconds, kind_of(ex), priority))
        return planned

    @staticmethod
    def _seconds(planned: list[PlannedExercise], infos: dict[int, ExerciseInfo]) -> int:
        return sum(estimate_seconds(p.sets, p.rep_min, p.rep_max, p.rest_seconds, infos[p.exercise_id].is_timed)
                   for p in planned)

    def _fit(self, planned: list[PlannedExercise], budget: int, infos: dict[int, ExerciseInfo]
             ) -> list[PlannedExercise]:
        """Trims a day to the session length: drop the least important exercises first (never below the
        minimum), then trim sets, then shorten rests."""
        planned = sorted(planned, key=lambda p: p.priority)[:MAX_EXERCISES]
        while len(planned) > MIN_EXERCISES and self._seconds(planned, infos) > budget:
            planned.pop()  # highest priority number = least important
        if self._seconds(planned, infos) > budget:
            for p in reversed(planned):
                while p.sets > 2 and self._seconds(planned, infos) > budget:
                    p.sets -= 1
        if self._seconds(planned, infos) > budget:
            for p in planned:
                p.rest_seconds = max(MIN_REST, round(p.rest_seconds * 0.75))
        return planned

    @staticmethod
    def _presentation_key(p: PlannedExercise) -> tuple[int, int]:
        """Big lifts first, then accessories, then core, then conditioning."""
        group = {"compound": 0, "isolation": 1, "conditioning": 3}[p.role]
        if group == 1 and p.primary_muscle == "core":
            group = 2
        return group, p.priority

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _validate(inp: GenerationInput) -> None:
        if not 1 <= inp.days_per_week <= 7:
            raise ValueError("days_per_week must be between 1 and 7.")
        if not 10 <= inp.duration_minutes <= 240:
            raise ValueError("duration_minutes must be between 10 and 240.")
        level_index(inp.experience)  # raises KeyError for unknown levels

    @staticmethod
    def _coverage_warnings(templates, days: list[PlannedDay], selector: ExerciseSelector) -> list[str]:
        trained = {e.primary_muscle for d in days for e in d.exercises}
        wanted = {s.muscle for t in templates for s in t.slots if s.role != "conditioning"}
        missing = sorted(m for m in wanted if m not in trained)
        return [f"No {m.replace('_', ' ')} exercise matched your equipment and experience." for m in missing]
