# Phase 2: Progressive overload engine

Liv now looks at what you actually lifted and tells you what to do next time. Every suggestion comes from your
stored workout data. When there is no history, Liv says so and invents no numbers.

> Recommended today: **82.5 kg · 8–10 reps · 3 sets**
> Last session: 80 kg × 10 / 10 / 10
> *You reached the top of your target range (10 reps) on all 3 sets last session, so add weight and work back up from 8.*

Phase 0 and 1 are untouched: workout generation, custom workouts, sessions and history behave as before, and the
workout screen still pre-fills each set from your last session. The suggestion sits on top, and you choose whether to
use it.

## Upgrading from Phase 1

Nothing to migrate by hand. Phase 2 only **adds** tables, so the existing startup (`create_all`) creates them. On
first start, personal records are built from workouts you already logged. Workouts started before the upgrade simply
have no suggestion (`recommendation: null`).

```bash
cd backend && pip install -r requirements-dev.txt && python -m uvicorn app.main:app --reload
```

---

## 1. Progression rules

The engine (`engine/progression.py`) judges the **most recent session**, using its **working sets**: the sets at the
heaviest weight used. Lighter warm-up and back-off sets are ignored.

A session is classified against the target range (e.g. 8–10) and the prescribed number of sets:

| Status | Meaning |
| --- | --- |
| **top** | Every prescribed set done, every working set at the top of the range or above |
| **in range** | Every prescribed set done, all at or above the bottom of the range, not all at the top |
| **short** | Reps were fine but fewer sets than prescribed were logged |
| **mixed** | Some sets (fewer than half) fell below the bottom of the range |
| **failed** | Half or more of the sets fell below the bottom of the range |

### Double progression (default for weighted exercises with a rep range)

| Last session | Recommendation |
| --- | --- |
| **top** | **Increase weight** by one step; reps return to the bottom of the range |
| **in range** | **Increase reps**: same weight, aim for (lowest set + 1) on every set, capped at the top of the range |
| **short** | **Maintain**: finish all prescribed sets before progressing |
| **mixed** | **Maintain**: aim for the bottom of the range on every set |
| **failed**, first time | **Maintain**: the weight is *not* increased |
| **failed**, 2 sessions in a row at the same weight | **Reduce weight** by about 5%, snapped to the step grid, at least one step |
| **failed**, 3+ in a row at the same weight | **Deload**: about 10% lighter and one fewer set (if 3 or more) |

### Weight progression (fixed reps, e.g. 5 × 5)

Used automatically when `rep_min == rep_max`, or chosen per exercise. If every prescribed set reaches the target reps,
add one step. Otherwise the same miss / reduce / deload ladder applies.

### Rep progression (bodyweight, resistance bands, timed holds)

No weight is recommended. Aim for (lowest set + 1) reps on every set, or +5 seconds for timed exercises. Past the top
of the range the target keeps rising and Liv suggests a harder variation or adding load. Two misses in a row hint at an
easier variation; three deload by one set. If you log added weight on a bodyweight exercise (weighted pull-ups), it is
progressed by weight instead.

### Hold

Chosen per exercise to switch progression off: the target stays as it was.

### RIR / RPE

- If RIR is missing, nothing changes. RPE is used as `10 − RPE` only when RIR was not logged for that set.
- RIR is used only when **at least 2 sets** have it, so a single optimistic entry cannot move the plan.
- "Very easy" means average RIR ≥ 4 and no set below 3.
  - **Top of range + very easy:** a bigger jump (two steps), capped at 10% of the weight (one step is always allowed).
  - **In range + very easy:** a one-step weight increase, worded as a suggestion because RIR is self-reported.
  - **Failed/mixed sessions:** RIR never rescues a miss.
- RIR 0 on every set at the top of the range still progresses, with a note that the next session will feel hard.
- A decision that leans on RIR lowers the confidence label by one level.

### Time away

| Days since last session | Behaviour |
| --- | --- |
| 14–27 | No increase: repeat the same target once (**hold**) |
| 28+ | About 10% lighter and build back up (**reduce weight**) |

### Decline detection (gentle, rule-based)

The last two sessions are each ≥ 5% below the median of the four before (≥ 10% is "marked"). The per-session score is the
best estimated 1RM of the working sets (reps above 12 are counted as 12), or average reps for bodyweight work. At least
4 sessions are needed. Language is always: *"Your recent performance is below your normal trend."* with a note that
lowering the weight on purpose explains it. Nothing is diagnosed. A decline **holds** the target instead of pushing, but a
clean top-of-range session is never blocked by an earlier dip.

