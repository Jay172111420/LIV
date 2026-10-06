# Architecture

## Overview

One FastAPI process serves both the JSON API (under `/api`) and the static frontend (everything else).
Same origin means no CORS configuration and cookies that work without special handling.

```
Browser (ES modules)  --fetch /api/*-->  routers  ->  services  ->  SQLAlchemy models  ->  SQLite
        ^                                  |            |
        +------ static files (/)           schemas      business rules, ownership checks
```

## Workout engine (Phase 1)

```
routers -> services/plan_service ----> services/engine_adapter ----> engine/  (pure Python)
        -> services/workout_session_service                           WorkoutGenerator
                                                                      SplitGenerator   ExerciseSelector
                                                                      EquipmentFilter  ExerciseSubstitutionService
```

`app/engine` imports nothing from SQLAlchemy, FastAPI or the UI. It works on plain `ExerciseInfo` objects, so
it is deterministic and testable without a database. `engine_adapter` is the single bridge from database rows to
engine objects. The frontend never contains generation logic: it sends inputs to `/workouts/generate` and renders
the result.

## Decisions

**Kept the planned stack.** FastAPI, SQLite and vanilla HTML/CSS/JS were already chosen in the README, so
nothing was replaced. SQLAlchemy 2 was added as the ORM. Plotly is reserved for the analytics phase.

**Layering.** Routers parse HTTP and call one service function. Services hold all rules (ownership,
validation that needs the database, defaults). Pydantic schemas validate input at the edge. Models know
only about storage. This keeps rules testable without HTTP and swappable later.

**Sessions, not JWTs.** Login creates a random token stored server-side (as a SHA-256 hash) and sent as an
`HttpOnly`, `SameSite=Lax` cookie. Logout and expiry truly invalidate it, and JavaScript can never read it.
Passwords use Argon2id.

**Data isolation.** Every query for user-owned data filters by the authenticated user's id inside the service
layer. Another user's record returns `404`, not `403`, so existence isn't revealed. Custom exercises are
private to their owner; built-in exercises have no owner and are visible to everyone.

**One error shape.** Every failure is `{"error": {"code", "message", "details"}}`. The frontend turns it into a
readable message, and network failures get their own message. Unexpected errors are logged server-side and
return a generic message with no internals.

**Metric storage.** Weight, height and measurements are stored in kg and cm. The user's unit preference only
changes display and input. This avoids mixed-unit data and rounding drift.

**Frontend without a build step.** Native ES modules, a small `h()` DOM helper that only ever creates text
nodes (so user text can't become markup), and a hash router. Route guards in `main.js` enforce login and
finished onboarding. The server is the real authority, since every API call re-checks the session.

**Design system.** Colours, type, spacing and radii are CSS custom properties in `tokens.css`. Components
(buttons, fields, chips, tabs, modal, states) live in `components.css` and `ui/components.js`.

## Security summary

| Concern | Approach |
| --- | --- |
| Passwords | Argon2id, 10 character minimum, dummy hash on unknown email to even out timing |
| Sessions | Random 256-bit token, stored hashed, HttpOnly + SameSite=Lax (+ Secure via env), server-side expiry |
| CSRF | SameSite cookies plus rejection of state-changing requests with a foreign `Origin` |
| XSS | No `innerHTML` in the frontend, strict CSP (`script-src 'self'`) |
| SQL injection | SQLAlchemy parameterised queries only; `LIKE` wildcards in search are escaped |
| Authorization | Ownership filter on every user-scoped query; tested with two real users |
| Validation | Pydantic on every request body; unknown fields rejected; numeric ranges enforced |
| Headers | CSP, `X-Frame-Options: DENY`, `nosniff`, `no-store` on API responses |

## Extending

- New split: build `DayTemplate`s and call `SplitGenerator.register(SplitSpec(...))`. No generator changes.
- New exercise: add an entry to `seed_data/exercise_library.py` (a test checks every entry's metadata).
- New goal prescription: add a row to `GOAL_RULES` in `engine/prescription.py` and `STYLE_BONUS` in `engine/exercise_selector.py`.
- New goal, equipment item or muscle group: add a row to `seed.py` lists (or insert in the DB). No code change.
- New body metric type: add to `BodyMetricType` and `VALUE_RANGES`.
- New feature area: add `models/x.py`, `schemas/x.py`, `services/x_service.py`, `routers/x.py`, register the
  router in `main.py`, then a view in `frontend/js/views/`.
