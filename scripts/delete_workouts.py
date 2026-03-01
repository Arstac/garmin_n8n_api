from database import get_db
from database.models import Workout

db = next(get_db())
deleted = db.query(Workout).delete()
db.commit()
print(f'✅ Deleted {deleted} workouts')