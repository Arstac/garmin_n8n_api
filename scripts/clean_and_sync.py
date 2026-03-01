"""
Clean database and sync from Garmin Connect
"""
from database import get_db
from database.models import Workout, Activity
import requests

print("🗑️  Step 1: Cleaning database...")
db = next(get_db())

workouts_deleted = db.query(Workout).delete()
activities_deleted = db.query(Activity).delete()
db.commit()

print(f"   ✅ Deleted {workouts_deleted} workouts")
print(f"   ✅ Deleted {activities_deleted} activities")

print("\n🔄 Step 2: Syncing from Garmin Connect...")
print("   This may take a few minutes...\n")

url = "http://localhost:8000/db/sync"
password = input("Enter your Garmin password: ")

data = {
    "email": "arnaucosta95@gmail.com",
    "password": password,
    "start_date": "2025-01-01",
    "end_date": "2025-10-09",
    "sync_details": False
}

response = requests.post(url, json=data)

if response.status_code == 200:
    result = response.json()
    print("✅ Sync completed successfully!\n")
    print(f"   📊 New activities synced: {result['new_activities']}")
    print(f"   🏋️  New workouts synced: {result['new_workouts']}")
    print(f"   📅 Sync date: {result['sync_date']}")
else:
    print(f"❌ Error: {response.status_code}")
    print(response.json())
