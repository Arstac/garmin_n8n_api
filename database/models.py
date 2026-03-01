"""
SQLAlchemy models for Garmin Planner database
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, JSON, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()


class SportType(enum.Enum):
    """Sport types"""
    RUNNING = "running"
    CYCLING = "cycling"
    SWIMMING = "swimming"
    STRENGTH = "strength"
    OTHER = "other"


class WorkoutStatus(enum.Enum):
    """Workout status"""
    PLANNED = "planned"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class User(Base):
    """User model - stores Garmin user information and settings"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    garmin_user_id = Column(String(100), unique=True, nullable=True)
    display_name = Column(String(255), nullable=True)

    # Settings personales
    settings = Column(JSON, nullable=True)  # {deleteSameNameWorkout: bool, zonas FC, FTP, ritmos, etc}

    # Encrypted credentials (optional for future use)
    encrypted_password = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_sync_at = Column(DateTime, nullable=True)

    # Relationships
    workouts = relationship("Workout", back_populates="user", cascade="all, delete-orphan")
    activities = relationship("Activity", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(email={self.email}, display_name={self.display_name})>"


class Workout(Base):
    """Workout model - stores planned/scheduled workouts"""
    __tablename__ = 'workouts'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)

    # Garmin Connect info
    garmin_workout_id = Column(String(100), unique=True, nullable=True, index=True)

    # Workout details
    name = Column(String(255), nullable=False)
    sport_type = Column(Enum(SportType), nullable=False, index=True)

    # Workout structure (YAML or JSON)
    structure = Column(JSON, nullable=False)  # Store the workout steps as JSON
    yaml_content = Column(Text, nullable=True)  # Original YAML for reference

    # Scheduling
    scheduled_date = Column(DateTime, nullable=True, index=True)
    status = Column(Enum(WorkoutStatus), default=WorkoutStatus.PLANNED, index=True)

    # Metadata
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Estimated values
    estimated_duration_seconds = Column(Integer, nullable=True)
    estimated_distance_meters = Column(Float, nullable=True)

    # Relationships
    user = relationship("User", back_populates="workouts")
    activity = relationship("Activity", back_populates="workout", uselist=False)

    def __repr__(self):
        return f"<Workout(name={self.name}, sport={self.sport_type.value}, status={self.status.value})>"


class Activity(Base):
    """Activity model - stores completed activities synced from Garmin"""
    __tablename__ = 'activities'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    workout_id = Column(Integer, ForeignKey('workouts.id'), nullable=True)  # Link to planned workout

    # Garmin Connect info
    garmin_activity_id = Column(String(100), unique=True, nullable=False, index=True)

    # Basic info
    activity_name = Column(String(255), nullable=True)
    sport_type = Column(Enum(SportType), nullable=False, index=True)
    start_time = Column(DateTime, nullable=False, index=True)

    # Duration and distance
    duration_seconds = Column(Integer, nullable=True)
    distance_meters = Column(Float, nullable=True)

    # Performance metrics
    average_pace = Column(Float, nullable=True)  # min/km
    average_speed = Column(Float, nullable=True)  # km/h
    average_heart_rate = Column(Integer, nullable=True)
    max_heart_rate = Column(Integer, nullable=True)
    average_cadence = Column(Integer, nullable=True)
    average_power = Column(Integer, nullable=True)
    max_power = Column(Integer, nullable=True)

    # Elevation
    elevation_gain = Column(Float, nullable=True)
    elevation_loss = Column(Float, nullable=True)

    # Energy
    calories = Column(Integer, nullable=True)

    # Training effect
    aerobic_training_effect = Column(Float, nullable=True)
    anaerobic_training_effect = Column(Float, nullable=True)

    # Weather (if available)
    weather_data = Column(JSON, nullable=True)

    # Detailed data (splits, laps, zones)
    splits = Column(JSON, nullable=True)
    laps = Column(JSON, nullable=True)
    heart_rate_zones = Column(JSON, nullable=True)
    power_zones = Column(JSON, nullable=True)

    # Full activity data from Garmin (for reference)
    raw_data = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="activities")
    workout = relationship("Workout", back_populates="activity")

    def __repr__(self):
        return f"<Activity(name={self.activity_name}, sport={self.sport_type.value}, date={self.start_time})>"


class Statistics(Base):
    """Statistics model - pre-calculated stats for performance"""
    __tablename__ = 'statistics'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)

    # Period
    period_type = Column(String(20), nullable=False, index=True)  # 'weekly', 'monthly', 'yearly'
    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False)

    # Sport filter
    sport_type = Column(Enum(SportType), nullable=True, index=True)  # None = all sports

    # Aggregated metrics
    total_activities = Column(Integer, default=0)
    total_distance_meters = Column(Float, default=0)
    total_duration_seconds = Column(Integer, default=0)
    total_elevation_gain = Column(Float, default=0)
    total_calories = Column(Integer, default=0)

    # Averages
    avg_pace = Column(Float, nullable=True)
    avg_heart_rate = Column(Integer, nullable=True)
    avg_power = Column(Integer, nullable=True)

    # Performance indicators
    best_pace = Column(Float, nullable=True)
    best_distance = Column(Float, nullable=True)
    longest_duration_seconds = Column(Integer, nullable=True)

    # Training load
    avg_aerobic_effect = Column(Float, nullable=True)
    avg_anaerobic_effect = Column(Float, nullable=True)

    # Additional data for charts
    chart_data = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")

    def __repr__(self):
        return f"<Statistics(user_id={self.user_id}, period={self.period_type}, activities={self.total_activities})>"
