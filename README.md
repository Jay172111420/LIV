# Liv

> **Your health, quantified.**

Liv is an all-in-one **fitness and nutrition tracking platform** designed to help you understand and improve your health.

### Planned Features

- 🥗 Nutrition & calorie tracking
- 💪 Workout tracking
- 📊 Health & fitness analytics
- ⚖️ Body composition tracking
- 🧬 Macro & micronutrient tracking
- 🎯 Personalized goals
- 📈 Progress tracking

### Tech Stack

**Backend:** Python, FastAPI, SQLAlchemy 2  
**Frontend:** HTML, CSS, JavaScript (ES modules, no build step)  
**Database:** SQLite  
**Analytics:** Plotly (planned, not used yet)

---

🚧 **Liv is currently under development.** Phase 0 (foundation) is complete.

## What works today

Registration and login, a three-step onboarding flow, a persisted profile with equipment selection,
body-weight and measurement logging, and the five-section app (Home, Workout, Nutrition, Progress, Profile).

**Phase 1 adds the first complete fitness feature:**

- A deterministic **workout-plan generator** (goal, experience, days, session length, location, equipment, split).
- A **104-exercise library** with full metadata, and strict **equipment filtering**.
- **Substitutions** that keep the target muscle and movement pattern.
- A **custom workout creator** (add, remove, reorder, change sets/reps/rest, rename, save, reuse).
- A fast **workout screen** that logs weight, reps, RPE, RIR and notes, with a **rest timer**.
- **Workout history**.

See [PHASE1.md](PHASE1.md) for architecture, rules, APIs and known limitations.

## Install

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r backend/requirements-dev.txt
cp backend/.env.example backend/.env   # optional, defaults work locally
```

## Run locally

```bash
cd backend
python -m uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>. The API serves the frontend, so there is only one process to run.
Interactive API docs: <http://127.0.0.1:8000/api/docs>.

The SQLite file (`backend/liv.db`) and all reference data (goals, equipment, muscle groups and a starter
exercise library) are created automatically on first start.

## Run the tests

```bash
cd backend
python -m pytest          # backend: API, engine, security, migration

cd ../frontend
node --test tests/*.test.mjs   # set validation and rest-timer logic (Node 20+, no install needed)
```

## Environment variables

All optional. Set them in `backend/.env` or the environment, prefixed with `LIV_`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `LIV_DATABASE_URL` | `sqlite:///./liv.db` | SQLAlchemy database URL |
| `LIV_COOKIE_SECURE` | `false` | Set to `true` when serving over HTTPS |
| `LIV_SESSION_TTL_HOURS` | `336` | How long a login lasts (14 days) |
| `LIV_ALLOWED_ORIGINS` | empty | Extra origins allowed to send state-changing requests |
| `LIV_SEED_ON_STARTUP` | `true` | Create/refresh reference data at startup |
| `LIV_SESSION_COOKIE_NAME` | `liv_session` | Name of the session cookie |

Liv has no API keys or signing secrets yet. Sessions are random server-side tokens, so nothing secret
needs to be configured. Never commit `.env`.

## Project structure

```
backend/
  app/
    main.py          app factory, security headers, static hosting
    config.py        settings from environment
    database.py      engine and session
    security.py      password hashing, session tokens
    errors.py        one error format for the whole API
    deps.py          current-user and DB dependencies
    models/          SQLAlchemy tables
    schemas/         request/response validation (Pydantic)
    engine/          workout engine: pure Python, no database or HTTP (generator, splits, selector, ...)
    services/        business logic and database access, no HTTP code
    routers/         thin HTTP layer
    seed.py          reference data; syncs the exercise library on startup
    seed_data/       the built-in exercise library
    migrate.py       adds new columns to an existing Phase 0 database
  tests/             pytest suite
frontend/
  index.html
  css/               tokens, base, components, layout
  js/
    main.js          boot, route guards, navigation shell
    api.js           the only place that calls the network
    views/           one file per screen
    ui/              reusable components (rest timer, modals)
    validation.js    set-entry validation (pure, unit tested)
  tests/             Node unit tests
ARCHITECTURE.md  DATABASE.md  API.md
```

See [PHASE1.md](PHASE1.md), [ARCHITECTURE.md](ARCHITECTURE.md), [DATABASE.md](DATABASE.md) and [API.md](API.md) for details.
