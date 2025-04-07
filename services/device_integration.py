import logging
from datetime import datetime

from app import db
from models import Device, HealthReading
from services.alerts import check_reading_for_alert

def process_device_reading(device_id, patient_id, reading_type, value, unit, 
                           timestamp=None, value_systolic=None, value_diastolic=None, value_pulse=None):
    """
    Process a reading received from a device
    """
    try:
        # Set timestamp to now if not provided
        if not timestamp:
            timestamp = datetime.utcnow()
            
        # Determine if the reading is abnormal
        is_abnormal = check_if_abnormal(reading_type, value, unit, value_systolic, value_diastolic)
        
        # Create the reading
        reading = HealthReading(
            device_id=device_id,
            patient_id=patient_id,
            reading_type=reading_type,
            value=value,
            unit=unit,
            timestamp=timestamp,
            is_abnormal=is_abnormal,
            value_systolic=value_systolic,
            value_diastolic=value_diastolic,
            value_pulse=value_pulse
        )
        
        db.session.add(reading)
        db.session.commit()
        
        # Update device last_synced timestamp
        device = Device.query.get(device_id)
        if device:
            device.last_synced = datetime.utcnow()
            db.session.commit()
        
        # Check if this reading should trigger an alert
        if is_abnormal:
            check_reading_for_alert(reading)
        
        return {
            'success': True,
            'reading_id': reading.id,
            'is_abnormal': is_abnormal
        }
        
    except Exception as e:
        logging.error(f"Error processing device reading: {str(e)}")
        return {
            'success': False,
            'message': str(e)
        }

def sync_devices(patient_id):
    """
    Simulate syncing all devices for a patient
    In a real implementation, this would communicate with actual devices
    """
    try:
        # Get all active devices for the patient
        devices = Device.query.filter_by(patient_id=patient_id, is_active=True).all()
        
        if not devices:
            return {
                'success': False,
                'message': 'No active devices found for this patient'
            }
        
        # Simulate getting readings from each device
        synced_count = 0
        for device in devices:
            # Update last_synced timestamp
            device.last_synced = datetime.utcnow()
            synced_count += 1
        
        db.session.commit()
        
        return {
            'success': True,
            'synced_devices': synced_count,
            'message': f'Successfully synced {synced_count} devices'
        }
        
    except Exception as e:
        logging.error(f"Error syncing devices: {str(e)}")
        return {
            'success': False,
            'message': str(e)
        }

def check_if_abnormal(reading_type, value, unit, value_systolic=None, value_diastolic=None):
    """
    Check if a reading is abnormal based on standard thresholds
    """
    if reading_type == 'blood_glucose':
        # Convert to mg/dL if needed
        if unit == 'mmol/L':
            value = value * 18  # Conversion factor from mmol/L to mg/dL
            unit = 'mg/dL'
        
        # Abnormal thresholds for blood glucose
        if value < 70:  # Hypoglycemia
            return True
        elif value > 180:  # Hyperglycemia
            return True
        
    elif reading_type == 'blood_pressure' and value_systolic and value_diastolic:
        # Abnormal thresholds for blood pressure
        if value_systolic >= 140 or value_diastolic >= 90:  # Hypertension
            return True
        elif value_systolic < 90 or value_diastolic < 60:  # Hypotension
            return True
    
    # Add more reading types as needed
    
    return False

def register_device(patient_id, device_type, device_id, manufacturer=None, model=None):
    """
    Register a new device for a patient
    """
    try:
        # Check if device already exists
        existing_device = Device.query.filter_by(device_id=device_id).first()
        if existing_device:
            return {
                'success': False,
                'message': 'Device already registered'
            }
        
        # Create new device
        device = Device(
            patient_id=patient_id,
            device_type=device_type,
            device_id=device_id,
            manufacturer=manufacturer,
            model=model,
            is_active=True
        )
        
        db.session.add(device)
        db.session.commit()
        
        return {
            'success': True,
            'device_id': device.id,
            'message': 'Device registered successfully'
        }
        
    except Exception as e:
        logging.error(f"Error registering device: {str(e)}")
        return {
            'success': False,
            'message': str(e)
        }
