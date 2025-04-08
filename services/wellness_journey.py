"""
Wellness Journey and Achievements Service
This service manages the wellness journey tracking, badges, and milestone achievements
"""

import json
import logging
from datetime import datetime, timedelta
from flask import current_app
from app import db
from models import (
    PatientProfile, 
    WellnessJourney, 
    WellnessBadge,
    MoodEntry,
    HealthReading,
    Medication
)

# Badge types and associated icons
BADGE_TYPES = {
    "consistent_readings": {
        "name": "Health Tracker",
        "description": "Consistently logging health readings",
        "icon_path": "/static/icons/health_tracker_badge.svg",
        "levels": [7, 30, 90]  # Days of consistent tracking
    },
    "medication_adherence": {
        "name": "Medication Champion",
        "description": "Maintaining excellent medication adherence",
        "icon_path": "/static/icons/medication_badge.svg",
        "levels": [75, 90, 100]  # Percentage of adherence
    },
    "exercise_goals": {
        "name": "Active Achiever",
        "description": "Meeting physical activity goals",
        "icon_path": "/static/icons/exercise_badge.svg",
        "levels": [5, 15, 30]  # Exercise sessions completed
    },
    "glucose_control": {
        "name": "Glucose Guardian",
        "description": "Maintaining blood glucose in target range",
        "icon_path": "/static/icons/glucose_badge.svg",
        "levels": [50, 70, 90]  # Percentage of readings in range
    },
    "blood_pressure_control": {
        "name": "BP Champion",
        "description": "Maintaining blood pressure in target range",
        "icon_path": "/static/icons/bp_badge.svg",
        "levels": [50, 70, 90]  # Percentage of readings in target range
    },
    "mood_tracking": {
        "name": "Mindfulness Master",
        "description": "Consistently tracking emotional wellbeing",
        "icon_path": "/static/icons/mood_badge.svg",
        "levels": [7, 30, 60]  # Days of mood tracking
    }
}


def initialize_wellness_journey(patient_id):
    """
    Initialize or retrieve a patient's wellness journey
    
    Args:
        patient_id: The patient's ID
        
    Returns:
        The WellnessJourney object
    """
    try:
        # Check if journey already exists
        journey = WellnessJourney.query.filter_by(patient_id=patient_id).first()
        
        if not journey:
            # Create new journey
            journey = WellnessJourney(
                patient_id=patient_id,
                total_points=0,
                current_level=1,
                milestone_progress=json.dumps({
                    "consistent_readings": 0,
                    "medication_adherence": 0,
                    "exercise_goals": 0,
                    "mood_tracking": 0
                })
            )
            db.session.add(journey)
            db.session.commit()
            current_app.logger.info(f"Initialized wellness journey for patient {patient_id}")
        
        return journey
    
    except Exception as e:
        current_app.logger.error(f"Error initializing wellness journey: {str(e)}")
        return None


def get_patient_journey_summary(patient_id):
    """
    Get a summary of the patient's wellness journey including badges and progress
    
    Args:
        patient_id: The patient's ID
        
    Returns:
        Dictionary with journey summary
    """
    try:
        journey = initialize_wellness_journey(patient_id)
        if not journey:
            return {"error": "Could not retrieve wellness journey"}
        
        # Get badges
        badges = WellnessBadge.query.filter_by(journey_id=journey.id).all()
        
        # Parse milestone progress
        try:
            milestones = json.loads(journey.milestone_progress)
        except Exception:
            milestones = {}
        
        # Group badges by type and get the highest level for each type
        badge_summary = {}
        for badge in badges:
            if badge.badge_type not in badge_summary or badge.badge_level > badge_summary[badge.badge_type]["level"]:
                badge_summary[badge.badge_type] = {
                    "name": badge.badge_name,
                    "level": badge.badge_level,
                    "level_name": badge.level_name,
                    "description": badge.badge_description,
                    "icon_path": badge.icon_path,
                    "awarded_at": badge.awarded_at.strftime("%Y-%m-%d")
                }
        
        # Calculate next level requirements
        next_level_points = journey.current_level * 100
        progress_to_next = min(100, int((journey.total_points / next_level_points) * 100)) if next_level_points > 0 else 0
        
        return {
            "success": True,
            "journey": {
                "level": journey.current_level,
                "total_points": journey.total_points,
                "next_level_points": next_level_points,
                "progress_to_next": progress_to_next,
                "badges_count": len(badges),
                "badges_by_type": len(badge_summary),
            },
            "badges": list(badge_summary.values()),
            "milestones": milestones,
            "next_milestones": _get_next_milestones(patient_id, milestones)
        }
        
    except Exception as e:
        current_app.logger.error(f"Error getting wellness journey summary: {str(e)}")
        return {"error": f"Failed to get wellness journey: {str(e)}"}


