# Phase 1: Dynamic workout generator

A new user can now complete onboarding, generate a personalised weekly plan, edit it, build custom workouts,
run a workout with a rest timer, and review their history. Phase 0 behaviour is unchanged: all 36 Phase 0 tests
still pass.

## Upgrading from Phase 0

Nothing manual. On startup the app creates the new tables, `app/migrate.py` adds the new columns to your existing
`liv.db` (no data is lost), and the seed re-syncs the exercise library. To start clean instead, delete
`backend/liv.db`.

## 1. Architecture changes

- **`backend/app/engine/`** is the workout engine. It is pure Python with no database, HTTP or UI imports, and it is
  deterministic (no randomness; ties break by name/id).

  | Class | File | Job |
  | --- | --- | --- |
  | `WorkoutGenerator` | `workout_generator.py` | Orchestrates: split, days, exercises, prescription, fitting to session length |
  | `SplitGenerator` | `split_generator.py` | Registry of splits, day templates, weekly layout. `register()` adds new splits |
  | `ExerciseSelector` | `exercise_selector.py` | Picks the best exercise for a slot |
  | `EquipmentFilter` | `equipment_filter.py` | The single place that decides if gear allows an exercise |
  | `ExerciseSubstitutionService` | `substitution.py` | Finds and validates replacements |
  | `prescription.py` | | Sets, rep ranges, rest, time estimates |
- **`services/engine_adapter.py`** is the only bridge from database rows to engine objects.
- **`services/plan_service.py`** handles generation, saving, custom workouts and all plan edits.
- **`services/workout_session_service.py`** (`WorkoutSessionService`) handles starting, logging, completing and
  discarding workouts.
- **`seed_data/exercise_library.py`** holds the exercise library as data; `seed.py` syncs it.
- **`migrate.py`** is an additive, idempotent schema upgrader.
- **Frontend**: no generation logic anywhere. Pure, unit-tested modules: `validation.js` (set entry) and
  `ui/restTimer.js` (`RestTimer`, which uses an absolute end time so it stays correct when a phone sleeps).
  The router now supports `/workout/plan/:id` style routes and per-screen cleanup. `loadInto` ignores stale
  results so fast tab switching can't show the wrong tab.
- The API error format is unchanged, but validation messages are now plain language ("Must be 0 or more." instead
  of "Input should be greater than or equal to 0").

## 2. Files

**Added (backend):** `app/engine/{__init__,types,equipment_filter,prescription,split_generator,exercise_selector,substitution,workout_generator}.py`,
`app/migrate.py`, `app/schemas/plan.py`, `app/seed_data/{__init__,exercise_library}.py`,
`app/services/{engine_adapter,plan_service,workout_session_service}.py`,
`tests/test_{library,equipment_filtering,generation,substitution,custom_workouts,sessions,workout_security,migration}.py`.

**Added (frontend):** `js/validation.js`, `js/ui/{restTimer,planModals}.js`,
`js/views/{generator,plan,session,sessionDetail,startWorkout}.js`, `tests/{validation,restTimer}.test.mjs`.

**Modified (backend):** `app/errors.py`, `main.py`, `models/{__init__,enums,exercise,workout}.py`, `routers/{exercises,workouts,workout_sessions}.py`,
`schemas/{exercise,workout}.py`, `seed.py`, `services/{exercise_service,workout_service}.py`, `tests/{conftest,test_isolation}.py`.

**Modified (frontend):** `css/components.css`, `js/{api,main,router,units}.js`, `js/ui/components.js`, `js/views/{home,workout}.js`.

**Docs:** `README.md`, `API.md`, `DATABASE.md`, `ARCHITECTURE.md`, this file.

## 3. Database changes

New tables: `plan_days`, `plan_exercises`. New columns (all added automatically to existing databases):

