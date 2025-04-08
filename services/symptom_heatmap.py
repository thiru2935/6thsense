"""
Symptom Severity Heatmap Service
This service manages the tracking and visualization of symptom severity
"""

import logging
import json
from datetime import datetime, timedelta
from flask import current_app
from app import db
from models import PatientProfile, SymptomHeatmapEntry


# Standard symptom types for structured tracking
COMMON_SYMPTOMS = {
    "diabetes": [
        "fatigue", "increased_thirst", "frequent_urination", 
        "blurred_vision", "slow_healing", "numbness_tingling", 
        "headache", "dry_mouth"
    ],
    "hypertension": [
        "headache", "shortness_of_breath", "chest_pain", 
        "dizziness", "nosebleed", "vision_changes", 
        "fatigue", "irregular_heartbeat"
    ],
    "cardiovascular": [
        "chest_pain", "shortness_of_breath", "irregular_heartbeat", 
        "fatigue", "dizziness", "swelling", "nausea", "cold_sweat"
    ],
    "general": [
        "pain", "fatigue", "nausea", "headache", 
        "fever", "dizziness", "anxiety", "mood_changes"
    ]
}

# Body locations for mapping symptoms
BODY_LOCATIONS = [
    "head", "neck", "chest", "abdomen", "back_upper", "back_lower", 
    "arm_left", "arm_right", "hand_left", "hand_right", 
    "leg_left", "leg_right", "foot_left", "foot_right", 
    "shoulder_left", "shoulder_right", "hip_left", "hip_right"
]


def add_symptom_entry(patient_id, symptom_type, severity, body_location=None, notes=None):
    """
    Add a new symptom severity entry
    
    Args:
        patient_id: ID of the patient
        symptom_type: Type of symptom (e.g., "fatigue", "pain")
        severity: Severity rating (0-10)
        body_location: Optional body location
        notes: Optional notes about the symptom
        
    Returns:
        Dictionary with the result of the operation
    """
    try:
        # Validate inputs
        severity = max(0, min(10, int(severity)))
        
        if body_location and body_location not in BODY_LOCATIONS:
            body_location = None
        
        # Generate color based on severity
        if severity <= 3:
            color_code = "#4CAF50"  # Green
        elif severity <= 5:
            color_code = "#FFC107"  # Yellow/Amber
        elif severity <= 7:
            color_code = "#FF9800"  # Orange
        else:
            color_code = "#F44336"  # Red
        
        # Create symptom entry
        symptom_entry = SymptomHeatmapEntry(
            patient_id=patient_id,
            symptom_type=symptom_type,
            severity=severity,
            body_location=body_location,
            color_code=color_code,
            reported_at=datetime.utcnow(),
            notes=notes
        )
        db.session.add(symptom_entry)
        db.session.commit()
        
        return {
            "success": True,
            "entry": {
                "id": symptom_entry.id,
                "symptom_type": symptom_type,
                "severity": severity,
                "severity_text": symptom_entry.severity_text,
                "body_location": body_location,
                "color_code": color_code,
                "reported_at": symptom_entry.reported_at.strftime("%Y-%m-%d %H:%M")
            }
        }
        
    except Exception as e:
        current_app.logger.error(f"Error adding symptom entry: {str(e)}")
        return {"error": f"Failed to add symptom entry: {str(e)}"}