def update_journey_progress(patient_id, actions=None):
    """
    Update a patient's wellness journey based on their recent actions
    
    Args:
        patient_id: The patient's ID
        actions: Dictionary of specific actions to recognize, or None to check all
        
    Returns:
        Dictionary with update results including any new badges
    """
    try:
        journey = initialize_wellness_journey(patient_id)
        if not journey:
            return {"error": "Could not retrieve wellness journey"}
        
        # If no specific actions, check all possible actions
        if not actions:
            actions = {
                "health_reading": True,
                "medication_taken": True,
                "mood_logged": True,
                "questionnaire_completed": True,
                "exercise_logged": True
            }
        
        # Load current milestone progress
        try:
            milestones = json.loads(journey.milestone_progress)
        except Exception:
            milestones = {}
        
        points_earned = 0
        updates = []
        new_badges = []
        
        # Process each type of action
        if actions.get("health_reading"):
            reading_points, reading_updates = _process_health_readings(patient_id, journey, milestones)
            points_earned += reading_points
            updates.extend(reading_updates)
        
        if actions.get("medication_taken"):
            med_points, med_updates, med_badges = _process_medication_adherence(patient_id, journey, milestones)
            points_earned += med_points
            updates.extend(med_updates)
            new_badges.extend(med_badges)
        
        if actions.get("mood_logged"):
            mood_points, mood_updates, mood_badges = _process_mood_tracking(patient_id, journey, milestones)
            points_earned += mood_points
            updates.extend(mood_updates)
            new_badges.extend(mood_badges)
        
        # Update journey with earned points
        if points_earned > 0:
            journey.total_points += points_earned
            
            # Check for level up
            next_level_points = journey.current_level * 100
            if journey.total_points >= next_level_points:
                journey.current_level += 1
                updates.append(f"Leveled up to Wellness Level {journey.current_level}!")
        
        # Save updated milestone progress
        journey.milestone_progress = json.dumps(milestones)
        db.session.commit()
        
        return {
            "success": True,
            "points_earned": points_earned,
            "updates": updates,
            "new_badges": [
                {
                    "name": badge.badge_name,
                    "level": badge.badge_level,
                    "level_name": badge.level_name,
                    "description": badge.badge_description
                } for badge in new_badges
            ],
            "total_points": journey.total_points,
            "current_level": journey.current_level
        }
        
    except Exception as e:
        current_app.logger.error(f"Error updating wellness journey: {str(e)}")
        return {"error": f"Failed to update wellness journey: {str(e)}"}


def _process_health_readings(patient_id, journey, milestones):
    """
    Process health readings to award points and check for badges
    
    Returns:
        Tuple of (points_earned, updates)
    """
    points_earned = 0
    updates = []
    
    # Check for readings within last 24 hours
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_readings = HealthReading.query.filter_by(
        patient_id=patient_id
    ).filter(
        HealthReading.timestamp > yesterday
    ).all()
    
    # Award points for each reading type (but only once per type per day)
    reading_types = set()
    for reading in recent_readings:
        if reading.reading_type not in reading_types:
            reading_types.add(reading.reading_type)
            points_earned += 5
            updates.append(f"5 points for logging {reading.reading_type}")
    
    # Update consistent readings milestone
    if reading_types:
        current_streak = milestones.get("consistent_readings", 0)
        milestones["consistent_readings"] = current_streak + 1
    
    return points_earned, updates


