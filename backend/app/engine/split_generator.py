"""Workout splits: which muscle groups are trained on which day, and how days fall in the week.

A split is registered with `SplitGenerator.register`, so new splits (or user-defined ones) plug in without
touching the generator. Each day is a `DayTemplate`: an ordered list of `Slot`s, most important first.
"""
from collections.abc import Callable
from dataclasses import dataclass

from app.engine.types import level_index


@dataclass(frozen=True)
class Slot:
    muscle: str
    role: str  # "compound" | "isolation" | "conditioning"
    patterns: tuple[str, ...] = ()  # preferred movement patterns; empty = any


@dataclass(frozen=True)
class DayTemplate:
    name: str
    focus: str
    slots: tuple[Slot, ...]


def C(muscle: str, *patterns: str) -> Slot:
    return Slot(muscle, "compound", patterns)


def I(muscle: str, *patterns: str) -> Slot:  # noqa: E741
    return Slot(muscle, "isolation", patterns)


CONDITIONING = Slot("full_body", "conditioning")

# ---- day templates. Variants of the same day (A, B) rotate so repeated days aren't identical. ----
FULL_BODY = [
    DayTemplate("Full body", "Whole body", (
        C("quads", "squat"), C("chest", "push"), C("back", "pull"), C("hamstrings", "hinge"),
        C("shoulders", "push"), I("triceps"), I("biceps"), I("core"), I("calves"))),
    DayTemplate("Full body", "Whole body", (
        C("hamstrings", "hinge"), C("back", "pull"), C("shoulders", "push"), C("quads", "lunge", "squat"),
        C("chest", "push"), I("biceps"), I("core"), I("triceps"), I("calves"))),
    DayTemplate("Full body", "Whole body", (
        C("quads", "squat"), C("back", "pull"), C("chest", "push"), C("glutes", "hinge"),
        I("shoulders"), I("biceps"), I("triceps"), I("core"), I("calves"))),
]
UPPER = [
    DayTemplate("Upper", "Chest, back, shoulders, arms", (
        C("chest", "push"), C("back", "pull"), C("shoulders", "push"), C("back", "pull"),
        I("biceps"), I("triceps"), I("shoulders"), C("chest", "push"), I("core"))),
    DayTemplate("Upper", "Chest, back, shoulders, arms", (
        C("back", "pull"), C("shoulders", "push"), C("chest", "push"), C("back", "pull"),
        I("shoulders", "pull"), I("triceps"), I("biceps"), I("chest"), I("core"))),
]
LOWER = [
    DayTemplate("Lower", "Quads, hamstrings, glutes, calves", (
        C("quads", "squat"), C("hamstrings", "hinge"), C("quads", "lunge"), C("glutes", "hinge"),
        I("hamstrings"), I("quads"), I("calves"), I("core"))),
    DayTemplate("Lower", "Quads, hamstrings, glutes, calves", (
        C("hamstrings", "hinge"), C("quads", "squat"), C("glutes", "hinge"), C("quads", "lunge"),
        I("quads"), I("hamstrings"), I("calves"), I("core"))),
]
PUSH = [
    DayTemplate("Push", "Chest, shoulders, triceps", (
        C("chest", "push"), C("shoulders", "push"), C("chest", "push"), I("shoulders"),
        I("triceps"), I("chest"), I("triceps"))),
    DayTemplate("Push", "Chest, shoulders, triceps", (
        C("shoulders", "push"), C("chest", "push"), C("chest", "push"), I("triceps"),
        I("shoulders"), I("triceps"), I("chest"))),
]
PULL = [
    DayTemplate("Pull", "Back, rear delts, biceps", (
        C("back", "pull"), C("back", "pull"), C("back", "pull"), I("shoulders", "pull"),
        I("biceps"), I("back"), I("biceps"), I("core"))),
    DayTemplate("Pull", "Back, rear delts, biceps", (
        C("back", "pull"), C("back", "pull"), I("shoulders", "pull"), I("biceps"),
        C("back", "pull"), I("biceps"), I("back"), I("core"))),
]
PUSH_QUADS = [
    DayTemplate("Push", "Chest, shoulders, triceps, quads", (
        C("chest", "push"), C("quads", "squat"), C("shoulders", "push"), C("chest", "push"),
        I("triceps"), I("shoulders"), C("quads", "lunge"), I("calves"), I("triceps"))),
]
PULL_HAMS = [
    DayTemplate("Pull", "Back, biceps, hamstrings, glutes", (
        C("back", "pull"), C("hamstrings", "hinge"), C("back", "pull"), C("glutes", "hinge"),
        I("biceps"), I("shoulders", "pull"), I("hamstrings"), I("biceps"), I("core"))),
]
CHEST = [DayTemplate("Chest", "Chest and triceps", (
    C("chest", "push"), C("chest", "push"), I("chest"), C("chest", "push"), I("chest"), I("triceps")))]
BACK = [DayTemplate("Back", "Back and biceps", (
    C("back", "pull"), C("back", "pull"), C("back", "pull"), I("back"), I("biceps"), I("shoulders", "pull")))]
SHOULDERS = [DayTemplate("Shoulders", "Shoulders and core", (
    C("shoulders", "push"), I("shoulders"), C("shoulders", "push"), I("shoulders", "pull"),
    I("shoulders"), I("core")))]
ARMS = [DayTemplate("Arms", "Biceps, triceps, forearms", (
    I("biceps"), I("triceps"), I("biceps"), I("triceps"), I("biceps"), I("triceps"), I("forearms")))]
