"""Exercise history, personal records, volume and performance flags. Read-mostly; records are rebuilt here."""
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.engine.metrics import (
    SessionPerformance,
    VolumeTotals,
    detect_decline,
    estimate_1rm,
    performance_score,
    session_volume,
    top_weight,
    trend_direction,
    week_start,
)
from app.engine.records import detect_records
from app.models import PersonalRecord, WorkoutExercise, WorkoutSession
from app.models.base import utcnow
from app.models.enums import RecordType, WorkoutStatus
from app.schemas.progression import (
    BestOut,
    ExerciseFlagOut,
    ExerciseHistoryOut,
    FlagOut,
    FlagReportOut,
    HistorySessionOut,
    HistorySetOut,
    RecordOut,
    TrainedExerciseOut,
    TrendOut,
    VolumeReportOut,
    VolumeRow,
)
from app.services.exercise_service import get_exercise
from app.services.performance_data import load_logged, load_performances, to_performances

ESTIMATE_NOTE = ("Estimated 1RM uses the Epley formula (weight x (1 + reps / 30)) on sets of 1-12 reps. "
                 "It is an estimate, not a tested max.")
VOLUME_NOTE = "Volume is weight x reps. It's a rough measure of work done, not a measure of results."
RECENT_FLAG_DAYS = 28


def _flag_out(flag) -> FlagOut:
    return FlagOut(code=flag.code, message=flag.message, level=flag.level, detail=flag.detail)


# --------------------------------------------------------------------------- records
def recompute_records(db: Session, user_id: int, exercise_ids) -> None:
    """Rebuild PR events for these exercises from the logged sets (chronological replay). Caller commits."""
    for ex_id in set(exercise_ids):
        oldest_first = list(reversed(load_performances(db, user_id, ex_id)))
        db.execute(delete(PersonalRecord).where(PersonalRecord.user_id == user_id,
                                                PersonalRecord.exercise_id == ex_id))
        for ev in detect_records(oldest_first):
            db.add(PersonalRecord(
                user_id=user_id, exercise_id=ex_id, session_id=ev.session_id, record_type=RecordType(ev.record_type),
                value=ev.value, weight_kg=ev.weight_kg, reps=ev.reps, previous_value=ev.previous_value,
                achieved_on=ev.achieved_on))
    db.flush()


def backfill_records(db: Session) -> int:
    """First start after upgrading from Phase 1: build PR events for workouts that were already logged."""
    if db.scalar(select(PersonalRecord.id).limit(1)) is not None:
        return 0
    pairs = db.execute(
        select(WorkoutSession.user_id, WorkoutExercise.exercise_id).join(
            WorkoutExercise, WorkoutExercise.session_id == WorkoutSession.id)
        .where(WorkoutSession.status == WorkoutStatus.completed).distinct()).all()
    by_user: dict[int, set[int]] = defaultdict(set)
    for user_id, ex_id in pairs:
        by_user[user_id].add(ex_id)
    for user_id, ids in by_user.items():
        recompute_records(db, user_id, ids)
    db.commit()
    return len(pairs)


def list_records(db: Session, user_id: int, *, exercise_id: int | None = None, limit: int = 30) -> list[PersonalRecord]:
    stmt = (select(PersonalRecord).where(PersonalRecord.user_id == user_id)
            .options(selectinload(PersonalRecord.exercise))
            .order_by(PersonalRecord.achieved_on.desc(), PersonalRecord.id.desc()).limit(limit))
    if exercise_id is not None:
        stmt = stmt.where(PersonalRecord.exercise_id == exercise_id)
    return list(db.scalars(stmt))


# --------------------------------------------------------------------------- exercise history
def _session_out(p: SessionPerformance) -> HistorySessionOut:
    sets = p.valid_sets
    e1rms = [estimate_1rm(s.load, s.reps) for s in sets]
    known = [x for x in e1rms if x is not None]
    return HistorySessionOut(
        session_id=p.session_id or 0, performed_on=p.performed_on,
        sets=[HistorySetOut(weight_kg=s.load, reps=s.reps, rir=s.rir, rpe=s.rpe, estimated_1rm_kg=e)
              for s, e in zip(sets, e1rms)],
        volume_kg=session_volume(sets), total_reps=sum(s.reps for s in sets), top_weight_kg=top_weight(sets),
        best_estimated_1rm_kg=max(known) if known else None, score=performance_score(p))


