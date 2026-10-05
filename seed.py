"""Idempotent reference data: goals, equipment, muscle groups, and a starter exercise library."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Equipment, Exercise, FitnessGoal, MuscleGroup
from app.models.enums import ExerciseType as T
from app.models.enums import ExperienceLevel as L
from app.models.enums import MovementPattern as M

GOALS = [
    ("fat_loss", "Fat loss", "Lose body fat while keeping muscle."),
    ("muscle_gain", "Muscle gain", "Build muscle size."),
    ("recomposition", "Body recomposition", "Lose fat and build muscle at the same time."),
    ("strength", "Strength", "Lift heavier over time."),
    ("general_fitness", "General fitness", "Feel and move better overall."),
]

EQUIPMENT = [
    ("bodyweight", "Bodyweight", "none"),
    ("dumbbells", "Dumbbells", "free weights"),
    ("barbell", "Barbell", "free weights"),
    ("kettlebell", "Kettlebell", "free weights"),
    ("bench", "Bench", "furniture"),
    ("squat_rack", "Squat rack", "racks"),
    ("pull_up_bar", "Pull-up bar", "racks"),
    ("cable_machine", "Cable machine", "machines"),
    ("machines", "Machines", "machines"),
    ("resistance_bands", "Resistance bands", "accessories"),
]

MUSCLES = [
    ("chest", "Chest"), ("back", "Back"), ("shoulders", "Shoulders"), ("biceps", "Biceps"),
    ("triceps", "Triceps"), ("forearms", "Forearms"), ("quads", "Quads"),
    ("hamstrings", "Hamstrings"), ("glutes", "Glutes"), ("calves", "Calves"),
    ("core", "Core"), ("full_body", "Full body"),
]

# name, primary, secondary, pattern, type, difficulty, equipment (all required), instructions
EXERCISES = [
    ("Bodyweight squat", "quads", ["glutes"], M.squat, T.compound, L.beginner, [],
     "Stand shoulder-width apart, sit your hips back and down until your thighs are parallel, then stand up."),
    ("Goblet squat", "quads", ["glutes", "core"], M.squat, T.compound, L.beginner, ["dumbbells"],
     "Hold one dumbbell at your chest, squat between your hips keeping your chest tall, then stand."),
    ("Barbell back squat", "quads", ["glutes", "core", "hamstrings"], M.squat, T.compound, L.intermediate,
     ["barbell", "squat_rack"],
     "Set the bar on your upper back, brace, squat to parallel or below, and drive up through mid-foot."),
    ("Leg press", "quads", ["glutes", "hamstrings"], M.squat, T.compound, L.beginner, ["machines"],
     "Place feet shoulder-width on the platform, lower until knees reach about 90 degrees, then press."),
    ("Glute bridge", "glutes", ["hamstrings", "core"], M.hinge, T.compound, L.beginner, [],
     "Lie on your back with knees bent, push through your heels to lift your hips, squeeze, and lower."),
    ("Dumbbell Romanian deadlift", "hamstrings", ["glutes", "back"], M.hinge, T.compound, L.beginner,
     ["dumbbells"],
     "With soft knees, push your hips back and slide the dumbbells down your thighs, then stand tall."),
    ("Romanian deadlift", "hamstrings", ["glutes", "back"], M.hinge, T.compound, L.intermediate, ["barbell"],
     "Hold the bar at hip height, hinge back with a flat spine until hamstrings stretch, then stand."),
    ("Kettlebell swing", "glutes", ["hamstrings", "core", "back"], M.hinge, T.compound, L.intermediate,
     ["kettlebell"],
     "Hinge back, snap your hips forward to swing the kettlebell to chest height, and let it fall back."),
    ("Walking lunge", "quads", ["glutes", "hamstrings"], M.lunge, T.compound, L.beginner, [],
     "Step forward, lower your back knee toward the floor, then drive through the front foot into the next step."),
    ("Calf raise", "calves", [], M.other, T.isolation, L.beginner, [],
     "Stand on the balls of your feet, rise as high as you can, pause, and lower slowly."),
    ("Push-up", "chest", ["triceps", "shoulders", "core"], M.push, T.compound, L.beginner, [],
     "Hands under shoulders, body in a straight line, lower your chest to the floor and press back up."),
    ("Dumbbell bench press", "chest", ["triceps", "shoulders"], M.push, T.compound, L.beginner,
     ["dumbbells", "bench"],
     "Lie on the bench, lower the dumbbells to chest level with elbows about 45 degrees, then press up."),
    ("Barbell bench press", "chest", ["triceps", "shoulders"], M.push, T.compound, L.intermediate,
     ["barbell", "bench"],
     "Lower the bar to mid-chest under control with shoulder blades pinched back, then press it up."),
    ("Dumbbell shoulder press", "shoulders", ["triceps"], M.push, T.compound, L.beginner, ["dumbbells"],
     "Press the dumbbells from shoulder height to overhead without arching your lower back."),
    ("Overhead press", "shoulders", ["triceps", "core"], M.push, T.compound, L.intermediate, ["barbell"],
     "Brace, press the bar from your collarbone to overhead, and move your head through at the top."),
    ("Dumbbell lateral raise", "shoulders", [], M.other, T.isolation, L.beginner, ["dumbbells"],
     "With a slight elbow bend, raise the dumbbells out to shoulder height and lower slowly."),
    ("Pull-up", "back", ["biceps", "forearms"], M.pull, T.compound, L.intermediate, ["pull_up_bar"],
     "From a dead hang, pull your chest toward the bar, then lower with control."),
    ("Lat pulldown", "back", ["biceps"], M.pull, T.compound, L.beginner, ["cable_machine"],
     "Pull the bar to your upper chest by driving your elbows down, then return slowly."),
    ("Seated cable row", "back", ["biceps"], M.pull, T.compound, L.beginner, ["cable_machine"],
     "Sit tall, pull the handle to your waist by squeezing your shoulder blades, then extend."),
    ("One-arm dumbbell row", "back", ["biceps"], M.pull, T.compound, L.beginner, ["dumbbells"],
     "Support yourself with one hand, row the dumbbell to your hip, and lower it fully."),
    ("Barbell row", "back", ["biceps", "forearms"], M.pull, T.compound, L.intermediate, ["barbell"],
     "Hinge forward with a flat back and row the bar to your lower ribs."),
    ("Resistance band pull-apart", "shoulders", ["back"], M.pull, T.isolation, L.beginner,
     ["resistance_bands"],
     "Hold the band at chest height and pull it apart until your arms form a T, then return slowly."),
    ("Dumbbell biceps curl", "biceps", ["forearms"], M.other, T.isolation, L.beginner, ["dumbbells"],
     "Keep elbows at your sides, curl the dumbbells up, and lower them slowly."),
    ("Cable triceps pushdown", "triceps", [], M.other, T.isolation, L.beginner, ["cable_machine"],
     "Elbows pinned at your sides, press the handle down until your arms are straight, then return."),
    ("Plank", "core", ["shoulders"], M.core, T.isolation, L.beginner, [],
     "Forearms down, body in a straight line, brace your abs and hold."),
    ("Hanging knee raise", "core", ["forearms"], M.core, T.isolation, L.intermediate, ["pull_up_bar"],
     "Hang from the bar and lift your knees toward your chest without swinging."),
    ("Burpee", "full_body", [], M.other, T.plyometric, L.intermediate, [],
     "Drop to a push-up, jump your feet in, then jump up with arms overhead."),
]


def seed_reference_data(db: Session) -> None:
    existing = {g.slug for g in db.scalars(select(FitnessGoal))}
    for i, (slug, name, desc) in enumerate(GOALS):
        if slug not in existing:
            db.add(FitnessGoal(slug=slug, name=name, description=desc, sort_order=i))

    existing = {e.slug for e in db.scalars(select(Equipment))}
    for slug, name, category in EQUIPMENT:
        if slug not in existing:
            db.add(Equipment(slug=slug, name=name, category=category))

    existing = {m.slug for m in db.scalars(select(MuscleGroup))}
    for slug, name in MUSCLES:
        if slug not in existing:
            db.add(MuscleGroup(slug=slug, name=name))
    db.flush()

    equipment = {e.slug: e for e in db.scalars(select(Equipment))}
    muscles = {m.slug: m for m in db.scalars(select(MuscleGroup))}
    have = set(db.scalars(select(Exercise.name).where(Exercise.owner_user_id.is_(None))))
    for name, primary, secondary, pattern, etype, level, gear, instructions in EXERCISES:
        if name in have:
            continue
        db.add(
            Exercise(
                name=name,
                primary_muscle_group=muscles[primary],
                secondary_muscle_groups=[muscles[s] for s in secondary],
                movement_pattern=pattern,
                exercise_type=etype,
                difficulty=level,
                equipment=[equipment[g] for g in gear],
                instructions=instructions,
            )
        )
    db.commit()
