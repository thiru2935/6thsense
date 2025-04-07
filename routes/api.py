from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
import json
from datetime import datetime, timedelta

from app import db
from models import (User, PatientProfile, HealthReading, Device, 
                    Alert, Medication, MedicationLog, Prediction)
from services.prediction import predict_risk_score
from services.device_integration import process_device_reading
from services.alerts import generate_alert

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/health')
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})

@api_bp.route('/patient/<int:patient_id>/readings', methods=['GET'])
@login_required
def get_patient_readings(patient_id):
    # Check authorization
    if current_user.is_patient():
        patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
        if patient.id != patient_id:
            return jsonify({"error": "Unauthorized"}), 403
    elif current_user.is_provider():
        # Check if provider is associated with this patient
        provider = current_user.provider_profile
        if not any(assoc.patient_id == patient_id for assoc in provider.patients):
            return jsonify({"error": "Unauthorized"}), 403
    else:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Get query parameters
    reading_type = request.args.get('type')
    days = int(request.args.get('days', 30))
    since_date = datetime.utcnow() - timedelta(days=days)
    
    # Build query
    query = HealthReading.query.filter_by(patient_id=patient_id).filter(HealthReading.timestamp >= since_date)
    
    if reading_type:
        query = query.filter_by(reading_type=reading_type)
    
    readings = query.order_by(HealthReading.timestamp).all()
    
    # Format the readings for JSON response
    result = []
    for reading in readings:
        reading_data = {
            "id": reading.id,
            "reading_type": reading.reading_type,
            "value": reading.value,
            "unit": reading.unit,
            "timestamp": reading.timestamp.isoformat(),
            "is_abnormal": reading.is_abnormal
        }
        
        # Add blood pressure specific fields if present
        if reading.reading_type == 'blood_pressure' and reading.value_systolic and reading.value_diastolic:
            reading_data["systolic"] = reading.value_systolic
            reading_data["diastolic"] = reading.value_diastolic
            
        if reading.value_pulse:
            reading_data["pulse"] = reading.value_pulse
            
        result.append(reading_data)
    
    return jsonify(result)

@api_bp.route('/patient/<int:patient_id>/risk_score', methods=['GET'])
@login_required
def get_risk_score(patient_id):
    # Check authorization (similar to above)
    if current_user.is_patient():
        patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
        if patient.id != patient_id:
            return jsonify({"error": "Unauthorized"}), 403
    elif current_user.is_provider():
        # Check if provider is associated with this patient
        provider = current_user.provider_profile
        if not any(assoc.patient_id == patient_id for assoc in provider.patients):
            return jsonify({"error": "Unauthorized"}), 403
    else:
        return jsonify({"error": "Unauthorized"}), 403
    
    risk_score = predict_risk_score(patient_id)
    
    return jsonify({
        "patient_id": patient_id,
        "risk_score": risk_score,
        "timestamp": datetime.utcnow().isoformat()
    })

@api_bp.route('/device/reading', methods=['POST'])
def receive_device_reading():
    # This endpoint would typically be called by IoT devices or wearables
    # with proper authentication, which we'll simulate for this demo
    
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['device_id', 'reading_type', 'value', 'unit']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Find the device
        device = Device.query.filter_by(device_id=data['device_id']).first()
        if not device:
            return jsonify({"error": "Device not found"}), 404
        
        # Process the reading
        result = process_device_reading(
            device_id=device.id,
            patient_id=device.patient_id,
            reading_type=data['reading_type'],
            value=data['value'],
            unit=data['unit'],
            timestamp=datetime.fromisoformat(data.get('timestamp', datetime.utcnow().isoformat())),
            value_systolic=data.get('systolic'),
            value_diastolic=data.get('diastolic'),
            value_pulse=data.get('pulse')
        )
        
        if result['success']:
            return jsonify({"status": "success", "reading_id": result['reading_id']})
        else:
            return jsonify({"error": result['message']}), 400
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/patient/<int:patient_id>/alerts', methods=['GET'])
@login_required
def get_patient_alerts(patient_id):
    # Check authorization (similar to above)
    if current_user.is_patient():
        patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
        if patient.id != patient_id:
            return jsonify({"error": "Unauthorized"}), 403
    elif current_user.is_provider():
        provider = current_user.provider_profile
        if not any(assoc.patient_id == patient_id for assoc in provider.patients):
            return jsonify({"error": "Unauthorized"}), 403
    else:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Get query parameters
    show_resolved = request.args.get('show_resolved', 'false').lower() == 'true'
    
    # Build query
    query = Alert.query.filter_by(patient_id=patient_id)
    
    if not show_resolved:
        query = query.filter_by(is_resolved=False)
    
    alerts = query.order_by(Alert.timestamp.desc()).all()
    
    # Format the alerts for JSON response
    result = []
    for alert in alerts:
        resolver = User.query.get(alert.resolved_by) if alert.resolved_by else None
        
        alert_data = {
            "id": alert.id,
            "alert_type": alert.alert_type,
            "message": alert.message,
            "severity": alert.severity,
            "timestamp": alert.timestamp.isoformat(),
            "is_resolved": alert.is_resolved
        }
        
        if alert.is_resolved and alert.resolved_at and resolver:
            alert_data["resolved_at"] = alert.resolved_at.isoformat()
            alert_data["resolved_by"] = resolver.get_full_name()
            
        result.append(alert_data)
    
    return jsonify(result)

@api_bp.route('/alert', methods=['POST'])
@login_required
def create_alert():
    if not current_user.is_provider():
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.json
    
    # Validate required fields
    required_fields = ['patient_id', 'alert_type', 'message', 'severity']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    # Check if provider is associated with this patient
    provider = current_user.provider_profile
    if not any(assoc.patient_id == data['patient_id'] for assoc in provider.patients):
        return jsonify({"error": "Unauthorized to create alerts for this patient"}), 403
    
    # Create the alert
    result = generate_alert(
        patient_id=data['patient_id'],
        alert_type=data['alert_type'],
        message=data['message'],
        severity=data['severity']
    )
    
    if result['success']:
        return jsonify({"status": "success", "alert_id": result['alert_id']})
    else:
        return jsonify({"error": result['message']}), 400