def exercise_history(db: Session, user_id: int, exercise_id: int, limit: int = 10) -> ExerciseHistoryOut:
    exercise = get_exercise(db, user_id, exercise_id)
    perfs = load_performances(db, user_id, exercise_id)  # newest first
    all_sets = [s for p in perfs for s in p.valid_sets]
    weighted = [s for s in all_sets if s.load]

    best = BestOut()
    if weighted:
        heaviest = max(s.load for s in weighted)
        best.weight_kg = heaviest
        best.weight_reps = max(s.reps for s in weighted if s.load == heaviest)
        e1rms = [e for e in (estimate_1rm(s.load, s.reps) for s in weighted) if e is not None]
        best.estimated_1rm_kg = max(e1rms) if e1rms else None
        best.volume_kg = max(session_volume(p.valid_sets) for p in perfs)
    if all_sets:
        top_set = max(all_sets, key=lambda s: (s.reps, s.load or 0))
        best.reps, best.reps_at_weight_kg = top_set.reps, top_set.load

    scored = [(p.performed_on, performance_score(p)) for p in reversed(perfs[:12])]
    scored = [(d, v) for d, v in scored if v is not None]
    direction, change = trend_direction([v for _, v in scored])
    decline = detect_decline([performance_score(p) for p in perfs])

    return ExerciseHistoryOut(
        exercise_id=exercise.id, exercise_name=exercise.name, is_timed=exercise.is_timed, uses_weight=bool(weighted),
        session_count=len(perfs), total_sets=len(all_sets), total_volume_kg=round(sum(session_volume(p.valid_sets) for p in perfs), 2),
        best=best, recent_sessions=[_session_out(p) for p in perfs[:limit]],
        records=[RecordOut.model_validate(r) for r in list_records(db, user_id, exercise_id=exercise_id, limit=20)],
        trend=TrendOut(direction=direction, percent_change=change, points=[v for _, v in scored],
                       dates=[d for d, _ in scored], metric="estimated_1rm_kg" if weighted else "average_reps"),
        flags=[_flag_out(decline)] if decline else [],
        notes=[ESTIMATE_NOTE, VOLUME_NOTE] if weighted else ["Reps are counted per set. Volume applies to weighted sets only."])


def trained_exercises(db: Session, user_id: int) -> list[TrainedExerciseOut]:
    rows = load_logged(db, user_id)
    grouped: dict[int, list] = defaultdict(list)
    for r in rows:
        grouped[r.exercise.id].append(r)
    out = []
    for ex_id, items in grouped.items():
        perfs = to_performances(items)
        loads = [s.load for p in perfs for s in p.valid_sets if s.load]
        flagged = (utcnow().date() - perfs[0].performed_on).days <= RECENT_FLAG_DAYS and \
            detect_decline([performance_score(p) for p in perfs]) is not None
        ex = items[0].exercise
        out.append(TrainedExerciseOut(
            exercise_id=ex_id, name=ex.name, muscle_group=ex.primary_muscle_group.name, session_count=len(perfs),
            last_performed_on=perfs[0].performed_on, best_weight_kg=max(loads) if loads else None, flagged=flagged))
    return sorted(out, key=lambda x: (x.last_performed_on, x.session_count), reverse=True)


# --------------------------------------------------------------------------- volume
def volume_report(db: Session, user_id: int, weeks: int = 8) -> VolumeReportOut:
    today = utcnow().date()
    first_week = week_start(today) - timedelta(weeks=weeks - 1)
    rows = load_logged(db, user_id, since=first_week)

    by_week = {first_week + timedelta(weeks=i): VolumeTotals() for i in range(weeks)}
    muscles: dict[int, tuple[str, VolumeTotals]] = {}
    exercises: dict[int, tuple[str, VolumeTotals]] = {}
    workouts: dict[int, tuple[date, str, VolumeTotals]] = {}
    for r in rows:
        by_week[week_start(r.performed_on)].add(r.sets)
        mg = r.exercise.primary_muscle_group  # primary muscle only; secondary muscles aren't credited
        muscles.setdefault(mg.id, (mg.name, VolumeTotals()))[1].add(r.sets)
        exercises.setdefault(r.exercise.id, (r.exercise.name, VolumeTotals()))[1].add(r.sets)
        workouts.setdefault(r.session_id, (r.performed_on, r.session_name or "Workout", VolumeTotals()))[2].add(r.sets)

    def row(key, label, t):
        return VolumeRow(key=str(key), label=label, volume_kg=t.volume_kg, sets=t.sets, reps=t.reps)

    def ranked(d):
        return [row(k, n, t) for k, (n, t) in sorted(d.items(), key=lambda kv: (kv[1][1].volume_kg, kv[1][1].sets), reverse=True)]

    return VolumeReportOut(
        weeks=weeks, since=first_week,
        by_week=[row(d.isoformat(), d.isoformat(), t) for d, t in by_week.items()],
        by_muscle_group=ranked(muscles), by_exercise=ranked(exercises)[:20],
        by_workout=[row(sid, f"{name}|{d.isoformat()}", t) for sid, (d, name, t) in workouts.items()][:20],
        note=VOLUME_NOTE)


# --------------------------------------------------------------------------- flags
def flag_report(db: Session, user_id: int) -> FlagReportOut:
    grouped: dict[int, list] = defaultdict(list)
    for r in load_logged(db, user_id):
        grouped[r.exercise.id].append(r)
    today = utcnow().date()
    flagged, evaluable = [], 0
    for ex_id, items in grouped.items():
        perfs = to_performances(items)
        if (today - perfs[0].performed_on).days > RECENT_FLAG_DAYS or len(perfs) < 4:
            continue
        evaluable += 1
        flag = detect_decline([performance_score(p) for p in perfs])
        if flag:
            flagged.append(ExerciseFlagOut(exercise_id=ex_id, name=items[0].exercise.name, flag=_flag_out(flag)))
    overall = None
    if len(flagged) >= 3 or (len(flagged) >= 2 and len(flagged) * 2 >= evaluable):
        overall = FlagOut(
            code="broad_decline", level="mild", message="Several exercises are below your normal trend.",
            detail="Your logged numbers have dipped across more than one lift. Sleep, stress, food and total "
                   "training load all affect this, so an easier week may help. This is based only on your logged numbers.")
    return FlagReportOut(exercises=flagged, overall=overall)