def get_symptom_heatmap(patient_id, condition=None, days=30):
    """
    Get symptom heatmap data for visualization
    
    Args:
        patient_id: ID of the patient
        condition: Optional condition filter (diabetes, hypertension, cardiovascular)
        days: Number of days of history to include
        
    Returns:
        Dictionary with heatmap data
    """
    try:
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Query symptom entries
        query = SymptomHeatmapEntry.query.filter_by(
            patient_id=patient_id
        ).filter(
            SymptomHeatmapEntry.reported_at >= start_date
        )
        
        # Apply condition filter if provided
        if condition and condition in COMMON_SYMPTOMS:
            symptoms_for_condition = COMMON_SYMPTOMS[condition]
            query = query.filter(SymptomHeatmapEntry.symptom_type.in_(symptoms_for_condition))
        
        symptom_entries = query.order_by(SymptomHeatmapEntry.reported_at.desc()).all()
        
        # Group entries by body location and symptom type
        body_map = {}
        for location in BODY_LOCATIONS:
            body_map[location] = {"entries": [], "avg_severity": 0, "max_severity": 0}
        
        symptom_map = {}
        
        for entry in symptom_entries:
            # Add to body location map
            if entry.body_location:
                body_map[entry.body_location]["entries"].append({
                    "id": entry.id,
                    "symptom_type": entry.symptom_type,
                    "severity": entry.severity,
                    "severity_text": entry.severity_text,
                    "color_code": entry.color_code,
                    "reported_at": entry.reported_at.strftime("%Y-%m-%d %H:%M"),
                    "notes": entry.notes
                })
            
            # Add to symptom type map
            if entry.symptom_type not in symptom_map:
                symptom_map[entry.symptom_type] = []
                
            symptom_map[entry.symptom_type].append({
                "id": entry.id,
                "severity": entry.severity,
                "body_location": entry.body_location,
                "reported_at": entry.reported_at.strftime("%Y-%m-%d %H:%M"),
                "color_code": entry.color_code
            })
        
        # Calculate averages and max severity for body locations
        for location, data in body_map.items():
            if data["entries"]:
                severities = [e["severity"] for e in data["entries"]]
                data["avg_severity"] = sum(severities) / len(severities)
                data["max_severity"] = max(severities)
                
                # Get most recent color for this location
                data["color_code"] = data["entries"][0]["color_code"]
        
        # Calculate trend data for each symptom type
        symptom_trends = {}
        for symptom_type, entries in symptom_map.items():
            if entries:
                # Sort by date reported
                sorted_entries = sorted(entries, key=lambda e: e["reported_at"])
                
                # Get values for trend graph
                dates = [e["reported_at"] for e in sorted_entries]
                severities = [e["severity"] for e in sorted_entries]
                
                # Calculate current severity (most recent) and average
                current = severities[-1] if severities else 0
                average = sum(severities) / len(severities) if severities else 0
                
                symptom_trends[symptom_type] = {
                    "dates": dates,
                    "severities": severities,
                    "current": current,
                    "average": average,
                    "count": len(entries)
                }
        
        # Get common symptoms for the specified condition (or general if not specified)
        condition_key = condition if condition and condition in COMMON_SYMPTOMS else "general"
        common_symptoms = COMMON_SYMPTOMS[condition_key]
        
        return {
            "success": True,
            "total_entries": len(symptom_entries),
            "body_map": body_map,
            "symptom_trends": symptom_trends,
            "common_symptoms": common_symptoms,
            "all_symptoms": list(symptom_map.keys()),
            "body_locations": BODY_LOCATIONS
        }
        
    except Exception as e:
        current_app.logger.error(f"Error getting symptom heatmap: {str(e)}")
        return {"error": f"Failed to get symptom heatmap: {str(e)}"}


def get_symptom_history(patient_id, symptom_type=None, body_location=None, days=30):
    """
    Get detailed history of symptom entries for a specific symptom or body location
    
    Args:
        patient_id: ID of the patient
        symptom_type: Optional specific symptom type to filter
        body_location: Optional specific body location to filter
        days: Number of days of history to include
        
    Returns:
        Dictionary with symptom history
    """
    try:
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Build query
        query = SymptomHeatmapEntry.query.filter_by(
            patient_id=patient_id
        ).filter(
            SymptomHeatmapEntry.reported_at >= start_date
        )
        
        # Apply symptom type filter if provided
        if symptom_type:
            query = query.filter_by(symptom_type=symptom_type)
            
        # Apply body location filter if provided
        if body_location and body_location in BODY_LOCATIONS:
            query = query.filter_by(body_location=body_location)
        
        # Get entries sorted by date
        entries = query.order_by(SymptomHeatmapEntry.reported_at).all()
        
        # Format entries
        formatted_entries = [
            {
                "id": entry.id,
                "symptom_type": entry.symptom_type,
                "severity": entry.severity,
                "severity_text": entry.severity_text,
                "body_location": entry.body_location,
                "color_code": entry.color_code,
                "notes": entry.notes,
                "date": entry.reported_at.strftime("%Y-%m-%d"),
                "time": entry.reported_at.strftime("%H:%M")
            } for entry in entries
        ]
        
        # Calculate trend data
        dates = [entry.reported_at.strftime("%Y-%m-%d") for entry in entries]
        severities = [entry.severity for entry in entries]
        
        # Group by date for chart display
        daily_data = {}
        for entry in entries:
            day = entry.reported_at.strftime("%Y-%m-%d")
            if day not in daily_data:
                daily_data[day] = []
                
            daily_data[day].append({
                "severity": entry.severity,
                "time": entry.reported_at.strftime("%H:%M")
            })
        
        # Calculate daily averages
        daily_averages = [
            {
                "date": day,
                "average": sum(e["severity"] for e in day_entries) / len(day_entries)
            } for day, day_entries in daily_data.items()
        ]
        
        # Sort by date
        daily_averages.sort(key=lambda x: x["date"])
        
        return {
            "success": True,
            "entries": formatted_entries,
            "entry_count": len(entries),
            "trend_data": {
                "dates": dates,
                "severities": severities
            },
            "daily_averages": daily_averages,
            "filter": {
                "symptom_type": symptom_type,
                "body_location": body_location
            }
        }
        
    except Exception as e:
        current_app.logger.error(f"Error getting symptom history: {str(e)}")
        return {"error": f"Failed to get symptom history: {str(e)}"}


