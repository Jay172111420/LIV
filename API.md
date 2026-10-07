# API

Base path `/api`. JSON in, JSON out. Interactive docs at `/api/docs` while the server runs.
Everything except `register`, `login`, `logout` and `health` requires the session cookie set at login.

## Errors

```json
{ "error": { "code": "validation_error", "message": "Some of the information you entered isn't valid.",
             "details": [ { "field": "age", "message": "Input should be greater than or equal to 13" } ] } }
```

| Status | Meaning | Example codes |
| --- | --- | --- |
| 400 | Valid shape, invalid reference | `invalid_goal`, `invalid_equipment`, `invalid_exercise`, `duplicate_exercise` |
| 401 | Not logged in / bad credentials | `not_authenticated`, `invalid_credentials` |
| 403 | Cross-origin write blocked | `forbidden_origin` |
| 404 | Not found, or belongs to someone else | `not_found` |
| 409 | Conflict | `email_taken` |
| 422 | Validation failed | `validation_error` |
| 500 | Server or database problem | `internal_error`, `database_error` |

## Endpoints

### Auth
| Method | Path | Notes |
| --- | --- | --- |
| POST | `/auth/register` | `{email, password}` (10 to 128 chars). Creates the account, empty profile, sets cookie. 201 |
| POST | `/auth/login` | `{email, password}`. Sets cookie |
| POST | `/auth/logout` | Ends the session server-side. 204 |
| GET | `/auth/me` | Current user |

### Profile
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/profile` | Includes `goal`, `equipment`, `preferred_training_days`, `onboarding_complete` |
| PUT | `/profile` | Partial update: only sent fields change, `null` clears. `equipment_ids` and `preferred_training_days` replace the whole list |

### Reference data
| Method | Path |
| --- | --- |
| GET | `/goals` |
| GET | `/equipment` |
| GET | `/exercises/muscle-groups` |

### Exercises
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/exercises` | Query: `q`, `muscle_group_id`, `equipment_id`, `available_only` (only exercises doable with your equipment and location), `limit` (1-100), `offset`. Built-in plus your own |
| POST | `/exercises` | Creates a private custom exercise. Optional: `min_experience_level`, `is_compound`, `is_timed`, `rep_min`, `rep_max`, `recommended_sets`. 201 |
| GET | `/exercises/{id}` | |
| GET | `/exercises/{id}/substitutes` | Ranked replacements for your equipment, location and experience. Query: `limit` (1-20) |

### Workouts (plans and custom workouts)
A *plan* has *days*; a day has *plan exercises* (an exercise plus sets, rep range and rest). A custom workout is a
plan of `kind: "custom"` with exactly one day. All edit endpoints return the updated day.

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/workouts` | Query: `kind` (`generated` or `custom`). Summaries incl. `workout_count`, `exercise_count`, `start_day_id`, `warnings` |
| POST | `/workouts` | Phase 0: empty plan shell. 201 |
| POST | `/workouts/generate` | Builds and saves a plan. Every field optional and defaults to your profile: `goal_id`, `experience_level`, `days_per_week`, `duration_minutes`, `training_location`, `equipment_ids`, `split_preference` (`auto`, `full_body`, `upper_lower`, `push_pull_legs`, `push_pull`, `bro_split`), `name`. 400 `profile_incomplete` if something is missing. 201 |
| POST | `/workouts/custom` | `{name, exercises:[{exercise_id, sets?, rep_min?, rep_max?, rest_seconds?, notes?}]}`. Missing values come from the exercise's recommendations. 201 |
| GET | `/workouts/{id}` | Plan with `days[]` (7 for generated plans, rest days included) |
| PATCH | `/workouts/{id}` | `name`, `is_active`. Renaming a custom workout renames its day |
| DELETE | `/workouts/{id}` | 204. Logged sessions are kept |
| PATCH | `/workouts/{id}/days/{day_id}` | Rename a day |
| POST | `/workouts/{id}/days/{day_id}/exercises` | Add an exercise. 400 `duplicate_exercise_in_day`, `too_many_exercises` (max 20), `rest_day`. 201 |
| PATCH | `/workouts/{id}/days/{day_id}/exercises/{pe_id}` | `sets` (1-10), `rep_min`, `rep_max`, `rest_seconds` (0-600), `notes` |
| DELETE | `/workouts/{id}/days/{day_id}/exercises/{pe_id}` | Remove; positions are renumbered |
| PUT | `/workouts/{id}/days/{day_id}/order` | `{plan_exercise_ids: [...]}` must list every exercise exactly once |
| GET | `/workouts/{id}/days/{day_id}/exercises/{pe_id}/substitutes` | Valid replacements with `score` and `reasons` |
| POST | `/workouts/{id}/days/{day_id}/exercises/{pe_id}/replace` | `{exercise_id}`. Keeps position, sets, reps, rest, notes. 400 `invalid_substitute` |

### Workout sessions (doing and logging a workout)
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/workout-sessions` | Query: `status` (`in_progress`, `completed`, ...), `limit`, `offset`. Newest first (history) |
| POST | `/workout-sessions` | Phase 0 bulk create (nested `exercises[].sets[]`) |
| POST | `/workout-sessions/start` | `{plan_day_id, performed_on?}`. Copies the day into a live session, pre-filling weight/reps from last time. 409 `workout_in_progress` (with `details.session_id`) if one is already running. 201 |
| GET | `/workout-sessions/active` | The session in progress, or `null` |
| GET | `/workout-sessions/{id}` | |
| PATCH | `/workout-sessions/{id}/sets/{set_id}` | Partial update: `weight_kg` (0-1000), `reps` (0-1000), `rpe` (1-10, step 0.5), `rir` (0-10), `notes`, `is_completed`. Completing needs reps >= 1 (400 `set_incomplete`) |
| POST | `/workout-sessions/{id}/exercises/{we_id}/sets` | Add a set (copies the last one). Max 20. 201 |
| DELETE | `/workout-sessions/{id}/exercises/{we_id}/sets/{set_id}` | Remove a set (an exercise keeps at least one) |
| POST | `/workout-sessions/{id}/complete` | `{duration_minutes?, notes?}`. Needs one completed set (400 `no_completed_sets`). Skipped sets are dropped. Duration defaults to elapsed time; a typed duration longer than elapsed time is rejected (400 `invalid_duration`) |
| DELETE | `/workout-sessions/{id}` | Discard a workout in progress. 204. Finished workouts return 409 `workout_not_active` |