def _process_medication_adherence(patient_id, journey, milestones):
    """
    Process medication adherence to award points and badges
    
    Returns:
        Tuple of (points_earned, updates, new_badges)
    """
    points_earned = 0
    updates = []
    new_badges = []
    
    # Get all medications for this patient
    medications = Medication.query.filter_by(patient_id=patient_id, is_active=True).all()
    
    if not medications:
        return points_earned, updates, new_badges
    
    # Calculate adherence percentage
    total_doses = 0
    taken_doses = 0
    
    for med in medications:
        # Simple calculation - could be more sophisticated based on frequency
        if med.frequency == "daily":
            total_doses += 30  # Last 30 days
        elif med.frequency == "twice_daily":
            total_doses += 60  # Last 30 days
        elif med.frequency == "weekly":
            total_doses += 4  # Last 4 weeks
        
        # Calculate taken doses (simplified for now)
        if med.adherence_rate is not None:
            taken_doses += total_doses * (med.adherence_rate / 100)
    
    if total_doses > 0:
        adherence_percentage = (taken_doses / total_doses) * 100
        
        # Update milestone
        milestones["medication_adherence"] = adherence_percentage
        
        # Award points for good adherence
        if adherence_percentage >= 90:
            points_earned += 10
            updates.append("10 points for excellent medication adherence")
        elif adherence_percentage >= 80:
            points_earned += 5
            updates.append("5 points for good medication adherence")
        
        # Check for medication adherence badges
        badge_type = "medication_adherence"
        badge_levels = BADGE_TYPES[badge_type]["levels"]
        
        for level_idx, threshold in enumerate(badge_levels, 1):
            if adherence_percentage >= threshold:
                # Check if badge already exists
                existing_badge = WellnessBadge.query.filter_by(
                    journey_id=journey.id,
                    badge_type=badge_type,
                    badge_level=level_idx
                ).first()
                
                if not existing_badge:
                    # Create new badge
                    badge = WellnessBadge(
                        journey_id=journey.id,
                        badge_type=badge_type,
                        badge_level=level_idx,
                        badge_name=BADGE_TYPES[badge_type]["name"],
                        badge_description=f"{BADGE_TYPES[badge_type]['description']} ({threshold}%+)",
                        awarded_at=datetime.utcnow(),
                        icon_path=BADGE_TYPES[badge_type]["icon_path"]
                    )
                    db.session.add(badge)
                    new_badges.append(badge)
                    
                    # Award extra points for earning a badge
                    badge_points = level_idx * 20
                    points_earned += badge_points
                    updates.append(f"{badge_points} points for earning the {badge.badge_name} {badge.level_name} badge!")
    
    return points_earned, updates, new_badges


