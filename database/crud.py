"""
CRUD operations for database models
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import json

from .models import User, Workout, Activity, Statistics, SportType, WorkoutStatus


# ==================== USER OPERATIONS ====================

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email"""
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Get user by ID"""
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, email: str, display_name: str = None,
                garmin_user_id: str = None, settings: Dict = None) -> User:
    """Create a new user"""
    user = User(
        email=email,
        display_name=display_name,
        garmin_user_id=garmin_user_id,
        settings=settings or {}
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_or_create_user(db: Session, email: str, **kwargs) -> User:
    """Get existing user or create new one"""
    user = get_user_by_email(db, email)
    if not user:
        user = create_user(db, email, **kwargs)
    return user


def update_user_settings(db: Session, user_id: int, settings: Dict) -> User:
    """Update user settings"""
    user = get_user_by_id(db, user_id)
    if user:
        user.settings = settings
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
    return user


def update_user_last_sync(db: Session, user_id: int) -> User:
    """Update last sync timestamp"""
    user = get_user_by_id(db, user_id)
    if user:
        user.last_sync_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
    return user


# ==================== WORKOUT OPERATIONS ====================

def create_workout(db: Session, user_id: int, name: str, sport_type: SportType,
                   structure: Dict, yaml_content: str = None,
                   garmin_workout_id: str = None, scheduled_date: datetime = None,
                   **kwargs) -> Workout:
    """Create a new workout"""
    workout = Workout(
        user_id=user_id,
        name=name,
        sport_type=sport_type,
        structure=structure,
        yaml_content=yaml_content,
        garmin_workout_id=garmin_workout_id,
        scheduled_date=scheduled_date,
        **kwargs
    )
    db.add(workout)
    db.commit()
    db.refresh(workout)
    return workout


def get_workout_by_id(db: Session, workout_id: int) -> Optional[Workout]:
    """Get workout by ID"""
    return db.query(Workout).filter(Workout.id == workout_id).first()


def get_workout_by_garmin_id(db: Session, garmin_workout_id: str) -> Optional[Workout]:
    """Get workout by Garmin workout ID"""
    return db.query(Workout).filter(Workout.garmin_workout_id == garmin_workout_id).first()


def get_user_workouts(db: Session, user_id: int,
                      sport_type: SportType = None,
                      status: WorkoutStatus = None,
                      start_date: datetime = None,
                      end_date: datetime = None,
                      limit: int = 100) -> List[Workout]:
    """Get user workouts with optional filters"""
    query = db.query(Workout).filter(Workout.user_id == user_id)

    if sport_type:
        query = query.filter(Workout.sport_type == sport_type)

    if status:
        query = query.filter(Workout.status == status)

    if start_date:
        query = query.filter(Workout.scheduled_date >= start_date)

    if end_date:
        query = query.filter(Workout.scheduled_date <= end_date)

    return query.order_by(Workout.scheduled_date.desc()).limit(limit).all()


def update_workout(db: Session, workout_id: int, **kwargs) -> Optional[Workout]:
    """Update workout fields"""
    workout = get_workout_by_id(db, workout_id)
    if workout:
        for key, value in kwargs.items():
            if hasattr(workout, key):
                setattr(workout, key, value)
        workout.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(workout)
    return workout


def delete_workout(db: Session, workout_id: int) -> bool:
    """Delete a workout"""
    workout = get_workout_by_id(db, workout_id)
    if workout:
        db.delete(workout)
        db.commit()
        return True
    return False


def get_workouts_by_name(db: Session, user_id: int, name: str) -> List[Workout]:
    """Get workouts by name (for duplicate checking)"""
    return db.query(Workout).filter(
        and_(Workout.user_id == user_id, Workout.name == name)
    ).all()


# ==================== ACTIVITY OPERATIONS ====================

def create_activity(db: Session, user_id: int, garmin_activity_id: str,
                    sport_type: SportType, start_time: datetime,
                    **kwargs) -> Activity:
    """Create a new activity"""
    activity = Activity(
        user_id=user_id,
        garmin_activity_id=garmin_activity_id,
        sport_type=sport_type,
        start_time=start_time,
        **kwargs
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


def get_activity_by_id(db: Session, activity_id: int) -> Optional[Activity]:
    """Get activity by ID"""
    return db.query(Activity).filter(Activity.id == activity_id).first()


def get_activity_by_garmin_id(db: Session, garmin_activity_id: str) -> Optional[Activity]:
    """Get activity by Garmin activity ID"""
    return db.query(Activity).filter(Activity.garmin_activity_id == garmin_activity_id).first()


def activity_exists(db: Session, garmin_activity_id: str) -> bool:
    """Check if activity already exists"""
    return db.query(Activity).filter(Activity.garmin_activity_id == garmin_activity_id).count() > 0


def get_user_activities(db: Session, user_id: int,
                        sport_type: SportType = None,
                        start_date: datetime = None,
                        end_date: datetime = None,
                        limit: int = 100,
                        offset: int = 0) -> List[Activity]:
    """Get user activities with optional filters"""
    query = db.query(Activity).filter(Activity.user_id == user_id)

    if sport_type:
        query = query.filter(Activity.sport_type == sport_type)

    if start_date:
        query = query.filter(Activity.start_time >= start_date)

    if end_date:
        query = query.filter(Activity.start_time <= end_date)

    return query.order_by(Activity.start_time.desc()).limit(limit).offset(offset).all()


def update_activity(db: Session, activity_id: int, **kwargs) -> Optional[Activity]:
    """Update activity fields"""
    activity = get_activity_by_id(db, activity_id)
    if activity:
        for key, value in kwargs.items():
            if hasattr(activity, key):
                setattr(activity, key, value)
        activity.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(activity)
    return activity


def delete_activity(db: Session, activity_id: int) -> bool:
    """Delete an activity"""
    activity = get_activity_by_id(db, activity_id)
    if activity:
        db.delete(activity)
        db.commit()
        return True
    return False


# ==================== STATISTICS OPERATIONS ====================

def create_or_update_statistics(db: Session, user_id: int, period_type: str,
                                 period_start: datetime, period_end: datetime,
                                 sport_type: SportType = None, **kwargs) -> Statistics:
    """Create or update statistics for a period"""
    # Check if stats already exist
    query = db.query(Statistics).filter(
        and_(
            Statistics.user_id == user_id,
            Statistics.period_type == period_type,
            Statistics.period_start == period_start,
            Statistics.period_end == period_end
        )
    )

    if sport_type:
        query = query.filter(Statistics.sport_type == sport_type)
    else:
        query = query.filter(Statistics.sport_type.is_(None))

    stats = query.first()

    if stats:
        # Update existing
        for key, value in kwargs.items():
            if hasattr(stats, key):
                setattr(stats, key, value)
        stats.updated_at = datetime.utcnow()
    else:
        # Create new
        stats = Statistics(
            user_id=user_id,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            sport_type=sport_type,
            **kwargs
        )
        db.add(stats)

    db.commit()
    db.refresh(stats)
    return stats


def get_user_statistics(db: Session, user_id: int, period_type: str = None,
                        sport_type: SportType = None,
                        start_date: datetime = None) -> List[Statistics]:
    """Get user statistics with optional filters"""
    query = db.query(Statistics).filter(Statistics.user_id == user_id)

    if period_type:
        query = query.filter(Statistics.period_type == period_type)

    if sport_type:
        query = query.filter(Statistics.sport_type == sport_type)

    if start_date:
        query = query.filter(Statistics.period_start >= start_date)

    return query.order_by(Statistics.period_start.desc()).all()


def calculate_and_store_statistics(db: Session, user_id: int, period_type: str,
                                   period_start: datetime, period_end: datetime,
                                   sport_type: SportType = None) -> Statistics:
    """Calculate statistics from activities and store them"""
    # Get activities for the period
    activities = get_user_activities(
        db, user_id,
        sport_type=sport_type,
        start_date=period_start,
        end_date=period_end,
        limit=10000  # Get all activities in period
    )

    if not activities:
        return create_or_update_statistics(
            db, user_id, period_type, period_start, period_end,
            sport_type=sport_type,
            total_activities=0
        )

    # Calculate aggregated metrics
    total_distance = sum(a.distance_meters or 0 for a in activities)
    total_duration = sum(a.duration_seconds or 0 for a in activities)
    total_elevation = sum(a.elevation_gain or 0 for a in activities)
    total_calories = sum(a.calories or 0 for a in activities)

    # Calculate averages (only from non-null values)
    paces = [a.average_pace for a in activities if a.average_pace]
    hrs = [a.average_heart_rate for a in activities if a.average_heart_rate]
    powers = [a.average_power for a in activities if a.average_power]

    avg_pace = sum(paces) / len(paces) if paces else None
    avg_hr = sum(hrs) / len(hrs) if hrs else None
    avg_power = sum(powers) / len(powers) if powers else None

    # Best values
    best_pace = min(paces) if paces else None
    best_distance = max(a.distance_meters or 0 for a in activities)
    longest_duration = max(a.duration_seconds or 0 for a in activities)

    # Training effects
    aerobic_effects = [a.aerobic_training_effect for a in activities if a.aerobic_training_effect]
    anaerobic_effects = [a.anaerobic_training_effect for a in activities if a.anaerobic_training_effect]

    avg_aerobic = sum(aerobic_effects) / len(aerobic_effects) if aerobic_effects else None
    avg_anaerobic = sum(anaerobic_effects) / len(anaerobic_effects) if anaerobic_effects else None

    # Prepare chart data
    chart_data = {
        'daily_distance': [],
        'daily_duration': [],
        'activity_types': {}
    }

    # Store statistics
    return create_or_update_statistics(
        db, user_id, period_type, period_start, period_end,
        sport_type=sport_type,
        total_activities=len(activities),
        total_distance_meters=total_distance,
        total_duration_seconds=total_duration,
        total_elevation_gain=total_elevation,
        total_calories=total_calories,
        avg_pace=avg_pace,
        avg_heart_rate=int(avg_hr) if avg_hr else None,
        avg_power=int(avg_power) if avg_power else None,
        best_pace=best_pace,
        best_distance=best_distance,
        longest_duration_seconds=longest_duration,
        avg_aerobic_effect=avg_aerobic,
        avg_anaerobic_effect=avg_anaerobic,
        chart_data=chart_data
    )


# ==================== BULK OPERATIONS ====================

def bulk_create_activities(db: Session, activities: List[Dict]) -> int:
    """Bulk create activities (for sync operations)"""
    count = 0
    for activity_data in activities:
        garmin_id = activity_data.get('garmin_activity_id')
        if not activity_exists(db, garmin_id):
            create_activity(db, **activity_data)
            count += 1
    return count


def bulk_create_workouts(db: Session, workouts: List[Dict]) -> int:
    """Bulk create workouts (for sync operations)"""
    count = 0
    for workout_data in workouts:
        garmin_id = workout_data.get('garmin_workout_id')
        if garmin_id and not get_workout_by_garmin_id(db, garmin_id):
            create_workout(db, **workout_data)
            count += 1
        elif not garmin_id:
            create_workout(db, **workout_data)
            count += 1
    return count