Finished workouts are read-only. All ids are scoped to the signed-in user; other users' ids return 404.

### Progression and history (Phase 2)
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/exercises/{id}/recommendation` | Preview of what to do next. Query: `sets`, `rep_min`, `rep_max` (default: how you last trained it). Reads stored data; saves nothing. 400 `invalid_rep_range` |
| GET | `/exercises/{id}/history` | Bests, estimated 1RM (labelled as an estimate), volume, recent sessions (`limit` 1-50), PRs, trend, flags |
| GET, PUT | `/exercises/{id}/progression-settings` | `{strategy?, increment_kg?}`. Strategy: `auto`, `double_progression`, `weight_progression`, `rep_progression`, `hold`. `null` resets to automatic / default |
| POST | `/workout-sessions/{id}/exercises/{we_id}/recommendation` | Accept, edit or ignore: `{choice: "accepted"}`, `{choice: "edited", weight_kg?, reps?}` (at least one), `{choice: "ignored"}`. Applies to sets not yet completed; the choice is stored. 409 `workout_not_active` after finishing, 400 `no_recommendation` |
| GET | `/progress/exercises` | Exercises with history, newest first; `flagged` marks a decline |
| GET | `/progress/records` | PR events, newest first. Query: `exercise_id`, `limit` (1-100) |
| GET | `/progress/volume` | `weeks` (1-52, default 8). Volume, sets and reps by week, muscle group, exercise and workout |
| GET | `/progress/flags` | Exercises whose recent performance is below trend, plus an `overall` notice when it is broad |
| GET | `/progress/increments` | Weight step per equipment type: default, custom and effective |
| PUT | `/progress/increments/{category}` | `{increment_kg}` or `null` to reset. Categories: `barbell`, `dumbbells`, `kettlebell`, `machines`, `cable_machine` |

Session responses now include `exercises[].recommendation` (frozen when the workout started; `null` for workouts
started before Phase 2) and `records` (PRs earned in that workout). A recommendation looks like:

```json
{"action": "increase_weight", "strategy": "double_progression", "weight_kg": 82.5, "rep_min": 8, "rep_max": 10,
 "reps_goal": 8, "sets": 3, "reason": "You reached the top of your target range (10 reps) on all 3 sets last session, so add weight and work back up from 8.",
 "confidence": "medium", "flags": [], "last_session": {"performed_on": "2026-10-06", "sets": [{"weight_kg": 80, "reps": 10}]},
 "user_choice": "pending"}
```
`action` is one of `start` (no history), `increase_weight`, `increase_reps`, `maintain`, `hold`, `reduce_weight`, `deload`.
`weight_kg` is `null` for bodyweight exercises and when there is no history. Weights are always kilograms.

### Body metrics
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/body-metrics` | Query: `metric_type`, `limit` (1-200), `offset`. Newest first |
| POST | `/body-metrics` | Values in kg / cm / %. `custom` needs `custom_label` and `unit` |
| DELETE | `/body-metrics/{id}` | 204 |

### Nutrition
| Method | Path | Notes |
| --- | --- | --- |
| GET, PUT | `/nutrition/profile` | Targets, `dietary_preference`, `allergies`, `restrictions`. Partial update like `/profile` |

### Meta
`GET /health` returns `{"status": "ok"}`.

## Not yet implemented

Deleting finished workouts, editing or deleting custom exercises, password change, account deletion.