An overall notice appears only when several exercises dip together.

### Confidence

`low` with one session, `medium` with two, `high` with three or more (one level lower when RIR drove the decision).

### Increments (configurable, never one number)

Resolution order: **per-exercise step → per-equipment step → default**.

| Equipment | Metric default | Imperial default |
| --- | --- | --- |
| Barbell | 2.5 kg | 5 lb |
| Dumbbells | 1 kg | 5 lb |
| Kettlebell | 2 kg | 4 lb |
| Machines | 2.5 kg (configurable) | 5 lb |
| Cable machine | 2.5 kg | 5 lb |
| Weighted bodyweight | 1 kg | 2.5 lb |
| Bodyweight / bands / timed | rep progression | rep progression |

Reasons never contain a weight unit, so they read correctly for kg and lb users.

### User control

Each suggestion can be **Used**, **Edited** or **Ignored**. Using or editing fills in the sets you have not completed
yet (and, for a deload, drops the extra unfinished set). Completed sets are never overwritten. The choice, the numbers
chosen, and later what you actually lifted (`performed_weight_kg`, `followed`) are stored. The next suggestion is based
on what you actually lifted, with a short note if it differed from the suggestion.

### Records

Computed by replaying history in date order (`engine/records.py`). The first session of an exercise is a baseline and
produces no records.

| Record | Rule |
| --- | --- |
| **Weight PR** | Heavier than any earlier set |
| **Rep PR** | More reps than any earlier set at the same or a heavier weight, on a working set. A new heaviest weight is a weight PR, not also a rep PR. Warm-ups never count |
| **Volume PR** | Higher weight × reps for the exercise in one workout than any earlier workout (weighted work only) |

### Volume and estimates

- Volume = weight × reps, aggregated by exercise, primary muscle group, workout and week (Monday start). Bodyweight sets
  count as sets and reps but add no volume. The UI and API both say volume is a rough measure, not a measure of results.
- Estimated 1RM uses Epley, `weight × (1 + reps/30)`, only for sets of 1–12 reps, and is always labelled an estimate.

---

## 2. Architecture

```
engine/metrics.py       1RM, volume, working sets, score, trend, decline     (pure)
engine/progression.py   ProgressionEngine, config, increments                (pure)
engine/records.py       PR detection                                           (pure)
services/performance_data.py   stored workouts  ->  engine objects           (only DB/engine bridge)
services/progression_service.py   settings, increments, recommend, respond, finalize
services/history_service.py       history, volume, flags, PR rebuild/backfill
routers/progress.py + exercises.py + workout_sessions.py   thin HTTP layer
frontend: progression.js (pure formatting), ui/recommendation.js, ui/charts.js,
          views/exerciseHistory.js, views/progress.js (tabs), views/session.js, views/sessionDetail.js
```

The engine takes `ProgressionInput(sessions, rep_min, rep_max, sets, strategy, increment_kg, category, is_timed,
is_bodyweight, today, previous)` and returns `Recommendation(action, strategy, weight_kg, rep_min, rep_max, reps_goal,
sets, reason, confidence, flags, basis)`. It is deterministic, takes the date as input, and has no UI, database or HTTP
dependency.

Progression is non-critical: if building suggestions or records fails, the error is logged and the workout still
starts or finishes.

## 3. Database changes (new tables only)

| Table | Purpose |
| --- | --- |
| `progression_recommendations` | The suggestion frozen at workout start, the user's response (`pending/accepted/edited/ignored`, chosen weight and reps) and the outcome (`performed_weight_kg`, `followed`). One per workout exercise, cascade-deleted with it |
| `personal_records` | PR events (`weight/reps/volume`, `value`, `weight_kg`, `reps`, `previous_value`, `achieved_on`). Unique per session, exercise and type. Rebuilt from sets |
| `exercise_progression_settings` | Per user and exercise: optional strategy and weight step |
| `user_increment_preferences` | Per user and equipment category: weight step |

No existing table or column changed. Details in [DATABASE.md](DATABASE.md).

## 4. API changes

New: `GET /exercises/{id}/recommendation`, `/history`, `GET|PUT /exercises/{id}/progression-settings`,
`POST /workout-sessions/{id}/exercises/{we_id}/recommendation`, `GET /progress/exercises`, `/records`, `/volume`,
`/flags`, `/increments`, `PUT /progress/increments/{category}`.

