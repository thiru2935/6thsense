import logging
from datetime import datetime

from app import db
from models import Alert, HealthReading

def generate_alert(patient_id, alert_type, message, severity):
    """
    Generate a new alert for a patient
    """
    try:
        alert = Alert(
            patient_id=patient_id,
            alert_type=alert_type,
            message=message,
            severity=severity,
            is_resolved=False
        )
        
        db.session.add(alert)
        db.session.commit()
        
        # In a real application, this would also trigger notifications
        # via SMS, email, app push notification, etc.
        
        return {
            'success': True,
            'alert_id': alert.id
        }
        
    except Exception as e:
        logging.error(f"Error generating alert: {str(e)}")
        return {
            'success': False,
            'message': str(e)
        }

def check_reading_for_alert(reading):
    """
    Check if a specific reading should trigger an alert
    """
    try:
        alert_type = None
        message = None
        severity = None
        
        # Check for abnormal blood glucose
        if reading.reading_type == 'blood_glucose':
            if reading.unit == 'mmol/L':
                value = reading.value * 18  # Convert to mg/dL
            else:
                value = reading.value
                
            if value < 54:  # Severe hypoglycemia
                alert_type = 'severe_hypoglycemia'
                message = f'URGENT: Very low blood glucose detected ({reading.value} {reading.unit})'
                severity = 'high'
            elif value < 70:  # Hypoglycemia
                alert_type = 'hypoglycemia'
                message = f'Low blood glucose detected ({reading.value} {reading.unit})'
                severity = 'medium'
            elif value > 300:  # Severe hyperglycemia
                alert_type = 'severe_hyperglycemia'
                message = f'URGENT: Very high blood glucose detected ({reading.value} {reading.unit})'
                severity = 'high'
            elif value > 180:  # Hyperglycemia
                alert_type = 'hyperglycemia'
                message = f'High blood glucose detected ({reading.value} {reading.unit})'
                severity = 'medium'
        
        # Check for abnormal blood pressure
        elif reading.reading_type == 'blood_pressure' and reading.value_systolic and reading.value_diastolic:
            if reading.value_systolic >= 180 or reading.value_diastolic >= 120:  # Hypertensive crisis
                alert_type = 'hypertensive_crisis'
                message = f'URGENT: Very high blood pressure detected ({reading.value_systolic}/{reading.value_diastolic} mmHg)'
                severity = 'high'
            elif reading.value_systolic >= 140 or reading.value_diastolic >= 90:  # Hypertension
                alert_type = 'hypertension'
                message = f'High blood pressure detected ({reading.value_systolic}/{reading.value_diastolic} mmHg)'
                severity = 'medium'
            elif reading.value_systolic < 90 or reading.value_diastolic < 60:  # Hypotension
                alert_type = 'hypotension'
                message = f'Low blood pressure detected ({reading.value_systolic}/{reading.value_diastolic} mmHg)'
                severity = 'medium'
        
        # Generate alert if needed
        if alert_type and message and severity:
            generate_alert(
                patient_id=reading.patient_id,
                alert_type=alert_type,
                message=message,
                severity=severity
            )
            return True
            
        return False
        
    except Exception as e:
        logging.error(f"Error checking reading for alert: {str(e)}")
        return False

def check_readings_for_alerts(patient_id):
    """
    Check recent readings for a patient to see if any should trigger alerts
    """
    try:
        # Get recent unprocessed readings
        readings = HealthReading.query.filter_by(
            patient_id=patient_id,
            is_abnormal=True
        ).order_by(HealthReading.timestamp.desc()).limit(10).all()
        
        alert_count = 0
        for reading in readings:
            if check_reading_for_alert(reading):
                alert_count += 1
        
        return {
            'success': True,
            'alert_count': alert_count
        }
        
    except Exception as e:
        logging.error(f"Error checking readings for alerts: {str(e)}")
        return {
            'success': False,
            'message': str(e)
        }
