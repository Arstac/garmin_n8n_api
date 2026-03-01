#!/usr/bin/env python
"""
Database initialization and migration script for Garmin Planner
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta
from database import init_db, Database, crud
from database.sync_service import GarminSyncService
from garminconnect import Garmin
import yaml


def load_secrets():
    """Load Garmin credentials from secrets.yaml"""
    secrets_path = Path(__file__).parent.parent / "garmin_planner" / "secrets.yaml"

    if not secrets_path.exists():
        print("❌ secrets.yaml not found. Please create it with your Garmin credentials.")
        print(f"   Expected location: {secrets_path}")
        sys.exit(1)

    with open(secrets_path) as f:
        secrets = yaml.safe_load(f)

    if 'email' not in secrets or 'password' not in secrets:
        print("❌ secrets.yaml must contain 'email' and 'password' fields")
        sys.exit(1)

    return secrets['email'], secrets['password']


def initialize_database():
    """Initialize the database schema"""
    print("🔧 Initializing database...")
    init_db()
    print("✅ Database schema created successfully")


def import_historical_data(email: str, password: str, months: int = 6):
    """
    Import historical data from Garmin Connect

    Args:
        email: Garmin email
        password: Garmin password
        months: Number of months of historical data to import
    """
    print(f"\n📥 Importing historical data ({months} months)...")

    try:
        # Connect to Garmin
        print("🔐 Authenticating with Garmin Connect...")
        garmin_client = Garmin(email, password)
        garmin_client.login()
        print("✅ Authentication successful")

        # Get or create user in database
        db = Database()
        with db.session_scope() as session:
            # Get user profile
            try:
                profile = garmin_client.get_user_profile()
                display_name = profile.get('displayName')
                garmin_user_id = str(profile.get('userProfileId'))
            except:
                display_name = None
                garmin_user_id = None

            # Create or get user
            user = crud.get_or_create_user(
                session, email,
                display_name=display_name,
                garmin_user_id=garmin_user_id
            )
            print(f"✅ User: {user.email} (ID: {user.id})")

            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=months * 30)

            print(f"\n📅 Importing data from {start_date.date()} to {end_date.date()}")

            # Create sync service
            sync_service = GarminSyncService(garmin_client, session, user)

            # Perform full sync
            print("\n⏳ Syncing activities and workouts...")
            result = sync_service.full_sync(start_date, end_date)

            print("\n✅ Sync completed successfully!")
            print(f"   - New activities: {result['new_activities']}")
            print(f"   - New workouts: {result['new_workouts']}")

            # Optionally sync detailed data for recent activities
            print("\n⏳ Syncing detailed activity data (last 50 activities)...")
            recent_activities = crud.get_user_activities(
                session, user.id,
                limit=50
            )

            synced_details = 0
            for activity in recent_activities:
                if not activity.splits:
                    try:
                        sync_service.sync_activity_details(activity.garmin_activity_id)
                        synced_details += 1
                    except:
                        pass  # Some activities might not have detailed data

            print(f"✅ Synced details for {synced_details} activities")

            return result

    except Exception as e:
        print(f"\n❌ Error importing historical data: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def show_summary():
    """Show summary of database contents"""
    print("\n📊 Database Summary")
    print("=" * 50)

    db = Database()
    with db.session_scope() as session:
        # Count users
        from database.models import User, Activity, Workout, Statistics

        user_count = session.query(User).count()
        activity_count = session.query(Activity).count()
        workout_count = session.query(Workout).count()
        stats_count = session.query(Statistics).count()

        print(f"Users:       {user_count}")
        print(f"Activities:  {activity_count}")
        print(f"Workouts:    {workout_count}")
        print(f"Statistics:  {stats_count}")

        # Show user details
        users = session.query(User).all()
        for user in users:
            print(f"\nUser: {user.email}")
            print(f"  Last sync: {user.last_sync_at or 'Never'}")

            # Count activities by sport
            from sqlalchemy import func
            activities_by_sport = session.query(
                Activity.sport_type,
                func.count(Activity.id)
            ).filter(Activity.user_id == user.id).group_by(Activity.sport_type).all()

            if activities_by_sport:
                print("  Activities by sport:")
                for sport, count in activities_by_sport:
                    print(f"    - {sport.value}: {count}")


def main():
    """Main function"""
    print("=" * 50)
    print("Garmin Planner - Database Initialization")
    print("=" * 50)

    import argparse
    parser = argparse.ArgumentParser(description="Initialize Garmin Planner database")
    parser.add_argument(
        '--init-only',
        action='store_true',
        help='Only initialize database schema, do not import data'
    )
    parser.add_argument(
        '--months',
        type=int,
        default=6,
        help='Number of months of historical data to import (default: 6)'
    )
    parser.add_argument(
        '--summary',
        action='store_true',
        help='Show database summary only'
    )

    args = parser.parse_args()

    if args.summary:
        show_summary()
        return

    # Initialize database
    initialize_database()

    if not args.init_only:
        # Load credentials
        email, password = load_secrets()

        # Import historical data
        import_historical_data(email, password, args.months)

        # Show summary
        show_summary()

    print("\n✅ Database initialization complete!")
    print(f"\nDatabase location: {Path(__file__).parent.parent / 'data' / 'garmin_planner.db'}")


if __name__ == "__main__":
    main()
