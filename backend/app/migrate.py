"""Tiny additive schema upgrader for existing SQLite databases.

`Base.metadata.create_all` creates missing *tables* but never adds columns to tables that already exist.
Phase 1 added columns to Phase 0 tables, so this adds any that are missing. It is idempotent and only
ever adds nullable/defaulted columns. Adopt Alembic before any destructive change.
"""
import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

log = logging.getLogger("liv.migrate")

# table -> [(column, column DDL)]
ADDED_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "exercises": [
        ("min_experience_level", "VARCHAR(32) NOT NULL DEFAULT 'beginner'"),
        ("is_compound", "BOOLEAN NOT NULL DEFAULT 0"),
        ("is_timed", "BOOLEAN NOT NULL DEFAULT 0"),
        ("rep_min", "SMALLINT NOT NULL DEFAULT 8"),
        ("rep_max", "SMALLINT NOT NULL DEFAULT 12"),
        ("recommended_sets", "SMALLINT NOT NULL DEFAULT 3"),
    ],
    "workout_plans": [
        ("kind", "VARCHAR(32) NOT NULL DEFAULT 'custom'"),
        ("split_type", "VARCHAR(32)"),
        ("training_location", "VARCHAR(32)"),
        ("notes", "TEXT"),
    ],
    "workout_sessions": [
        ("plan_day_id", "INTEGER REFERENCES plan_days(id) ON DELETE SET NULL"),
        ("name", "VARCHAR(120)"),
        ("ended_at", "DATETIME"),
    ],
    "workout_exercises": [("rest_seconds", "INTEGER")],
    "workout_sets": [
        ("target_reps_min", "SMALLINT"),
        ("target_reps_max", "SMALLINT"),
        ("notes", "VARCHAR(500)"),
    ],
}


def upgrade_schema(engine: Engine) -> list[str]:
    """Adds missing columns. Returns the list of "table.column" that were added."""
    added: list[str] = []
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in ADDED_COLUMNS.items():
            if not inspector.has_table(table):
                continue  # create_all will build it with every column
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                    added.append(f"{table}.{name}")
        if inspector.has_table("workout_sessions"):
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_one_active_session ON workout_sessions (user_id) "
                "WHERE status = 'in_progress'"))
        if "exercises.is_compound" in added:
            # Custom exercises from Phase 0: derive the flag from their type. Built-ins are re-seeded.
            conn.execute(text("UPDATE exercises SET is_compound = 1 WHERE exercise_type = 'compound'"))
    if added:
        log.info("Schema upgraded: added %s", ", ".join(added))
    return added