def get_symptom_summary(patient_id, days=30):
    """
    Get a summary of overall symptom trends and statistics
    
    Args:
        patient_id: ID of the patient
        days: Number of days of history to include
        
    Returns:
        Dictionary with summary statistics
    """
    try:
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get all entries in time period
        entries = SymptomHeatmapEntry.query.filter_by(
            patient_id=patient_id
        ).filter(
            SymptomHeatmapEntry.reported_at >= start_date
        ).all()
        
        if not entries:
            return {
                "success": True,
                "entry_count": 0,
                "message": "No symptom data available for this period"
            }
        
        # Count entries by symptom type
        symptom_counts = {}
        for entry in entries:
            if entry.symptom_type not in symptom_counts:
                symptom_counts[entry.symptom_type] = {
                    "count": 0,
                    "total_severity": 0,
                    "max_severity": 0
                }
                
            symptom_counts[entry.symptom_type]["count"] += 1
            symptom_counts[entry.symptom_type]["total_severity"] += entry.severity
            symptom_counts[entry.symptom_type]["max_severity"] = max(
                symptom_counts[entry.symptom_type]["max_severity"], 
                entry.severity
            )
        
        # Calculate average severity by symptom
        for symptom, data in symptom_counts.items():
            data["avg_severity"] = data["total_severity"] / data["count"]
        
        # Find most reported and most severe symptoms
        most_reported = max(symptom_counts.items(), key=lambda x: x[1]["count"])[0]
        most_severe = max(symptom_counts.items(), key=lambda x: x[1]["max_severity"])[0]
        
        # Group by date to track daily reporting
        daily_entries = {}
        for entry in entries:
            day = entry.reported_at.strftime("%Y-%m-%d")
            if day not in daily_entries:
                daily_entries[day] = []
                
            daily_entries[day].append({
                "symptom_type": entry.symptom_type,
                "severity": entry.severity
            })
        
        # Calculate daily severity averages
        daily_averages = []
        for day, day_entries in daily_entries.items():
            daily_averages.append({
                "date": day,
                "average": sum(e["severity"] for e in day_entries) / len(day_entries),
                "count": len(day_entries)
            })
            
        # Sort by date
        daily_averages.sort(key=lambda x: x["date"])
        
        # Calculate overall statistics
        all_severities = [entry.severity for entry in entries]
        overall_severity = sum(all_severities) / len(all_severities)
        
        # Calculate trend (improving, worsening, stable)
        if len(daily_averages) >= 2:
            # Compare first and last week averages
            first_week = daily_averages[:min(7, len(daily_averages)//2)]
            last_week = daily_averages[-min(7, len(daily_averages)//2):]
            
            first_week_avg = sum(day["average"] for day in first_week) / len(first_week)
            last_week_avg = sum(day["average"] for day in last_week) / len(last_week)
            
            if last_week_avg < first_week_avg - 1:
                trend = "improving"
            elif last_week_avg > first_week_avg + 1:
                trend = "worsening"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
        
        return {
            "success": True,
            "entry_count": len(entries),
            "unique_symptoms": len(symptom_counts),
            "days_reported": len(daily_entries),
            "coverage_percentage": int((len(daily_entries) / days) * 100),
            "most_reported_symptom": most_reported,
            "most_severe_symptom": most_severe,
            "overall_severity_average": overall_severity,
            "symptom_statistics": symptom_counts,
            "daily_averages": daily_averages,
            "trend": trend
        }
        
    except Exception as e:
        current_app.logger.error(f"Error getting symptom summary: {str(e)}")
        return {"error": f"Failed to get symptom summary: {str(e)}"}