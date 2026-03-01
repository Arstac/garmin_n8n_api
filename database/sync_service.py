"""
Synchronization service between Garmin Connect and local database
"""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from garminconnect import Garmin
import logging

from . import crud
from .models import SportType, WorkoutStatus, User

logger = logging.getLogger(__name__)


class GarminSyncService:
    """Service to sync data between Garmin Connect and local database"""

    def __init__(self, garmin_client: Garmin, db: Session, user: User):
        self.garmin = garmin_client
        self.db = db
        self.user = user

    def map_sport_type(self, garmin_activity_type: str) -> SportType:
        """Map Garmin activity type to our SportType enum"""
        activity_type_lower = garmin_activity_type.lower()

        if 'run' in activity_type_lower or 'jogging' in activity_type_lower:
            return SportType.RUNNING
        elif 'cycl' in activity_type_lower or 'bike' in activity_type_lower or 'bik' in activity_type_lower:
            return SportType.CYCLING
        elif 'swim' in activity_type_lower:
            return SportType.SWIMMING
        else:
            return SportType.OTHER

    def sync_activities(self, start_date: datetime, end_date: datetime) -> Tuple[int, int]:
        """
        Sync activities from Garmin Connect to database
        Returns: (new_activities_count, updated_activities_count)
        """
        new_count = 0
        updated_count = 0

        try:
            # Get activities from Garmin
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")

            logger.info(f"Syncing activities from {start_str} to {end_str}")

            # Get activities by date range
            garmin_activities = self.garmin.get_activities_by_date(
                startdate=start_str,
                enddate=end_str
            )

            if not garmin_activities:
                logger.info("No activities found in Garmin for this date range")
                return 0, 0

            for garmin_activity in garmin_activities:
                activity_id = str(garmin_activity.get('activityId'))

                # Check if activity already exists
                existing = crud.get_activity_by_garmin_id(self.db, activity_id)

                if existing:
                    # Optionally update existing activity
                    # For now, we skip updating to avoid overwriting
                    continue

                # Parse activity data
                activity_data = self._parse_activity_data(garmin_activity)

                if activity_data:
                    crud.create_activity(self.db, **activity_data)
                    new_count += 1
                    logger.info(f"Synced new activity: {activity_data.get('activity_name')}")

        except Exception as e:
            logger.error(f"Error syncing activities: {e}")
            raise

        # Update user's last sync timestamp
        crud.update_user_last_sync(self.db, self.user.id)

        return new_count, updated_count

    def _parse_activity_data(self, garmin_activity: Dict) -> Optional[Dict]:
        """Parse Garmin activity data to our database format"""
        try:
            activity_id = str(garmin_activity.get('activityId'))
            activity_name = garmin_activity.get('activityName', 'Unnamed Activity')

            # Parse activity type
            activity_type = garmin_activity.get('activityType', {})
            if isinstance(activity_type, dict):
                type_key = activity_type.get('typeKey', 'other')
            else:
                type_key = str(activity_type)

            sport_type = self.map_sport_type(type_key)

            # Parse start time
            start_time_str = garmin_activity.get('startTimeLocal') or garmin_activity.get('startTimeGMT')
            if start_time_str:
                # Handle different datetime formats
                try:
                    start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                except:
                    start_time = datetime.strptime(start_time_str[:19], "%Y-%m-%d %H:%M:%S")
            else:
                logger.warning(f"Activity {activity_id} has no start time, skipping")
                return None

            # Basic metrics
            duration = garmin_activity.get('duration')  # seconds
            distance = garmin_activity.get('distance')  # meters

            # Convert duration to integer (round)
            if duration is not None:
                duration = int(round(duration))

            # Performance metrics
            avg_speed = garmin_activity.get('averageSpeed')  # m/s
            avg_pace = None
            if avg_speed and avg_speed > 0:
                # Convert m/s to min/km
                avg_pace = 1000 / (avg_speed * 60) if avg_speed > 0 else None

            avg_hr = garmin_activity.get('averageHR')
            max_hr = garmin_activity.get('maxHR')
            avg_cadence = garmin_activity.get('averageRunningCadenceInStepsPerMinute') or \
                         garmin_activity.get('averageBikingCadenceInRevPerMinute')

            # Convert to int if present
            if avg_hr is not None:
                avg_hr = int(round(avg_hr))
            if max_hr is not None:
                max_hr = int(round(max_hr))
            if avg_cadence is not None:
                avg_cadence = int(round(avg_cadence))

            # Power metrics (cycling)
            avg_power = garmin_activity.get('avgPower')
            max_power = garmin_activity.get('maxPower')

            if avg_power is not None:
                avg_power = int(round(avg_power))
            if max_power is not None:
                max_power = int(round(max_power))

            # Elevation
            elevation_gain = garmin_activity.get('elevationGain')
            elevation_loss = garmin_activity.get('elevationLoss')

            # Energy
            calories = garmin_activity.get('calories')
            if calories is not None:
                calories = int(round(calories))

            # Training effect
            aerobic_effect = garmin_activity.get('aerobicTrainingEffect')
            anaerobic_effect = garmin_activity.get('anaerobicTrainingEffect')

            return {
                'user_id': self.user.id,
                'garmin_activity_id': activity_id,
                'activity_name': activity_name,
                'sport_type': sport_type,
                'start_time': start_time,
                'duration_seconds': duration,
                'distance_meters': distance,
                'average_pace': avg_pace,
                'average_speed': avg_speed,
                'average_heart_rate': avg_hr,
                'max_heart_rate': max_hr,
                'average_cadence': avg_cadence,
                'average_power': avg_power,
                'max_power': max_power,
                'elevation_gain': elevation_gain,
                'elevation_loss': elevation_loss,
                'calories': calories,
                'aerobic_training_effect': aerobic_effect,
                'anaerobic_training_effect': anaerobic_effect,
                'raw_data': garmin_activity  # Store full data for reference
            }

        except Exception as e:
            logger.error(f"Error parsing activity {garmin_activity.get('activityId')}: {e}")
            return None

    def sync_activity_details(self, activity_id: str) -> bool:
        """
        Sync detailed data for a specific activity (splits, laps, HR zones)
        """
        try:
            # Get activity from database
            activity = crud.get_activity_by_garmin_id(self.db, activity_id)
            if not activity:
                logger.warning(f"Activity {activity_id} not found in database")
                return False

            # Get splits
            try:
                splits = self.garmin.get_activity_splits(activity_id)
                activity.splits = splits
            except Exception as e:
                logger.warning(f"Could not get splits for activity {activity_id}: {e}")

            # Get weather data
            try:
                weather = self.garmin.get_activity_weather(activity_id)
                activity.weather_data = weather
            except Exception as e:
                logger.warning(f"Could not get weather for activity {activity_id}: {e}")

            # Get activity details (includes HR zones, power zones, etc.)
            try:
                details = self.garmin.get_activity_details(activity_id)

                # Extract HR zones if available
                if 'heartRateZones' in details:
                    activity.heart_rate_zones = details['heartRateZones']

                # Extract power zones if available
                if 'powerZones' in details:
                    activity.power_zones = details['powerZones']

            except Exception as e:
                logger.warning(f"Could not get details for activity {activity_id}: {e}")

            self.db.commit()
            return True

        except Exception as e:
            logger.error(f"Error syncing details for activity {activity_id}: {e}")
            return False

    def sync_workouts(self, start_date: datetime = None, end_date: datetime = None) -> Tuple[int, int]:
        """
        Sync workouts from Garmin Connect to database
        Returns: (new_workouts_count, updated_workouts_count)
        """
        new_count = 0
        updated_count = 0

        try:
            # Get all workouts from Garmin
            garmin_workouts = self.garmin.get_workouts(start=1, limit=999)

            if not garmin_workouts:
                logger.info("No workouts found in Garmin")
                return 0, 0

            for garmin_workout in garmin_workouts:
                workout_id = str(garmin_workout.get('workoutId'))

                # Check if workout already exists
                existing = crud.get_workout_by_garmin_id(self.db, workout_id)

                if existing:
                    continue

                # Get full workout details from Garmin
                try:
                    workout_detail = self.garmin.get_workout_by_id(workout_id)
                except Exception as e:
                    logger.warning(f"Could not get details for workout {workout_id}: {e}")
                    workout_detail = garmin_workout

                # Parse workout data
                workout_data = self._parse_workout_data(workout_detail)

                if workout_data:
                    # Filter by date if specified
                    if start_date or end_date:
                        scheduled = workout_data.get('scheduled_date')
                        if scheduled:
                            if start_date and scheduled < start_date:
                                continue
                            if end_date and scheduled > end_date:
                                continue

                    crud.create_workout(self.db, **workout_data)
                    new_count += 1
                    logger.info(f"Synced new workout: {workout_data.get('name')}")

        except Exception as e:
            logger.error(f"Error syncing workouts: {e}")
            raise

        return new_count, updated_count

    def _parse_workout_data(self, garmin_workout: Dict) -> Optional[Dict]:
        """Parse Garmin workout data to our database format"""
        try:
            workout_id = str(garmin_workout.get('workoutId'))
            workout_name = garmin_workout.get('workoutName', 'Unnamed Workout')

            # Parse sport type
            sport_type_key = garmin_workout.get('sportType', {})
            if isinstance(sport_type_key, dict):
                sport_key = sport_type_key.get('sportTypeKey', 'other')
            else:
                sport_key = str(sport_type_key)

            sport_type = self.map_sport_type(sport_key)

            # Parse scheduled date if available
            scheduled_date = None
            # Note: Garmin workouts don't always have a scheduled date in the list
            # We might need to get workout details separately

            # Status
            status = WorkoutStatus.PLANNED  # Default

            # Parse structure - capture full workout structure
            structure = {}

            # Try to get workout segments (the main structure)
            workout_segments = garmin_workout.get('workoutSegments', [])
            if workout_segments:
                structure['segments'] = workout_segments

            # Capture additional workout fields that define structure
            if 'workoutSteps' in garmin_workout:
                structure['steps'] = garmin_workout['workoutSteps']

            # Store sport type in structure for reference
            if 'sportType' in garmin_workout:
                structure['sportType'] = garmin_workout['sportType']

            # Capture estimated duration if available
            if 'estimatedDurationInSecs' in garmin_workout:
                structure['estimatedDuration'] = garmin_workout['estimatedDurationInSecs']

            # Capture estimated distance if available
            if 'estimatedDistanceInMeters' in garmin_workout:
                structure['estimatedDistance'] = garmin_workout['estimatedDistanceInMeters']

            # If structure is still empty, store the entire workout as raw data
            if not structure or structure == {}:
                structure = {
                    'raw': garmin_workout,
                    'note': 'Full workout data - structure not parsed'
                }

            # Parse estimated values
            estimated_duration = garmin_workout.get('estimatedDurationInSecs')
            estimated_distance = garmin_workout.get('estimatedDistanceInMeters')

            return {
                'user_id': self.user.id,
                'garmin_workout_id': workout_id,
                'name': workout_name,
                'sport_type': sport_type,
                'structure': structure,
                'scheduled_date': scheduled_date,
                'status': status,
                'description': garmin_workout.get('description'),
                'estimated_duration_seconds': estimated_duration,
                'estimated_distance_meters': estimated_distance,
            }

        except Exception as e:
            logger.error(f"Error parsing workout {garmin_workout.get('workoutId')}: {e}")
            return None

    def sync_calendar(self, start_date: datetime, end_date: datetime) -> int:
        """
        Sync calendar to update scheduled workout dates
        Returns number of workouts updated with scheduled dates
        """
        updated_count = 0

        try:
            # Iterate through each month in the date range
            current_date = start_date.replace(day=1)

            while current_date <= end_date:
                year = current_date.year
                month = current_date.month

                logger.info(f"Syncing calendar for {year}-{month:02d}")

                try:
                    # Get calendar data from Garmin
                    url = f"calendar-service/year/{year}/month/{month}"
                    calendar_data = self.garmin.download(url)

                    # Decode if bytes
                    if isinstance(calendar_data, bytes):
                        calendar_data = calendar_data.decode("utf-8")

                    # Parse JSON
                    import json
                    calendar_dict = json.loads(calendar_data) if isinstance(calendar_data, str) else calendar_data

                    # Process calendar items
                    calendar_items = calendar_dict.get('calendarItems', [])

                    for item in calendar_items:
                        # Only process workout items
                        if item.get('itemType') != 'workout':
                            continue

                        workout_id = item.get('workoutId')
                        scheduled_date_str = item.get('date')

                        if not workout_id or not scheduled_date_str:
                            continue

                        # Parse date
                        scheduled_date = datetime.strptime(scheduled_date_str, "%Y-%m-%d")

                        # Find workout in database
                        workout = crud.get_workout_by_garmin_id(self.db, str(workout_id))

                        if workout:
                            # Update scheduled date if different
                            if workout.scheduled_date != scheduled_date:
                                workout.scheduled_date = scheduled_date
                                workout.status = WorkoutStatus.SCHEDULED
                                updated_count += 1
                                logger.info(f"Updated workout {workout.name} scheduled for {scheduled_date_str}")

                except Exception as e:
                    logger.warning(f"Could not sync calendar for {year}-{month:02d}: {e}")

                # Move to next month
                if month == 12:
                    current_date = current_date.replace(year=year + 1, month=1)
                else:
                    current_date = current_date.replace(month=month + 1)

            self.db.commit()

        except Exception as e:
            logger.error(f"Error syncing calendar: {e}")
            raise

        return updated_count

    def full_sync(self, start_date: datetime, end_date: datetime) -> Dict:
        """
        Perform a full sync of activities and workouts
        Returns summary of sync operation
        """
        logger.info(f"Starting full sync for user {self.user.email}")

        # Sync activities
        new_activities, updated_activities = self.sync_activities(start_date, end_date)

        # Sync workouts
        new_workouts, updated_workouts = self.sync_workouts(start_date, end_date)

        # Sync calendar to get scheduled dates for workouts
        scheduled_workouts = self.sync_calendar(start_date, end_date)

        # Calculate statistics for the synced period
        from .crud import calculate_and_store_statistics

        # Calculate weekly stats
        current = start_date
        while current < end_date:
            week_end = min(current + timedelta(days=7), end_date)

            # All sports
            calculate_and_store_statistics(
                self.db, self.user.id, 'weekly',
                current, week_end, sport_type=None
            )

            # Per sport
            for sport in [SportType.RUNNING, SportType.CYCLING]:
                calculate_and_store_statistics(
                    self.db, self.user.id, 'weekly',
                    current, week_end, sport_type=sport
                )

            current = week_end

        return {
            'success': True,
            'new_activities': new_activities,
            'updated_activities': updated_activities,
            'new_workouts': new_workouts,
            'updated_workouts': updated_workouts,
            'scheduled_workouts': scheduled_workouts,
            'sync_date': datetime.utcnow().isoformat()
        }