SHOULDERS_ARMS = [DayTemplate("Shoulders & arms", "Shoulders, biceps, triceps", (
    C("shoulders", "push"), I("shoulders"), I("biceps"), I("triceps"), I("shoulders", "pull"),
    I("biceps"), I("triceps")))]
LEGS = [DayTemplate("Legs", t.focus, t.slots) for t in LOWER]
QUADS = [DayTemplate("Quads & calves", "Quads and calves", (
    C("quads", "squat"), C("quads", "lunge"), I("quads"), C("quads", "squat"), I("calves"), I("calves")))]
POSTERIOR = [DayTemplate("Hamstrings & glutes", "Hamstrings, glutes, core", (
    C("hamstrings", "hinge"), C("glutes", "hinge"), I("hamstrings"), C("hamstrings", "hinge"),
    I("glutes"), I("core")))]


@dataclass(frozen=True)
class SplitSpec:
    key: str
    label: str
    min_days: int
    max_days: int
    # days -> the ordered cycle of (template variants) per training day
    build: Callable[[int], list[list[DayTemplate]]]


def _cycle(*groups: list[DayTemplate]) -> Callable[[int], list[list[DayTemplate]]]:
    return lambda n: [list(groups[i % len(groups)]) for i in range(n)]


def _fixed(by_days: dict[int, list[list[DayTemplate]]]) -> Callable[[int], list[list[DayTemplate]]]:
    return lambda n: by_days[n]


_BASE_SPLITS = [
    SplitSpec("full_body", "Full body", 1, 4, _cycle(FULL_BODY)),
    SplitSpec("upper_lower", "Upper / lower", 2, 6, _cycle(UPPER, LOWER)),
    SplitSpec("push_pull_legs", "Push / pull / legs", 3, 7, _cycle(PUSH, PULL, LEGS)),
    SplitSpec("push_pull", "Push / pull", 2, 6, _cycle(PUSH_QUADS, PULL_HAMS)),
    SplitSpec("bro_split", "Body-part split", 4, 6, _fixed({
        4: [CHEST, BACK, SHOULDERS_ARMS, LEGS],
        5: [CHEST, BACK, SHOULDERS, ARMS, LEGS],
        6: [CHEST, BACK, SHOULDERS, ARMS, QUADS, POSTERIOR],
    })),
]

# Which weekdays (position in the 7-day cycle) are training days, leaving rest days between blocks.
TRAINING_POSITIONS = {
    1: (1,), 2: (1, 4), 3: (1, 3, 5), 4: (1, 2, 4, 5), 5: (1, 2, 3, 5, 6),
    6: (1, 2, 3, 4, 5, 6), 7: (1, 2, 3, 4, 5, 6, 7),
}


class SplitGenerator:
    def __init__(self):
        self._splits: dict[str, SplitSpec] = {s.key: s for s in _BASE_SPLITS}

    def register(self, spec: SplitSpec) -> None:
        """Add or replace a split. This is the extension point for future splits."""
        self._splits[spec.key] = spec

    def keys(self) -> list[str]:
        return list(self._splits)

    def spec(self, key: str) -> SplitSpec:
        return self._splits[key]

    # ---- choosing ----
    def choose(self, days: int, goal: str, experience: str, preference: str = "auto") -> tuple[str, list[str]]:
        """Returns (split key, warnings). Honors the preference when it fits the number of days."""
        warnings: list[str] = []
        if preference and preference != "auto" and preference != "custom":
            spec = self._splits.get(preference)
            if spec and spec.min_days <= days <= spec.max_days:
                return preference, warnings
            label = spec.label if spec else preference
            warnings.append(
                f"{label} doesn't suit {days} training {'day' if days == 1 else 'days'} a week, "
                "so a better-fitting split was chosen instead.")
        return self._auto(days, goal, experience), warnings

    @staticmethod
    def _auto(days: int, goal: str, experience: str) -> str:
        beginner = level_index(experience) == 0
        builds_muscle = goal in ("muscle_gain", "recomposition")
        if days <= 2:
            return "full_body"
        if days == 3:
            return "push_pull_legs" if builds_muscle and not beginner else "full_body"
        if days == 4:
            return "upper_lower"
        if days == 5:
            return "push_pull_legs" if builds_muscle and not beginner else "upper_lower"
        if days == 6:
            return "upper_lower" if beginner else "push_pull_legs"
        return "push_pull_legs"

    # ---- building ----
    def layout(self, days: int) -> tuple[int, ...]:
        return TRAINING_POSITIONS[days]

    def build(self, key: str, days: int) -> list[DayTemplate]:
        """One template per training day. Repeated day types rotate through their A/B variants and
        get a letter suffix (Upper A, Upper B)."""
        variants = self._splits[key].build(days)
        seen: dict[str, int] = {}
        chosen: list[DayTemplate] = []
        for options in variants:
            base = options[0].name
            n = seen.get(base, 0)
            seen[base] = n + 1
            chosen.append(options[n % len(options)])
        totals: dict[str, int] = {}
        for t in chosen:
            totals[t.name] = totals.get(t.name, 0) + 1
        counters: dict[str, int] = {}
        named: list[DayTemplate] = []
        for t in chosen:
            if totals[t.name] > 1:
                idx = counters.get(t.name, 0)
                counters[t.name] = idx + 1
                named.append(DayTemplate(f"{t.name} {chr(65 + idx)}", t.focus, t.slots))
            else:
                named.append(t)
        return named