def _process_mood_tracking(patient_id, journey, milestones):
    """
    Process mood tracking to award points and badges
    
    Returns:
        Tuple of (points_earned, updates, new_badges)
    """
    points_earned = 0
    updates = []
    new_badges = []
    
    # Check for streak of daily mood logging
    today = datetime.utcnow().date()
    
    # Count consecutive days of mood entries
    streak = 0
    check_date = today
    
    while True:
        day_entries = MoodEntry.query.filter_by(
            patient_id=patient_id
        ).filter(
            MoodEntry.created_at >= datetime.combine(check_date, datetime.min.time()),
            MoodEntry.created_at < datetime.combine(check_date + timedelta(days=1), datetime.min.time())
        ).first()
        
        if not day_entries:
            break
            
        streak += 1
        check_date -= timedelta(days=1)
    
    # Update milestone
    milestones["mood_tracking"] = streak
    
    # Award points for streak
    if streak > 0:
        # Today's entry
        points_earned += 3
        updates.append("3 points for logging your mood today")
        
        # Bonus for streak
        if streak >= 7:
            streak_points = min(15, streak // 7 * 5)  # 5 points per week, max 15
            points_earned += streak_points
            updates.append(f"{streak_points} points for a {streak}-day mood tracking streak")
    
    # Check for mood tracking badges
    badge_type = "mood_tracking"
    badge_levels = BADGE_TYPES[badge_type]["levels"]
    
    for level_idx, threshold in enumerate(badge_levels, 1):
        if streak >= threshold:
            # Check if badge already exists
            existing_badge = WellnessBadge.query.filter_by(
                journey_id=journey.id,
                badge_type=badge_type,
                badge_level=level_idx
            ).first()
            
            if not existing_badge:
                # Create new badge
                badge = WellnessBadge(
                    journey_id=journey.id,
                    badge_type=badge_type,
                    badge_level=level_idx,
                    badge_name=BADGE_TYPES[badge_type]["name"],
                    badge_description=f"{BADGE_TYPES[badge_type]['description']} ({threshold}+ days)",
                    awarded_at=datetime.utcnow(),
                    icon_path=BADGE_TYPES[badge_type]["icon_path"]
                )
                db.session.add(badge)
                new_badges.append(badge)
                
                # Award extra points for earning a badge
                badge_points = level_idx * 20
                points_earned += badge_points
                updates.append(f"{badge_points} points for earning the {badge.badge_name} {badge.level_name} badge!")
    
    return points_earned, updates, new_badges


def _get_next_milestones(patient_id, current_milestones):
    """
    Calculate the next milestone goals for the patient
    
    Args:
        patient_id: The patient's ID
        current_milestones: Dictionary of current milestone progress
        
    Returns:
        Dictionary of next milestone goals
    """
    next_milestones = {}
    
    # Consistent readings - next 7/30/90 day streak
    current_streak = current_milestones.get("consistent_readings", 0)
    if current_streak < 7:
        next_milestones["consistent_readings"] = {
            "goal": 7,
            "current": current_streak,
            "description": "Log readings for 7 consecutive days",
            "progress": min(100, int((current_streak / 7) * 100))
        }
    elif current_streak < 30:
        next_milestones["consistent_readings"] = {
            "goal": 30,
            "current": current_streak,
            "description": "Log readings for 30 consecutive days",
            "progress": min(100, int((current_streak / 30) * 100))
        }
    elif current_streak < 90:
        next_milestones["consistent_readings"] = {
            "goal": 90,
            "current": current_streak,
            "description": "Log readings for 90 consecutive days",
            "progress": min(100, int((current_streak / 90) * 100))
        }
    
    # Medication adherence - next 75/90/100% adherence
    adherence = current_milestones.get("medication_adherence", 0)
    if adherence < 75:
        next_milestones["medication_adherence"] = {
            "goal": 75,
            "current": adherence,
            "description": "Achieve 75% medication adherence",
            "progress": min(100, int((adherence / 75) * 100))
        }
    elif adherence < 90:
        next_milestones["medication_adherence"] = {
            "goal": 90,
            "current": adherence,
            "description": "Achieve 90% medication adherence",
            "progress": min(100, int((adherence / 90) * 100))
        }
    elif adherence < 100:
        next_milestones["medication_adherence"] = {
            "goal": 100,
            "current": adherence,
            "description": "Achieve 100% medication adherence",
            "progress": min(100, int(adherence))
        }
    
    # Mood tracking - next 7/30/60 day streak
    mood_streak = current_milestones.get("mood_tracking", 0)
    if mood_streak < 7:
        next_milestones["mood_tracking"] = {
            "goal": 7,
            "current": mood_streak,
            "description": "Log your mood for 7 consecutive days",
            "progress": min(100, int((mood_streak / 7) * 100))
        }
    elif mood_streak < 30:
        next_milestones["mood_tracking"] = {
            "goal": 30,
            "current": mood_streak,
            "description": "Log your mood for 30 consecutive days",
            "progress": min(100, int((mood_streak / 30) * 100))
        }
    elif mood_streak < 60:
        next_milestones["mood_tracking"] = {
            "goal": 60,
            "current": mood_streak,
            "description": "Log your mood for 60 consecutive days",
            "progress": min(100, int((mood_streak / 60) * 100))
        }
    
    return next_milestones


def log_mood(patient_id, mood_emoji, mood_value, notes=None):
    """
    Log a patient's mood entry and update wellness journey
    
    Args:
        patient_id: The patient's ID
        mood_emoji: The emoji representing the mood
        mood_value: The numerical value (1-5)
        notes: Optional notes about the mood
        
    Returns:
        Dictionary with result
    """
    try:
        # Validate mood value
        mood_value = max(1, min(5, int(mood_value)))
        
        # Create mood entry
        mood_entry = MoodEntry(
            patient_id=patient_id,
            mood_emoji=mood_emoji,
            mood_value=mood_value,
            notes=notes,
            created_at=datetime.utcnow()
        )
        db.session.add(mood_entry)
        db.session.commit()
        
        # Update wellness journey
        journey_update = update_journey_progress(patient_id, {"mood_logged": True})
        
        return {
            "success": True,
            "mood_entry": {
                "id": mood_entry.id,
                "emoji": mood_emoji,
                "value": mood_value,
                "description": mood_entry.emoji_description,
                "created_at": mood_entry.created_at.strftime("%Y-%m-%d %H:%M")
            },
            "journey_update": journey_update
        }
        
    except Exception as e:
        current_app.logger.error(f"Error logging mood: {str(e)}")
        return {"error": f"Failed to log mood: {str(e)}"}


def get_mood_history(patient_id, days=30):
    """
    Get a patient's mood history for the specified period
    
    Args:
        patient_id: The patient's ID
        days: Number of days of history to retrieve
        
    Returns:
        Dictionary with mood history data
    """
    try:
        start_date = datetime.utcnow() - timedelta(days=days)
        
        mood_entries = MoodEntry.query.filter_by(
            patient_id=patient_id
        ).filter(
            MoodEntry.created_at >= start_date
        ).order_by(
            MoodEntry.created_at
        ).all()
        
        # Group by day
        mood_by_day = {}
        for entry in mood_entries:
            day = entry.created_at.strftime("%Y-%m-%d")
            if day not in mood_by_day:
                mood_by_day[day] = []
            
            mood_by_day[day].append({
                "id": entry.id,
                "emoji": entry.mood_emoji,
                "value": entry.mood_value,
                "description": entry.emoji_description,
                "notes": entry.notes,
                "time": entry.created_at.strftime("%H:%M")
            })
        
        # Calculate daily averages
        daily_averages = []
        for day, entries in mood_by_day.items():
            avg_value = sum(e["value"] for e in entries) / len(entries)
            daily_averages.append({
                "date": day,
                "average": round(avg_value, 1),
                "entries": len(entries)
            })
        
        # Calculate overall stats
        all_values = [entry.mood_value for entry in mood_entries]
        avg_mood = sum(all_values) / len(all_values) if all_values else 0
        most_common = max(set(all_values), key=all_values.count) if all_values else 0
        
        return {
            "success": True,
            "entries_count": len(mood_entries),
            "days_logged": len(mood_by_day),
            "days_coverage": int((len(mood_by_day) / days) * 100) if days > 0 else 0,
            "mood_entries": mood_by_day,
            "daily_averages": daily_averages,
            "stats": {
                "average_mood": round(avg_mood, 1),
                "most_common": most_common
            }
        }
        
    except Exception as e:
        current_app.logger.error(f"Error getting mood history: {str(e)}")
        return {"error": f"Failed to get mood history: {str(e)}"}