# Database

SQLite via SQLAlchemy 2. Tables are created at startup (`Base.metadata.create_all`). Foreign keys are enforced
(`PRAGMA foreign_keys=ON` on every connection). Closed vocabularies are VARCHAR columns with CHECK constraints.
Timestamps are stored as UTC and returned timezone-aware.

```mermaid
erDiagram
  users ||--o{ auth_sessions : has
  users ||--|| user_profiles : has
  users ||--|| nutrition_profiles : has
  users ||--o{ workout_plans : owns
  users ||--o{ workout_sessions : owns
  users ||--o{ body_metrics : owns
  users ||--o{ exercises : "owns custom"
  user_profiles }o--o{ equipment : "profile_equipment"
  user_profiles ||--o{ user_training_days : prefers
  user_profiles }o--o| fitness_goals : targets
  nutrition_profiles ||--o{ nutrition_restrictions : lists
  exercises }o--o{ equipment : "exercise_equipment"
  exercises }o--|| muscle_groups : primary
  exercises }o--o{ muscle_groups : "exercise_secondary_muscles"
  workout_plans }o--o{ equipment : "plan_equipment"
  workout_plans }o--o| fitness_goals : targets
  workout_sessions }o--o| workout_plans : "performed from"
  workout_sessions ||--o{ workout_exercises : contains
  workout_exercises }o--|| exercises : uses
  workout_exercises ||--o{ workout_sets : has
```

## Tables

| Table | Purpose / notable columns |
| --- | --- |
| `users` | `email` (unique), `password_hash`, `is_active`, timestamps |
| `auth_sessions` | `token_hash` (unique), `expires_at`. Deleted on logout/expiry or with the user |
| `user_profiles` | One per user. Every field optional: `age`, `height_cm`, `weight_kg`, `sex`, `experience_level`, `goal_id`, `activity_level`, `training_location`, `training_days_per_week`, `preferred_workout_minutes`, `unit_preference` |
| `user_training_days` | Preferred weekdays (0 = Monday), one row per day |
| `profile_equipment` | Which equipment a user has (many-to-many) |
| `fitness_goals` | Lookup: fat loss, muscle gain, recomposition, strength, general fitness. Add rows to add goals |
| `equipment` | Lookup: barbell, dumbbells, cable machine, bench, squat rack, pull-up bar, resistance bands, kettlebell, machines, bodyweight |
| `muscle_groups` | Lookup used for primary/secondary muscles |
| `exercises` | `owner_user_id` NULL = built-in, otherwise a private custom exercise. `movement_pattern`, `difficulty`, `exercise_type`, `instructions`, `is_active` |
| `exercise_equipment` | Equipment an exercise needs. **All** linked items are required; no rows = no equipment |
| `exercise_secondary_muscles` | Secondary muscles (many-to-many) |
| `workout_plans` | `name`, `goal_id`, `days_per_week`, `experience_level`, `duration_minutes`, `is_active`, created/updated |
| `plan_equipment` | Equipment a plan requires |
| `workout_sessions` | `performed_on`, `plan_id` (nullable), `duration_minutes`, `status` (planned, in_progress, completed, skipped), `notes` |
| `workout_exercises` | Exercise within a session, ordered by `position` (unique per session) |
| `workout_sets` | `set_number`, `weight_kg`, `reps`, `rpe`, `rir`, `rest_seconds`, `is_completed` |
| `body_metrics` | One row per measurement: `metric_type` (weight, body_fat, waist, chest, arm, thigh, hip, neck, custom), `custom_label`, `value`, `unit`, `recorded_at`. Indexed by user, type and time |
| `nutrition_profiles` | One per user: `calorie_target`, `protein_g`, `carbs_g`, `fat_g`, `dietary_preference` |
| `nutrition_restrictions` | Allergies and restrictions as rows (`kind`, `label`) |

## Design notes

- History is relational (sessions, exercises, sets, metrics are all rows), so later analytics can query it
  directly. No important data lives in JSON blobs.
- Deleting a user cascades to everything they own.
- Migrations: Phase 0 uses `create_all`, which creates missing tables but doesn't alter existing ones. Adopt
  Alembic before the first schema change after real data exists.

## Reset local data

Stop the server and delete `backend/liv.db`. It's recreated on next start.
