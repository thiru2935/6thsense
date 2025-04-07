from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import current_user, login_required
from datetime import datetime, timedelta

from app import db
from models import User, PatientProfile, Device, HealthReading, Medication, MedicationLog, Alert
from services.prediction import predict_risk_score
from services.device_integration import sync_devices
from services.alerts import check_readings_for_alerts

patient_bp = Blueprint('patient', __name__, url_prefix='/patient')

@patient_bp.before_request
def check_patient():
    if not current_user.is_authenticated or not current_user.is_patient():
        flash('Access denied. You must be logged in as a patient.', 'danger')
        return redirect(url_for('auth.login'))

@patient_bp.route('/dashboard')
@login_required
def dashboard():
    # Get patient profile
    patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
    
    # Get recent health readings
    recent_readings = HealthReading.query.filter_by(patient_id=patient.id).order_by(HealthReading.timestamp.desc()).limit(10).all()
    
    # Get active medications
    medications = Medication.query.filter_by(patient_id=patient.id, is_active=True).all()
    
    # Get recent alerts
    alerts = Alert.query.filter_by(patient_id=patient.id, is_resolved=False).order_by(Alert.timestamp.desc()).limit(5).all()
    
    # Calculate risk score
    risk_score = predict_risk_score(patient.id)
    
    # Get reading data for charts
    glucose_readings = HealthReading.query.filter_by(
        patient_id=patient.id, 
        reading_type='blood_glucose'
    ).order_by(HealthReading.timestamp.desc()).limit(30).all()
    
    bp_readings = HealthReading.query.filter_by(
        patient_id=patient.id, 
        reading_type='blood_pressure'
    ).order_by(HealthReading.timestamp.desc()).limit(30).all()
    
    return render_template('patient/dashboard.html',
                           patient=patient,
                           readings=recent_readings,
                           medications=medications,
                           alerts=alerts,
                           risk_score=risk_score,
                           glucose_readings=glucose_readings,
                           bp_readings=bp_readings)

@patient_bp.route('/devices')
@login_required
def devices():
    patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
    devices = Device.query.filter_by(patient_id=patient.id).all()
    return render_template('patient/devices.html', patient=patient, devices=devices)

@patient_bp.route('/sync_devices', methods=['POST'])
@login_required
def sync_patient_devices():
    patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
    
    # Call device integration service
    result = sync_devices(patient.id)
    
    if result['success']:
        # Check if any new readings need alerts
        check_readings_for_alerts(patient.id)
        flash('Devices synced successfully!', 'success')
    else:
        flash(f'Error syncing devices: {result["message"]}', 'danger')
    
    return redirect(url_for('patient.devices'))

@patient_bp.route('/readings')
@login_required
def readings():
    patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
    
    reading_type = request.args.get('type', 'all')
    days = int(request.args.get('days', 30))
    
    since_date = datetime.utcnow() - timedelta(days=days)
    
    # Build the query
    query = HealthReading.query.filter_by(patient_id=patient.id).filter(HealthReading.timestamp >= since_date)
    
    if reading_type != 'all':
        query = query.filter_by(reading_type=reading_type)
    
    readings = query.order_by(HealthReading.timestamp.desc()).all()
    
    return render_template('patient/readings.html', patient=patient, readings=readings, reading_type=reading_type, days=days)

@patient_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
    
    if request.method == 'POST':
        # Update user info
        current_user.first_name = request.form.get('first_name')
        current_user.last_name = request.form.get('last_name')
        
        # Update patient profile
        patient.date_of_birth = datetime.strptime(request.form.get('date_of_birth'), '%Y-%m-%d') if request.form.get('date_of_birth') else None
        patient.gender = request.form.get('gender')
        patient.contact_number = request.form.get('contact_number')
        patient.emergency_contact = request.form.get('emergency_contact')
        patient.address = request.form.get('address')
        patient.preferred_language = request.form.get('preferred_language')
        patient.diagnosis = request.form.get('diagnosis')
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('patient.profile'))
    
    return render_template('patient/profile.html', patient=patient)

@patient_bp.route('/medications')
@login_required
def medications():
    patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
    medications = Medication.query.filter_by(patient_id=patient.id).order_by(Medication.is_active.desc()).all()
    
    return render_template('patient/medications.html', patient=patient, medications=medications)

@patient_bp.route('/log_medication/<int:med_id>', methods=['POST'])
@login_required
def log_medication(med_id):
    patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
    medication = Medication.query.get_or_404(med_id)
    
    if medication.patient_id != patient.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('patient.medications'))
    
    was_taken = request.form.get('was_taken') == 'true'
    notes = request.form.get('notes', '')
    
    log = MedicationLog(
        medication_id=med_id,
        was_taken=was_taken,
        notes=notes,
        taken_at=datetime.utcnow()
    )
    
    db.session.add(log)
    db.session.commit()
    
    flash('Medication log recorded', 'success')
    return redirect(url_for('patient.medications'))

@patient_bp.route('/alerts')
@login_required
def alerts():
    patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
    show_resolved = request.args.get('show_resolved', 'false') == 'true'
    
    query = Alert.query.filter_by(patient_id=patient.id)
    
    if not show_resolved:
        query = query.filter_by(is_resolved=False)
        
    alerts = query.order_by(Alert.timestamp.desc()).all()
    
    return render_template('patient/alerts.html', patient=patient, alerts=alerts, show_resolved=show_resolved)
