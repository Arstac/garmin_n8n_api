"""
Database-backed API endpoints for Garmin Planner
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel
from garminconnect import Garmin
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import get_db, crud
from database.models import SportType, WorkoutStatus, User, Workout, Activity, Statistics
from database.sync_service import GarminSyncService

router = APIRouter(prefix="/db", tags=["Database"])


# ==================== PYDANTIC MODELS ====================

class UserCreate(BaseModel):
    email: str
    display_name: Optional[str] = None
    garmin_user_id: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    email: str
    display_name: Optional[str]
    garmin_user_id: Optional[str]
    settings: Optional[dict]
    last_sync_at: Optional[datetime]

    class Config:
        from_attributes = True


class WorkoutCreate(BaseModel):
    # Acepta ambos formatos: camelCase (frontend) y snake_case (backend)
    name: Optional[str] = None
    title: Optional[str] = None  # Alias para name

    sport_type: Optional[str] = None
    sportType: Optional[str] = None  # Alias para sport_type

    structure: Optional[dict] = None  # Ahora es opcional

    # Campos adicionales del frontend
    duration: Optional[int] = None  # Duración en minutos
    intensity: Optional[str] = None  # Nivel de intensidad

    yaml_content: Optional[str] = None
    scheduled_date: Optional[datetime] = None

    description: Optional[str] = None
    notes: Optional[str] = None  # Alias para description

    def get_name(self) -> str:
        """Obtiene el nombre del workout, priorizando 'name' sobre 'title'"""
        return self.name or self.title or "Untitled Workout"

    def get_sport_type(self) -> str:
        """Obtiene el sport_type, priorizando 'sport_type' sobre 'sportType'"""
        return self.sport_type or self.sportType or "other"

    def get_description(self) -> Optional[str]:
        """Obtiene la descripción, priorizando 'description' sobre 'notes'"""
        return self.description or self.notes or None

    def get_structure(self) -> dict:
        """Genera estructura automáticamente si no se proporciona"""
        if self.structure:
            return self.structure

        # Generar estructura simple basada en duration e intensity
        steps = []

        if self.duration:
            steps.append({
                "type": "workout",
                "duration": self.duration * 60,  # Convertir minutos a segundos
                "intensity": self.intensity or "medium"
            })

        return {"steps": steps} if steps else {}


class WorkoutResponse(BaseModel):
    id: int
    name: str
    sport_type: str
    structure: dict
    garmin_workout_id: Optional[str]
    scheduled_date: Optional[datetime]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class ActivityResponse(BaseModel):
    id: int
    garmin_activity_id: str
    activity_name: Optional[str]
    sport_type: str
    start_time: datetime
    duration_seconds: Optional[int]
    distance_meters: Optional[float]
    average_pace: Optional[float]
    average_heart_rate: Optional[int]
    calories: Optional[int]
    elevation_gain: Optional[float]

    class Config:
        from_attributes = True


class SyncRequest(BaseModel):
    email: str
    password: str
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    sync_details: bool = False  # Whether to sync detailed activity data


class SyncResponse(BaseModel):
    success: bool
    new_activities: int
    updated_activities: int
    new_workouts: int
    updated_workouts: int
    sync_date: str
    message: str


class StatisticsResponse(BaseModel):
    period_type: str
    period_start: datetime
    period_end: datetime
    sport_type: Optional[str]
    total_activities: int
    total_distance_meters: float
    total_duration_seconds: int
    avg_pace: Optional[float]
    avg_heart_rate: Optional[int]
    total_calories: int

    class Config:
        from_attributes = True


# ==================== HELPER FUNCTIONS ====================

def get_or_create_user_from_email(db: Session, email: str) -> User:
    """Get or create user by email"""
    user = crud.get_user_by_email(db, email)
    if not user:
        user = crud.create_user(db, email=email)
    return user


def get_garmin_client_and_user(email: str, password: str, db: Session) -> tuple[Garmin, User]:
    """Authenticate with Garmin and get/create user"""
    try:
        garmin_client = Garmin(email, password)
        garmin_client.login()

        # Get user profile to extract additional info
        try:
            profile = garmin_client.get_user_profile()
            display_name = profile.get('displayName')
            user_id = str(profile.get('userProfileId'))
        except:
            display_name = None
            user_id = None

        # Get or create user in database
        user = crud.get_user_by_email(db, email)
        if not user:
            user = crud.create_user(
                db, email=email,
                display_name=display_name,
                garmin_user_id=user_id
            )

        return garmin_client, user

    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Garmin authentication failed: {str(e)}")


# ==================== USER ENDPOINTS ====================

@router.post("/users", response_model=UserResponse)
def create_user_endpoint(user_data: UserCreate, db: Session = Depends(get_db)):
    """Create a new user"""
    existing = crud.get_user_by_email(db, user_data.email)
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    user = crud.create_user(
        db, email=user_data.email,
        display_name=user_data.display_name,
        garmin_user_id=user_data.garmin_user_id
    )
    return user


@router.get("/users/{email}", response_model=UserResponse)
def get_user_endpoint(email: str, db: Session = Depends(get_db)):
    """Get user by email"""
    user = crud.get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ==================== SYNC ENDPOINTS ====================

@router.post("/sync", response_model=SyncResponse)
def sync_from_garmin(sync_request: SyncRequest, db: Session = Depends(get_db)):
    """
    Sync activities and workouts from Garmin Connect to database
    """
    try:
        # Parse dates
        start_date = datetime.strptime(sync_request.start_date, "%Y-%m-%d")
        end_date = datetime.strptime(sync_request.end_date, "%Y-%m-%d")

        # Authenticate and get user
        garmin_client, user = get_garmin_client_and_user(
            sync_request.email,
            sync_request.password,
            db
        )

        # Create sync service
        sync_service = GarminSyncService(garmin_client, db, user)

        # Perform full sync
        result = sync_service.full_sync(start_date, end_date)

        # Optionally sync detailed data for recent activities
        if sync_request.sync_details:
            # Get recent activities
            recent_activities = crud.get_user_activities(
                db, user.id,
                start_date=start_date,
                end_date=end_date,
                limit=50
            )

            for activity in recent_activities:
                if not activity.splits:  # Only sync if not already synced
                    sync_service.sync_activity_details(activity.garmin_activity_id)

        result['message'] = f"Synced {result['new_activities']} activities and {result['new_workouts']} workouts"
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.post("/sync/activity/{activity_id}")
def sync_activity_details_endpoint(
    activity_id: str,
    email: str,
    password: str,
    db: Session = Depends(get_db)
):
    """Sync detailed data for a specific activity"""
    try:
        garmin_client, user = get_garmin_client_and_user(email, password, db)
        sync_service = GarminSyncService(garmin_client, db, user)

        success = sync_service.sync_activity_details(activity_id)

        if success:
            return {"message": f"Activity {activity_id} details synced successfully"}
        else:
            raise HTTPException(status_code=404, detail="Activity not found")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


# ==================== WORKOUT ENDPOINTS ====================

@router.get("/users/{email}/workouts", response_model=List[WorkoutResponse])
def get_user_workouts_endpoint(
    email: str,
    sport_type: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db)
):
    """Get user workouts from database"""
    user = crud.get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Parse filters
    sport_filter = SportType(sport_type) if sport_type else None
    status_filter = WorkoutStatus(status) if status else None
    start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
    end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

    workouts = crud.get_user_workouts(
        db, user.id,
        sport_type=sport_filter,
        status=status_filter,
        start_date=start_dt,
        end_date=end_dt,
        limit=limit
    )

    return workouts


@router.post("/users/{email}/workouts", response_model=WorkoutResponse)
def create_workout_endpoint(
    email: str,
    workout_data: WorkoutCreate,
    upload_to_garmin: bool = Query(True),
    garmin_password: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Create a workout and optionally upload to Garmin Connect
    """
    user = crud.get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Obtener valores usando los métodos helper
    workout_name = workout_data.get_name()
    workout_sport_type = workout_data.get_sport_type()
    workout_description = workout_data.get_description()
    workout_structure = workout_data.get_structure()

    # Parse sport type
    try:
        sport_type = SportType(workout_sport_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid sport type: {workout_sport_type}")

    # Create workout in database
    workout = crud.create_workout(
        db, user_id=user.id,
        name=workout_name,
        sport_type=sport_type,
        structure=workout_structure,
        yaml_content=workout_data.yaml_content,
        scheduled_date=workout_data.scheduled_date,
        description=workout_description
    )

    # Upload to Garmin if requested
    if upload_to_garmin:
        if not garmin_password:
            raise HTTPException(status_code=400, detail="Password required to upload to Garmin")

        try:
            from garmin_planner.client import Client
            from garmin_planner.main import createWorkoutJson

            # Create Garmin client
            garmin_client = Client(email, garmin_password)

            # Convert workout structure to Garmin format
            workout_json = createWorkoutJson(
                workout_data.name,
                workout_data.structure,
                workout_data.sport_type
            )

            # Import to Garmin
            result = garmin_client.importWorkout(workout_json)
            garmin_workout_id = str(result.get('workoutId'))

            # Update workout with Garmin ID
            crud.update_workout(db, workout.id, garmin_workout_id=garmin_workout_id)

        except Exception as e:
            # Workout is already in DB, just log the error
            print(f"Warning: Could not upload to Garmin: {e}")

    db.refresh(workout)
    return workout


@router.delete("/users/{email}/workouts/{workout_id}")
def delete_workout_endpoint(
    email: str,
    workout_id: int,
    db: Session = Depends(get_db)
):
    """Delete a workout from database"""
    user = crud.get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    workout = crud.get_workout_by_id(db, workout_id)
    if not workout or workout.user_id != user.id:
        raise HTTPException(status_code=404, detail="Workout not found")

    success = crud.delete_workout(db, workout_id)
    if success:
        return {"message": "Workout deleted successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete workout")


# ==================== ACTIVITY ENDPOINTS ====================

@router.get("/users/{email}/activities", response_model=List[ActivityResponse])
def get_user_activities_endpoint(
    email: str,
    sport_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Get user activities from database"""
    user = crud.get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Parse filters
    sport_filter = SportType(sport_type) if sport_type else None
    start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
    end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

    activities = crud.get_user_activities(
        db, user.id,
        sport_type=sport_filter,
        start_date=start_dt,
        end_date=end_dt,
        limit=limit,
        offset=offset
    )

    return activities


@router.get("/users/{email}/activities/{activity_id}", response_model=ActivityResponse)
def get_activity_endpoint(
    email: str,
    activity_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific activity"""
    user = crud.get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    activity = crud.get_activity_by_id(db, activity_id)
    if not activity or activity.user_id != user.id:
        raise HTTPException(status_code=404, detail="Activity not found")

    return activity


# ==================== STATISTICS ENDPOINTS ====================

@router.get("/users/{email}/statistics", response_model=List[StatisticsResponse])
def get_user_statistics_endpoint(
    email: str,
    period_type: Optional[str] = Query(None, regex="^(weekly|monthly|yearly)$"),
    sport_type: Optional[str] = None,
    start_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get user statistics"""
    user = crud.get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Parse filters
    sport_filter = SportType(sport_type) if sport_type else None
    start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None

    statistics = crud.get_user_statistics(
        db, user.id,
        period_type=period_type,
        sport_type=sport_filter,
        start_date=start_dt
    )

    return statistics


@router.post("/users/{email}/statistics/calculate")
def calculate_statistics_endpoint(
    email: str,
    period_type: str = Query(..., regex="^(weekly|monthly|yearly)$"),
    start_date: str = Query(...),
    end_date: str = Query(...),
    sport_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Calculate and store statistics for a period"""
    user = crud.get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        sport_filter = SportType(sport_type) if sport_type else None

        stats = crud.calculate_and_store_statistics(
            db, user.id, period_type, start_dt, end_dt, sport_filter
        )

        return {
            "message": "Statistics calculated successfully",
            "period": f"{start_date} to {end_date}",
            "total_activities": stats.total_activities,
            "total_distance_km": stats.total_distance_meters / 1000 if stats.total_distance_meters else 0
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate statistics: {str(e)}")


@router.get("/users/{email}/dashboard")
def get_dashboard_data(
    email: str,
    days: int = Query(7, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    Get dashboard data for the user (summary for charts and stats)
    """
    user = crud.get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Get activities
    activities = crud.get_user_activities(
        db, user.id,
        start_date=start_date,
        end_date=end_date,
        limit=1000
    )

    # Calculate totals by sport
    by_sport = {}
    for activity in activities:
        sport = activity.sport_type.value
        if sport not in by_sport:
            by_sport[sport] = {
                'count': 0,
                'total_distance': 0,
                'total_duration': 0,
                'total_calories': 0,
                'total_elevation': 0
            }

        by_sport[sport]['count'] += 1
        by_sport[sport]['total_distance'] += activity.distance_meters or 0
        by_sport[sport]['total_duration'] += activity.duration_seconds or 0
        by_sport[sport]['total_calories'] += activity.calories or 0
        by_sport[sport]['total_elevation'] += activity.elevation_gain or 0

    # Get recent statistics
    stats = crud.get_user_statistics(
        db, user.id,
        period_type='weekly',
        start_date=start_date
    )

    return {
        'period_days': days,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'total_activities': len(activities),
        'by_sport': by_sport,
        'recent_activities': [
            {
                'id': a.id,
                'name': a.activity_name,
                'sport': a.sport_type.value,
                'date': a.start_time.isoformat(),
                'distance_km': round(a.distance_meters / 1000, 2) if a.distance_meters else 0,
                'duration_min': round(a.duration_seconds / 60, 1) if a.duration_seconds else 0,
            }
            for a in activities[:10]  # Last 10
        ],
        'statistics': [
            {
                'period_start': s.period_start.isoformat(),
                'period_end': s.period_end.isoformat(),
                'sport': s.sport_type.value if s.sport_type else 'all',
                'activities': s.total_activities,
                'distance_km': round(s.total_distance_meters / 1000, 2) if s.total_distance_meters else 0,
                'duration_hours': round(s.total_duration_seconds / 3600, 1) if s.total_duration_seconds else 0,
            }
            for s in stats[:8]  # Last 8 weeks
        ]
    }


# ==================== CALENDAR ENDPOINT ====================

@router.get("/users/{email}/calendar/{year}/{month}")
def get_calendar_month(
    email: str,
    year: int,
    month: int,
    db: Session = Depends(get_db)
):
    """
    Get calendar data for a specific month (activities and scheduled workouts)
    Returns a dictionary with dates as keys and activities/workouts as values
    """
    user = crud.get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Calculate date range for the month
    from calendar import monthrange
    _, num_days = monthrange(year, month)

    start_date = datetime(year, month, 1)
    end_date = datetime(year, month, num_days, 23, 59, 59)

    # Get activities for the month
    activities = crud.get_user_activities(
        db, user.id,
        start_date=start_date,
        end_date=end_date,
        limit=1000
    )

    # Get workouts scheduled for the month
    workouts = crud.get_user_workouts(
        db, user.id,
        start_date=start_date,
        end_date=end_date,
        limit=1000
    )

    # Organize by date
    calendar_data = {}

    # Add activities
    for activity in activities:
        date_key = activity.start_time.strftime("%Y-%m-%d")
        if date_key not in calendar_data:
            calendar_data[date_key] = {'activities': [], 'workouts': []}

        calendar_data[date_key]['activities'].append({
            'id': activity.id,
            'garmin_activity_id': activity.garmin_activity_id,
            'name': activity.activity_name,
            'sport_type': activity.sport_type.value,
            'start_time': activity.start_time.isoformat(),
            'duration_seconds': activity.duration_seconds,
            'distance_meters': activity.distance_meters,
            'calories': activity.calories,
            'average_heart_rate': activity.average_heart_rate,
            'type': 'activity'
        })

    # Add scheduled workouts
    for workout in workouts:
        if not workout.scheduled_date:
            continue

        date_key = workout.scheduled_date.strftime("%Y-%m-%d")
        if date_key not in calendar_data:
            calendar_data[date_key] = {'activities': [], 'workouts': []}

        calendar_data[date_key]['workouts'].append({
            'id': workout.id,
            'garmin_workout_id': workout.garmin_workout_id,
            'name': workout.name,
            'sport_type': workout.sport_type.value,
            'scheduled_date': workout.scheduled_date.isoformat(),
            'status': workout.status.value,
            'description': workout.description,
            'estimated_duration_seconds': workout.estimated_duration_seconds,
            'estimated_distance_meters': workout.estimated_distance_meters,
            'type': 'workout'
        })

    return {
        'year': year,
        'month': month,
        'num_days': num_days,
        'calendar': calendar_data
    }
