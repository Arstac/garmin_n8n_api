"""
Fix workouts with empty list structure in database
"""
from database import get_db
from database.models import Workout

def fix_workout_structures():
    db = next(get_db())

    # Get all workouts
    workouts = db.query(Workout).all()

    fixed_count = 0
    for workout in workouts:
        # If structure is a list, convert to dict
        if isinstance(workout.structure, list):
            workout.structure = {'segments': workout.structure} if workout.structure else {}
            fixed_count += 1

    db.commit()
    print(f"✅ Fixed {fixed_count} workouts with incorrect structure")

    # Verify
    remaining = db.query(Workout).filter(
        Workout.structure == []
    ).count()

    print(f"Remaining workouts with list structure: {remaining}")

if __name__ == "__main__":
    fix_workout_structures()