| Table | Columns |
| --- | --- |
| `exercises` | `min_experience_level`, `is_compound`, `is_timed`, `rep_min`, `rep_max`, `recommended_sets` (+ CHECK constraints on new databases) |
| `workout_plans` | `kind`, `split_type`, `training_location`, `notes` |
| `workout_sessions` | `plan_day_id`, `name`, `ended_at`; partial unique index `uq_one_active_session` (one in-progress workout per user) |
| `workout_exercises` | `rest_seconds` |
| `workout_sets` | `target_reps_min`, `target_reps_max`, `notes` |

## 4. New APIs

Full detail in [API.md](API.md).

- `POST /workouts/generate`, `POST /workouts/custom`, `PATCH|DELETE /workouts/{id}`, `GET /workouts?kind=`
- Day and exercise editing under `/workouts/{id}/days/{day_id}/...`: rename, add, edit sets/reps/rest, remove,
  reorder (`PUT .../order`), list substitutes, replace
- `GET /exercises?available_only=true`, `GET /exercises/{id}/substitutes`
- `POST /workout-sessions/start`, `GET /workout-sessions/active`, `PATCH .../sets/{id}`, add/delete set,
  `POST .../complete`, `DELETE /workout-sessions/{id}` (discard), `GET /workout-sessions?status=`

## 5. Workout-generation rules

**Inputs:** goal, experience, days per week (1-7), session minutes (10-240), equipment, location, split preference.
Anything omitted comes from the profile.

**Equipment (never relaxed).** An exercise is allowed only if *every* item it needs is available (Barbell back
squat needs barbell *and* squat rack). Bodyweight is always available. Location `home_bodyweight` limits gear to
bodyweight, resistance bands and a pull-up bar, and the plan says which ticked items were ignored. Experience
limits are also never relaxed: an exercise above the user's level is never prescribed. If a muscle can't be trained
with the available gear, the plan carries a warning rather than an invalid exercise.

**Split (auto):** 1-2 days full body; 3 days full body, or push/pull/legs for intermediate+ muscle gain or
recomposition; 4 days upper/lower; 5 days push/pull/legs for intermediate+ muscle builders, otherwise upper/lower;
6 days push/pull/legs (upper/lower for beginners); 7 days push/pull/legs with a recovery warning. A preference is
honoured when it fits the number of days (full body 1-4, upper/lower 2-6, push/pull/legs 3-7, push/pull 2-6,
body-part 4-6); otherwise the engine falls back with a warning.

**Week layout:** 2 days = Day 1, 4; 3 = 1, 3, 5; 4 = 1, 2, 4, 5; 5 = 1, 2, 3, 5, 6; 6 = Days 1-6; the rest are rest
days. Repeated day types rotate A/B variants (Upper A / Upper B) that use different exercises.

**Exercise choice per slot:** same muscle, role (compound or isolation) and preferred movement pattern first, then
relaxed in steps. Score = experience fit + goal-based equipment style bonus (strength favours barbell, fat loss
favours dumbbells and bodyweight, etc.) minus a penalty for exercises already used in the plan (smaller for
strength, which deliberately repeats main lifts). No exercise appears twice in a day. Thin days are topped up from
the muscles that day already trains.

**Prescription**

| Goal | Compound reps / rest | Isolation reps / rest | Notes |
| --- | --- | --- | --- |
| Strength | 3-6 / 3 min (+30s if heavy) | 8-12 / 90s | Max 2 isolation exercises a day; lead lift +1 set |
| Muscle gain | 6-10 / 2 min | 10-15 / 75s | |
| Recomposition | 6-12 / 90s | 10-15 / 60s | |
| Fat loss | 8-12 / 60s | 12-20 / 45s | Adds a conditioning slot each day |
| General fitness | 8-12 / 75s | 12-15 / 60s | Adds a conditioning slot |

Rep ranges are always kept inside each exercise's own range (timed exercises use seconds). Sets start from the
exercise's recommended sets: beginner -1, advanced compound +1, clamped to 2-5.