Extended (backwards compatible): session responses gain `exercises[].recommendation` and `records`. Full reference in
[API.md](API.md).

## 5. Tests

| Suite | What it covers |
| --- | --- |
| `test_progression_engine.py` (65) | Successful and failed progression, double / weight / rep / hold strategies, bodyweight and timed, missing and present RIR/RPE, no history, failure streaks, increments per equipment, time away, decline, overrides, confidence, warm-up handling, 400-case randomized sanity check |
| `test_progress_metrics.py` (29) | Epley, volume, week boundaries, trend, decline thresholds, PR rules (weight, reps, volume, baseline, warm-ups, bodyweight, chronological replay) |
| `test_progression_api.py` (49) | The completion criteria end to end (finish a workout, next start shows the suggestion built from stored data), frozen suggestions, accept / edit / ignore, invalid responses, finished and foreign workouts, overrides, settings and increments, history, records and backfill, volume, flags, authentication and isolation |
| `frontend/tests/progression.test.mjs` | Formatting, edit validation and chart geometry |

Backend: 377 tests (234 from earlier phases, 143 new). Frontend: 31 tests.

## 6. Example scenarios

All values are produced by the engine (range 8–10, 3 sets).

| History (newest first) | Result |
| --- | --- |
| 80 kg × 10/10/10 | **Increase weight** → 82.5 kg, 8–10, aim for 8 |
| 80 kg × 9/8/8 | **Increase reps** → 80 kg, aim for 9 on every set |
| 80 kg × 8/7/6 | **Maintain** → 80 kg, aim for 8 on every set |
| 80 kg × 8/7/6, twice | **Reduce weight** → 75 kg |
| 80 kg × 8/7/6, three times | **Deload** → 72.5 kg, 2 sets |
| 80 kg × 10/10/10 at RIR 4 | **Increase weight** → 85 kg (bigger jump, medium-to-low confidence) |
| 100 kg × 5/5/5, range 5–5 | **Increase weight** → 102.5 kg (weight progression) |
| Dumbbell press 80 kg × 10/10/10 | **Increase weight** → 81 kg (1 kg dumbbell step) |
| Push-up 10/10/10, range 8–20 | **Increase reps** → no weight, aim for 11 |
| Plank 30/30/30 sec | **Increase reps** → aim for 35 seconds |
| 80 kg × 10/10/10, 15 days ago | **Hold** → 80 kg, repeat once |
| 80 kg × 10/10/10, 30 days ago | **Reduce weight** → 72.5 kg |
| Six sessions, last two clearly lower | Flag "below your normal trend", **hold** |
| No history | **Start**: no weight shown, "choose a weight you can lift for 8–10 reps with about 2 reps left" |

## 7. Known limitations

- **Judged on the last session**, with only a break rule and a decline rule looking further back. A lone bad day after
  a great streak produces a conservative suggestion rather than an average of several sessions.
- **Working sets = the heaviest weight used.** A top set followed by back-off sets is judged on the top set alone, and a
  last set dropped to a lighter weight counts as a missed set at the heavier weight. There is no warm-up marker yet.
- **Prescribed sets come from the plan**, which is edited separately. If you add an extra set during a workout, the
  engine treats the extra as bonus work.
- **Thresholds are fixed rules**, not learned per user. They live in `ProgressionConfig` and are unit-tested, but not
  personalised.
- **RIR/RPE is self-reported** and treated as a soft signal, which means it can make a suggestion more or less
  ambitious but never overrides missed reps.
- **Estimated 1RM** is an Epley estimate from sets of 1–12 reps and gets less reliable above about 8.
- **Records are per exercise.** Swapping to a substitute exercise starts a new history, and no records carry over.
- **Volume credits the primary muscle only**, and bodyweight sets add no volume.
- **Decline flags are sensitive to deliberate deloads.** The message says so, but a planned lighter week still shows
  as "below trend".
- **Imperial steps** are stored in kilograms (5 lb = 2.27 kg), so after many increases a weight can read a fraction of a
  pound off a round number (for example 139.99 lb shown as 140).
- **Workouts started before the upgrade** have no stored suggestion. The preview endpoint and exercise page still work.
- No automatic periodisation (mesocycles, planned deload weeks), no per-set rest or tempo analysis, and no
  cross-exercise fatigue modelling.
