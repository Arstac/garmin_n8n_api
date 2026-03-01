#!/usr/bin/env python
"""
Database management tools for Garmin Planner
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta
from database import Database, crud
from database.models import User, Activity, Workout, Statistics, SportType
from sqlalchemy import func


def list_users():
    """List all users in database"""
    db = Database()
    with db.session_scope() as session:
        users = session.query(User).all()

        if not users:
            print("No users found in database")
            return

        print("\n📋 Users in database:")
        print("=" * 80)
        for user in users:
            print(f"ID: {user.id}")
            print(f"Email: {user.email}")
            print(f"Display Name: {user.display_name or 'N/A'}")
            print(f"Garmin User ID: {user.garmin_user_id or 'N/A'}")
            print(f"Last Sync: {user.last_sync_at or 'Never'}")
            print(f"Created: {user.created_at}")
            print("-" * 80)


def list_activities(email: str, limit: int = 20):
    """List recent activities for a user"""
    db = Database()
    with db.session_scope() as session:
        user = crud.get_user_by_email(session, email)
        if not user:
            print(f"User {email} not found")
            return

        activities = crud.get_user_activities(session, user.id, limit=limit)

        if not activities:
            print(f"No activities found for {email}")
            return

        print(f"\n📋 Recent activities for {email}:")
        print("=" * 100)

        for activity in activities:
            distance_km = f"{activity.distance_meters/1000:.2f} km" if activity.distance_meters else "N/A"
            duration_min = f"{activity.duration_seconds/60:.1f} min" if activity.duration_seconds else "N/A"
            pace = f"{activity.average_pace:.2f} min/km" if activity.average_pace else "N/A"

            print(f"{activity.start_time.strftime('%Y-%m-%d %H:%M')} | "
                  f"{activity.sport_type.value:10} | "
                  f"{activity.activity_name[:30]:30} | "
                  f"{distance_km:10} | {duration_min:10} | {pace}")


def list_workouts(email: str, limit: int = 20):
    """List workouts for a user"""
    db = Database()
    with db.session_scope() as session:
        user = crud.get_user_by_email(session, email)
        if not user:
            print(f"User {email} not found")
            return

        workouts = crud.get_user_workouts(session, user.id, limit=limit)

        if not workouts:
            print(f"No workouts found for {email}")
            return

        print(f"\n📋 Workouts for {email}:")
        print("=" * 100)

        for workout in workouts:
            scheduled = workout.scheduled_date.strftime('%Y-%m-%d') if workout.scheduled_date else "Not scheduled"
            print(f"{workout.id:4} | {workout.sport_type.value:10} | "
                  f"{workout.name[:30]:30} | {workout.status.value:10} | {scheduled}")


def show_statistics(email: str, period: str = 'weekly', sport: str = None):
    """Show statistics for a user"""
    db = Database()
    with db.session_scope() as session:
        user = crud.get_user_by_email(session, email)
        if not user:
            print(f"User {email} not found")
            return

        sport_filter = SportType(sport) if sport else None
        stats = crud.get_user_statistics(
            session, user.id,
            period_type=period,
            sport_type=sport_filter
        )

        if not stats:
            print(f"No {period} statistics found")
            return

        print(f"\n📊 {period.capitalize()} Statistics for {email}:")
        if sport:
            print(f"Sport: {sport}")
        print("=" * 100)

        for stat in stats:
            print(f"\nPeriod: {stat.period_start.date()} to {stat.period_end.date()}")
            print(f"  Activities: {stat.total_activities}")
            print(f"  Distance: {stat.total_distance_meters/1000:.2f} km")
            print(f"  Duration: {stat.total_duration_seconds/3600:.2f} hours")
            print(f"  Calories: {stat.total_calories}")
            if stat.avg_pace:
                print(f"  Avg Pace: {stat.avg_pace:.2f} min/km")
            if stat.avg_heart_rate:
                print(f"  Avg HR: {stat.avg_heart_rate} bpm")


def delete_user(email: str, confirm: bool = False):
    """Delete a user and all their data"""
    if not confirm:
        print("⚠️  This will delete ALL data for this user!")
        response = input(f"Are you sure you want to delete user {email}? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled")
            return

    db = Database()
    with db.session_scope() as session:
        user = crud.get_user_by_email(session, email)
        if not user:
            print(f"User {email} not found")
            return

        # Delete user (cascade will delete all related data)
        session.delete(user)
        session.commit()

        print(f"✅ User {email} and all related data deleted successfully")


def clear_database(confirm: bool = False):
    """Clear all data from database"""
    if not confirm:
        print("⚠️  WARNING: This will DELETE ALL DATA from the database!")
        response = input("Are you sure? Type 'DELETE ALL' to confirm: ")
        if response != 'DELETE ALL':
            print("Cancelled")
            return

    db = Database()
    db.drop_tables()
    db.create_tables()
    print("✅ Database cleared and recreated")


def calculate_stats_for_user(email: str, days: int = 30):
    """Calculate and store statistics for a user"""
    db = Database()
    with db.session_scope() as session:
        user = crud.get_user_by_email(session, email)
        if not user:
            print(f"User {email} not found")
            return

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        print(f"Calculating statistics for {email} from {start_date.date()} to {end_date.date()}")

        # Calculate weekly stats
        current = start_date
        weeks_calculated = 0

        while current < end_date:
            week_end = min(current + timedelta(days=7), end_date)

            # All sports
            crud.calculate_and_store_statistics(
                session, user.id, 'weekly',
                current, week_end, sport_type=None
            )

            # Per sport
            for sport in [SportType.RUNNING, SportType.CYCLING]:
                crud.calculate_and_store_statistics(
                    session, user.id, 'weekly',
                    current, week_end, sport_type=sport
                )

            current = week_end
            weeks_calculated += 1

        print(f"✅ Calculated statistics for {weeks_calculated} weeks")


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description="Garmin Planner Database Tools")
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # List users
    subparsers.add_parser('list-users', help='List all users')

    # List activities
    activities_parser = subparsers.add_parser('list-activities', help='List user activities')
    activities_parser.add_argument('email', help='User email')
    activities_parser.add_argument('--limit', type=int, default=20, help='Number of activities to show')

    # List workouts
    workouts_parser = subparsers.add_parser('list-workouts', help='List user workouts')
    workouts_parser.add_argument('email', help='User email')
    workouts_parser.add_argument('--limit', type=int, default=20, help='Number of workouts to show')

    # Show statistics
    stats_parser = subparsers.add_parser('show-stats', help='Show user statistics')
    stats_parser.add_argument('email', help='User email')
    stats_parser.add_argument('--period', default='weekly', choices=['weekly', 'monthly', 'yearly'])
    stats_parser.add_argument('--sport', choices=['running', 'cycling', 'swimming'])

    # Calculate statistics
    calc_parser = subparsers.add_parser('calc-stats', help='Calculate statistics for user')
    calc_parser.add_argument('email', help='User email')
    calc_parser.add_argument('--days', type=int, default=30, help='Number of days to calculate')

    # Delete user
    delete_parser = subparsers.add_parser('delete-user', help='Delete a user')
    delete_parser.add_argument('email', help='User email')
    delete_parser.add_argument('--confirm', action='store_true', help='Skip confirmation')

    # Clear database
    clear_parser = subparsers.add_parser('clear-db', help='Clear all database data')
    clear_parser.add_argument('--confirm', action='store_true', help='Skip confirmation')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Execute command
    if args.command == 'list-users':
        list_users()
    elif args.command == 'list-activities':
        list_activities(args.email, args.limit)
    elif args.command == 'list-workouts':
        list_workouts(args.email, args.limit)
    elif args.command == 'show-stats':
        show_statistics(args.email, args.period, args.sport)
    elif args.command == 'calc-stats':
        calculate_stats_for_user(args.email, args.days)
    elif args.command == 'delete-user':
        delete_user(args.email, args.confirm)
    elif args.command == 'clear-db':
        clear_database(args.confirm)


if __name__ == "__main__":
    main()