**Session length:** budget = minutes - 5 (warm-up). If the day is too long, least important exercises are dropped
first (never below 3), then sets are trimmed to 2, then rests are shortened by 25%. Order is big lifts, accessories,
core, conditioning.

**Substitution:** must be a different active exercise with the same primary muscle and compound/isolation
classification, available equipment, and allowed experience. Major lifts keep their movement pattern whenever any
alternative exists. Ranked by pattern, shared secondary muscles, difficulty closeness and equipment style. Replacing
keeps position, sets, rep range, rest and notes (switching between reps and seconds takes the new exercise's defaults).

## 6. Tests

**234 backend tests pass** (36 from Phase 0, 198 new) plus **18 frontend tests**, and a headless-browser run of the
complete user journey (onboarding to history) was used to verify the UI end to end.

| Area | File | Covers |
| --- | --- | --- |
| Equipment | `test_equipment_filtering.py` | All-gear-required rule, spec example (dumbbells + bench + bands), a sweep of 7 gear sets x 6 splits x goals x levels x frequencies, experience limits, bodyweight location, warnings |
| Generation | `test_generation.py` | Goal structures, 1-7 day frequencies, spec 4-day layout, auto split table, registering new/custom splits, fitting session length, determinism, API defaults/overrides/validation |
| Substitution | `test_substitution.py` | Bench press alternatives, muscle/pattern/classification preserved for the whole library, equipment and experience respected, replace keeps the prescription, invalid replacements rejected |
| Logging | `test_sessions.py` | Start, log weight/reps/RPE/RIR/notes, validation (negative, out of range, impossible duration), completion rules, history, prefill, one active workout |
| Custom workouts | `test_custom_workouts.py` | Create, add, remove, reorder, edit sets/reps/rest, rename, delete keeps history, limits |
| Security | `test_workout_security.py`, `test_isolation.py` | Other users can't read, edit, start, log, complete or discard anything; ids can't be mixed across users; endpoints require login |
| Library | `test_library.py` | Every exercise has valid metadata; seed is idempotent and syncs |
| Migration | `test_migration.py` | Phase 0 databases upgrade without data loss |
| Frontend | `frontend/tests/*.test.mjs` | Set validation messages, unit conversion, every rest-timer operation with a fake clock |

Run: `cd backend && python -m pytest` and `cd frontend && node --test tests/*.test.mjs`.

## 7. Known limitations

- **Plan progression:** a generated plan is a single weekly template. There is no week-to-week progression,
  deloads, or auto-regulation. Weight suggestions are only "what you did last time".
- **Substitution inside a running workout** is not available; swap exercises in the plan before starting. Exercises
  can't be added to a workout in progress.
- **Finished workouts are read-only** and can't be deleted or edited (only in-progress ones can be discarded).
- **Custom user exercises** can be added to workouts and used as substitutes, but the generator only uses built-in
  exercises, because their metadata is user-chosen.
- **Muscle coverage is limited by the library.** Without equipment, some muscles (e.g. biceps) have no exercise, and
  the plan says so. Body-part splits on no equipment give very short chest or arm days.
- **No warm-up sets, supersets, drop sets or unilateral (per-side) logging.** Time estimates use fixed assumptions.
- **Reordering uses up/down buttons**, not drag and drop.
- **Rest timer** only runs while the workout screen is open and gives no sound; it vibrates on supported phones.
- **Rest timer / UI** was verified in headless Chromium, not on real devices or screen readers (ARIA labels and live
  regions are in place).
- **Migrations** are additive only; adopt Alembic before any rename or destructive change. One active workout per
  user is enforced by a database index, so a crashed tab leaves a workout "in progress" until resumed or discarded.
- Weights are stored in kg; pound entries are converted and may display with rounding (135 lb is stored as 61.23 kg).
- Time zones: workout dates use the browser's local date, validated within one day of the server's UTC date.
