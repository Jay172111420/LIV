"""ProgressionEngine: decides what to do next time for one exercise, from what the user actually did.

Pure Python, deterministic, independent of the UI, database and HTTP. Give it the recent sessions (newest
first) and the exercise's target; it returns a recommendation with a plain-language reason.

Rules at a glance (full table in PHASE2.md)
- Double progression (default for weighted work with a rep range): add reps at the same weight until every
  set reaches the top of the range, then add weight and return to the bottom of the range.
- Weight progression (fixed rep target): complete every set at the target reps, then add weight.
- Rep progression (bodyweight, bands, timed): add reps (or seconds); no weight is recommended.
- Hold: progression is switched off for the exercise; the target stays as it was.
- Missing the rep minimum holds the weight; repeated misses at one weight reduce it, then deload.
- RIR/RPE nudges decisions (very easy sets, a bigger jump) but never overrides the rep result on its own
  when data is thin, because self-reported effort is noisy.
- A long break holds, then lowers, the weight. A decline in performance blocks pushing harder.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from app.engine.metrics import (
    PerformanceFlag,
    SessionPerformance,
    SetPerformance,
    detect_decline,
    performance_score,
    same_weight,
    working_sets,
)


class ProgressionStrategy(str, Enum):
    auto = "auto"
    double_progression = "double_progression"
    weight_progression = "weight_progression"
    rep_progression = "rep_progression"
    hold = "hold"


class Action(str, Enum):
    start = "start"  # no history yet
    increase_weight = "increase_weight"
    increase_reps = "increase_reps"
    maintain = "maintain"  # same weight, keep working on the target
    hold = "hold"  # same target, don't push (unstable, paused or returning from a break)
    reduce_weight = "reduce_weight"
    deload = "deload"  # lighter weight and fewer sets for a while


# --------------------------------------------------------------------------- increments
# Kilograms. Configurable per exercise and per equipment category by the user; these are only defaults.
DEFAULT_INCREMENTS_KG: Mapping[str, float] = {
    "barbell": 2.5, "dumbbells": 1.0, "kettlebell": 2.0, "machines": 2.5, "cable_machine": 2.5, "bodyweight": 1.0,
}
# Imperial users get plate-friendly steps instead (5 lb, rounded to 2 decimals of a kilogram).
_LB = 0.45359237
IMPERIAL_INCREMENTS_KG: Mapping[str, float] = {
    "barbell": round(5 * _LB, 2), "dumbbells": round(5 * _LB, 2), "kettlebell": round(4 * _LB, 2),
    "machines": round(5 * _LB, 2), "cable_machine": round(5 * _LB, 2), "bodyweight": round(2.5 * _LB, 2),
}
CONFIGURABLE_CATEGORIES = ("barbell", "dumbbells", "kettlebell", "machines", "cable_machine")
REP_PROGRESSION_CATEGORIES = {"bodyweight", "bands"}
_BODYWEIGHT_GEAR = {"pull_up_bar", "bench", "squat_rack", "bodyweight"}


def equipment_category(slugs: Iterable[str]) -> str:
    """The kind of load an exercise uses, from its equipment slugs. Decides the default increment."""
    gear = set(slugs)
    for slug, category in (("barbell", "barbell"), ("dumbbells", "dumbbells"), ("kettlebell", "kettlebell"),
                           ("machines", "machines"), ("cable_machine", "cable_machine"),
                           ("resistance_bands", "bands")):
        if slug in gear:
            return category
    return "bodyweight"  # nothing, or only a pull-up bar / bench / rack


def default_increment_kg(category: str, imperial: bool = False) -> float:
    table = IMPERIAL_INCREMENTS_KG if imperial else DEFAULT_INCREMENTS_KG
    return table.get(category, table["barbell"] if category != "bands" else table["bodyweight"])


@dataclass(frozen=True)
class ProgressionConfig:
    rep_step: int = 1
    timed_step: int = 5  # seconds
    reduce_pct: float = 0.05  # second miss in a row
    deload_pct: float = 0.10  # third miss in a row
    max_increase_pct: float = 0.10  # one jump never exceeds this share of the current weight
    easy_avg_rir: float = 4.0
    easy_min_rir: float = 3.0
    min_rir_sets: int = 2  # RIR needs at least this many sets logged before it is trusted
    layoff_hold_days: int = 14
    layoff_reduce_days: int = 28
    layoff_reduce_pct: float = 0.10
    history_window: int = 8


DEFAULT_CONFIG = ProgressionConfig()


# --------------------------------------------------------------------------- input and output
@dataclass(frozen=True)
class PreviousOutcome:
    """What Liv suggested last time and what the user actually lifted. Used to word the explanation."""

    action: str
    recommended_weight_kg: float | None
    performed_weight_kg: float | None
    choice: str = "pending"


@dataclass(frozen=True)
class ProgressionInput:
    sessions: Sequence[SessionPerformance]  # newest first
    rep_min: int
    rep_max: int
    sets: int | None = None  # prescribed sets
    strategy: ProgressionStrategy = ProgressionStrategy.auto
    increment_kg: float | None = None
    category: str = "barbell"
    is_timed: bool = False
    is_bodyweight: bool = False  # can be done without added load
    today: date | None = None
    previous: PreviousOutcome | None = None
    exercise_name: str = ""


@dataclass(frozen=True)
class Recommendation:
    action: Action
    strategy: ProgressionStrategy
    weight_kg: float | None
    rep_min: int
    rep_max: int
    reps_goal: int | None  # "aim for at least this on every set"
    sets: int
    reason: str
    increment_kg: float | None = None
    confidence: str = "low"  # low | medium | high
    flags: tuple[PerformanceFlag, ...] = ()
    basis: str = ""  # machine-readable rule id, handy for tests and debugging


@dataclass
class _Assessment:
    weight: float | None
    reps: list[int]
    n: int
    min_reps: int
    below: int
    status: str  # top | in_range | short | mixed | failed
    required_sets: int
    avg_rir: float | None
    min_rir: float | None
    rir_n: int
    easy: bool
    grinding: bool
    sets: list[SetPerformance] = field(default_factory=list)


class ProgressionEngine:
    def __init__(self, config: ProgressionConfig = DEFAULT_CONFIG):
        self.cfg = config

    # ------------------------------------------------------------------ entry point
    def recommend(self, inp: ProgressionInput) -> Recommendation:
        rep_min = max(1, int(inp.rep_min))
        rep_max = max(rep_min, int(inp.rep_max))
        sessions = [s for s in inp.sessions if s.valid_sets][: self.cfg.history_window]
        base_sets = max(1, inp.sets or (len(working_sets(sessions[0].valid_sets)) if sessions else 3))
        ctx = _Ctx(inp, rep_min, rep_max, base_sets, sessions)

        if not sessions:
            return self._start(ctx)

        flags: list[PerformanceFlag] = []
        decline = detect_decline([performance_score(s) for s in sessions])
        if decline:
            flags.append(decline)
        if inp.previous:
            note = self._override_note(inp.previous)
            if note:
                flags.append(note)

        last = sessions[0]
        weight = self._last_weight(last)
        strategy = self._resolve_strategy(inp, weight, rep_min, rep_max)
        ctx.strategy, ctx.flags, ctx.decline = strategy, flags, decline is not None
        ctx.weight = weight
        ctx.increment = inp.increment_kg or default_increment_kg(inp.category)
        ctx.gap = (inp.today - last.performed_on).days if inp.today else 0

        if strategy is ProgressionStrategy.hold:
            return self._explicit_hold(ctx)
        if strategy is ProgressionStrategy.rep_progression:
            return self._rep_progression(ctx)
        return self._weighted(ctx)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _last_weight(session: SessionPerformance) -> float | None:
        ws = working_sets(session.valid_sets)
        return ws[0].load if ws else None

    def _resolve_strategy(self, inp, weight, rep_min, rep_max) -> ProgressionStrategy:
        if inp.strategy is not ProgressionStrategy.auto:
            return inp.strategy
        if inp.is_timed and weight is None:
            return ProgressionStrategy.rep_progression
        if weight is None and (inp.is_bodyweight or inp.category in REP_PROGRESSION_CATEGORIES):
            return ProgressionStrategy.rep_progression
        return (ProgressionStrategy.double_progression if rep_max > rep_min
                else ProgressionStrategy.weight_progression)

    @staticmethod
    def _unit(ctx) -> str:
        return "seconds" if ctx.inp.is_timed else "reps"

    def _assess(self, session: SessionPerformance, ctx, success_reps: int) -> _Assessment:
        ws = list(working_sets(session.valid_sets))
        reps = [s.reps for s in ws]
        n = len(ws)
        below = sum(1 for r in reps if r < ctx.rep_min)
        sets_ok = n >= ctx.base_sets
        if below == 0:
            status = "top" if (sets_ok and all(r >= success_reps for r in reps)) else (
                "in_range" if sets_ok else "short")
        else:
            status = "failed" if below >= max(1, math.ceil(n / 2)) else "mixed"
        rirs = [x for x in (s.effective_rir for s in ws) if x is not None]
        rir_ok = len(rirs) >= self.cfg.min_rir_sets
        avg = sum(rirs) / len(rirs) if rirs else None
        return _Assessment(
            weight=ws[0].load if ws else None, reps=reps, n=n, min_reps=min(reps) if reps else 0, below=below,
            status=status, required_sets=ctx.base_sets, avg_rir=avg, min_rir=min(rirs) if rirs else None,
            rir_n=len(rirs), sets=ws,
            easy=bool(rir_ok and avg >= self.cfg.easy_avg_rir and min(rirs) >= self.cfg.easy_min_rir),
            grinding=bool(rir_ok and avg <= 0.5),
        )

    def _failure_streak(self, ctx, weight: float | None) -> int:
        streak = 0
        for s in ctx.sessions:
            a = self._assess(s, ctx, ctx.rep_max)
            if a.status == "failed" and same_weight(a.weight, weight):
                streak += 1
            else:
                break
        return streak

    def _confidence(self, ctx, used_rir: bool = False) -> str:
        levels = ["low", "medium", "high"]
        i = min(len(ctx.sessions), 3) - 1
        return levels[max(0, i - (1 if used_rir else 0))]

    @staticmethod
    def _override_note(prev: PreviousOutcome) -> PerformanceFlag | None:
        if prev.recommended_weight_kg is None or prev.performed_weight_kg is None:
            return None
        if same_weight(prev.recommended_weight_kg, prev.performed_weight_kg):
            return None
        side = "lighter" if prev.performed_weight_kg < prev.recommended_weight_kg else "heavier"
        return PerformanceFlag(
            code="override_noted", level="info",
            message=f"Last time you used a {side} weight than suggested.",
            detail="This recommendation is based on what you actually lifted, not on what was suggested.")

    def _snap_down(self, weight: float, pct: float, inc: float) -> float:
        """About `pct` lower, on the increment grid, and at least one increment lower."""
        step = inc if inc > 0 else 2.5
        target = round(round(weight * (1 - pct) / step) * step, 2)
        return round(max(0.0, min(target, weight - step)), 2)

    def _step_up(self, weight: float, inc: float, mult: int) -> float:
        cap = max(inc, weight * self.cfg.max_increase_pct)
        return round(weight + min(inc * mult, cap), 2)

    def _make(self, ctx, action, *, weight, reps_goal, reason, sets=None, rep_range=None, used_rir=False, basis=""):
        lo, hi = rep_range or (ctx.rep_min, ctx.rep_max)
        return Recommendation(
            action=action, strategy=ctx.strategy, weight_kg=weight, rep_min=lo, rep_max=hi, reps_goal=reps_goal,
            sets=sets if sets is not None else ctx.base_sets, reason=reason,
            increment_kg=ctx.increment if weight is not None else None,
            confidence=self._confidence(ctx, used_rir), flags=tuple(ctx.flags), basis=basis)

    def _deload_sets(self, ctx) -> int:
        return ctx.base_sets - 1 if ctx.base_sets >= 3 else ctx.base_sets

    # ------------------------------------------------------------------ no history
    def _start(self, ctx) -> Recommendation:
        inp = ctx.inp
        unit = self._unit(ctx)
        rng = f"{ctx.rep_min}" if ctx.rep_min == ctx.rep_max else f"{ctx.rep_min}-{ctx.rep_max}"
        if inp.is_bodyweight or inp.category in REP_PROGRESSION_CATEGORIES or inp.is_timed:
            reason = (f"This is your first logged session for this exercise. Aim for {rng} {unit} with good "
                      "form; this session sets your starting point.")
        else:
            reason = (f"This is your first logged session for this exercise. Choose a weight you can lift for "
                      f"{rng} reps with about 2 reps left in reserve; this session sets your starting point.")
        ctx.strategy = (inp.strategy if inp.strategy is not ProgressionStrategy.auto else
                        ProgressionStrategy.rep_progression if (inp.is_bodyweight or inp.is_timed)
                        else ProgressionStrategy.double_progression if ctx.rep_max > ctx.rep_min
                        else ProgressionStrategy.weight_progression)
        ctx.flags, ctx.increment = [], inp.increment_kg or default_increment_kg(inp.category)
        return self._make(ctx, Action.start, weight=None, reps_goal=None, reason=reason, basis="no_history")

    # ------------------------------------------------------------------ explicit hold
    def _explicit_hold(self, ctx) -> Recommendation:
        return self._make(
            ctx, Action.hold, weight=ctx.weight, reps_goal=None, basis="strategy_hold",
            reason="Progression is switched off for this exercise, so your target stays the same.")

    # ------------------------------------------------------------------ weighted strategies
    def _weighted(self, ctx) -> Recommendation:
        cfg, inp = self.cfg, ctx.inp
        double = ctx.strategy is ProgressionStrategy.double_progression
        success_reps = ctx.rep_max if double else ctx.rep_min
        a = self._assess(ctx.sessions[0], ctx, success_reps)
        weight, inc, unit = ctx.weight, ctx.increment, self._unit(ctx)

        if weight is None:
            return self._make(
                ctx, Action.hold, weight=None, reps_goal=ctx.rep_min, basis="no_weight_logged",
                reason="No weight was logged last session, so there's nothing to progress from. Log the weight "
                       "you use and Liv can suggest the next step.")

        # A long break: ease back in before pushing.
        if ctx.gap >= cfg.layoff_reduce_days:
            lighter = self._snap_down(weight, cfg.layoff_reduce_pct, inc)
            if lighter < weight:
                ctx.flags.append(PerformanceFlag("returning_after_break", f"It has been {ctx.gap} days since you last did this."))
                return self._make(
                    ctx, Action.reduce_weight, weight=lighter, reps_goal=ctx.rep_min, basis="layoff_reduce",
                    reason=f"It's been {ctx.gap} days since you last did this exercise, so start about 10% lighter "
                           "and build back up.")

        streak = self._failure_streak(ctx, weight)
        if streak >= 3:
            return self._make(
                ctx, Action.deload, weight=self._snap_down(weight, cfg.deload_pct, inc), reps_goal=ctx.rep_min,
                sets=self._deload_sets(ctx), basis="deload",
                reason=f"You've been below {ctx.rep_min} {unit} at this weight for {streak} sessions in a row. "
                       "Take a lighter week (about 10% less weight and one fewer set), then build back up.")
        if streak == 2:
            lighter = self._snap_down(weight, cfg.reduce_pct, inc)
            return self._make(
                ctx, Action.reduce_weight, weight=lighter, reps_goal=ctx.rep_min, basis="reduce_after_two_misses",
                reason=f"You've been below {ctx.rep_min} {unit} at this weight for 2 sessions in a row. Drop the "
                       "weight a little to rebuild reps with good form, then work back up.")

        if a.status == "top":
            if ctx.gap >= cfg.layoff_hold_days:
                ctx.flags.append(PerformanceFlag("returning_after_break", f"It has been {ctx.gap} days since you last did this."))
                return self._make(
                    ctx, Action.hold, weight=weight, reps_goal=ctx.rep_min, basis="layoff_hold",
                    reason=f"It's been {ctx.gap} days since you last did this. Repeat the same weight once "
                           "before adding more.")
            mult = 2 if a.easy else 1
            new = self._step_up(weight, inc, mult)
            why = (f"You reached the top of your target range ({ctx.rep_max} {unit}) on all {a.n} sets last session, "
                   f"so add weight and work back up from {ctx.rep_min}." if double else
                   f"You completed every set at {ctx.rep_min}+ {unit} last session, so add weight and keep the reps "
                   "the same.")
            if mult == 2 and new - weight > inc + 1e-9:
                why += " You also logged 4+ reps in reserve on every set, so a slightly bigger jump is suggested."
            elif a.grinding:
                why += " Those sets were close to failure, so expect the first session at the new weight to feel hard."
            return self._make(ctx, Action.increase_weight, weight=new, reps_goal=ctx.rep_min,
                              used_rir=mult == 2, basis="top_of_range" if double else "target_met", reason=why)

        # Very easy by RIR, but not at the top yet: one increment. Needs enough RIR data to be trusted.
        if a.status == "in_range" and a.easy and ctx.gap < cfg.layoff_hold_days:
            return self._make(
                ctx, Action.increase_weight, weight=self._step_up(weight, inc, 1), reps_goal=ctx.rep_min,
                used_rir=True, basis="easy_by_rir",
                reason=f"You logged 4+ reps in reserve on every set, so this weight looks light for {ctx.rep_min}-"
                       f"{ctx.rep_max} {unit}. RIR is self-reported, so treat this as a suggestion.")

        # A recent decline blocks pushing harder.
        if ctx.decline and a.status in ("in_range", "short", "mixed", "failed"):
            return self._make(
                ctx, Action.hold, weight=weight, reps_goal=max(ctx.rep_min, a.min_reps), basis="decline_hold",
                reason="Your recent performance is below your normal trend, so hold your current target instead "
                       "of pushing harder.")

        if a.status == "in_range":
            step = self.cfg.rep_step * (2 if a.easy else 1)
            if not double:
                return self._make(ctx, Action.maintain, weight=weight, reps_goal=ctx.rep_min, basis="not_yet_target",
                                  reason=f"Keep this weight and aim for at least {ctx.rep_min} {unit} on every set.")
            goal = min(ctx.rep_max, max(ctx.rep_min, a.min_reps + step))
            return self._make(
                ctx, Action.increase_reps, weight=weight, reps_goal=goal, used_rir=a.easy, basis="add_reps",
                reason=f"Your lowest set last session was {a.min_reps} {unit}. Stay at this weight and aim for "
                       f"{goal} on every set; once every set reaches {ctx.rep_max}, add weight.")
        if a.status == "short":
            return self._make(
                ctx, Action.maintain, weight=weight, reps_goal=ctx.rep_min, basis="short_on_sets",
                reason=f"You logged {a.n} of {a.required_sets} sets last session. Complete all {a.required_sets} "
                       "sets at this weight before progressing.")
        if a.status == "mixed":
            return self._make(
                ctx, Action.maintain, weight=weight, reps_goal=ctx.rep_min, basis="mixed_sets",
                reason=f"{a.below} of {a.n} sets fell below {ctx.rep_min} {unit}. Keep this weight and aim to get "
                       f"every set to at least {ctx.rep_min}.")
        return self._make(  # failed once
            ctx, Action.maintain, weight=weight, reps_goal=ctx.rep_min, basis="missed_minimum",
            reason=f"Most sets last session were below {ctx.rep_min} {unit}. Stay at this weight rather than adding "
                   f"more, and aim for {ctx.rep_min} on every set.")

    # ------------------------------------------------------------------ bodyweight / timed
    def _rep_progression(self, ctx) -> Recommendation:
        cfg = self.cfg
        a = self._assess(ctx.sessions[0], ctx, ctx.rep_max)
        unit = self._unit(ctx)
        step = cfg.timed_step if ctx.inp.is_timed else cfg.rep_step
        if a.easy and not ctx.inp.is_timed:
            step *= 2
        ctx.increment = None
        streak = self._failure_streak(ctx, None)

        if streak >= 3:
            return self._make(
                ctx, Action.deload, weight=None, reps_goal=ctx.rep_min, sets=self._deload_sets(ctx), basis="deload",
                reason=f"You've been below {ctx.rep_min} {unit} for {streak} sessions in a row. Take a lighter week "
                       "with one fewer set or an easier variation, then build back up.")
        if a.status in ("failed", "mixed"):
            hint = " Consider an easier variation if this keeps happening." if streak >= 2 else ""
            return self._make(
                ctx, Action.maintain, weight=None, reps_goal=ctx.rep_min, basis="missed_minimum",
                reason=f"{a.below} of {a.n} sets were below {ctx.rep_min} {unit}. Aim for {ctx.rep_min} on every "
                       f"set before adding more.{hint}")
        if ctx.gap >= cfg.layoff_hold_days:
            return self._make(
                ctx, Action.hold, weight=None, reps_goal=a.min_reps, basis="layoff_hold",
                reason=f"It's been {ctx.gap} days since you last did this. Repeat last session's numbers before "
                       "adding more.")
        if ctx.decline:
            return self._make(
                ctx, Action.hold, weight=None, reps_goal=a.min_reps, basis="decline_hold",
                reason="Your recent performance is below your normal trend, so hold your current target instead "
                       "of pushing harder.")
        if a.status == "short":
            return self._make(
                ctx, Action.maintain, weight=None, reps_goal=a.min_reps, basis="short_on_sets",
                reason=f"You logged {a.n} of {a.required_sets} sets last session. Complete all {a.required_sets} "
                       "sets before adding reps.")
        goal = a.min_reps + step
        over = a.min_reps >= ctx.rep_max
        reason = (f"Your lowest set last session was {a.min_reps} {unit}. Aim for {goal} on every set.")
        if over:
            reason += " You're past the top of your range, so consider a harder variation or adding weight."
        return self._make(ctx, Action.increase_reps, weight=None, reps_goal=goal, used_rir=a.easy,
                          rep_range=(goal, max(ctx.rep_max, goal)) if over else (min(goal, ctx.rep_max), ctx.rep_max),
                          basis="add_reps_bodyweight", reason=reason)


@dataclass
class _Ctx:
    inp: ProgressionInput
    rep_min: int
    rep_max: int
    base_sets: int
    sessions: list
    strategy: ProgressionStrategy = ProgressionStrategy.double_progression
    flags: list = field(default_factory=list)
    decline: bool = False
    weight: float | None = None
    increment: float = 2.5
    gap: int = 0
