from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import current_user, login_required
from datetime import datetime, timedelta

from app import db
from models import (User, PatientProfile, ProviderProfile, ProviderPatientAssociation, 
                    Device, HealthReading, Medication, Alert, Prediction)
from services.prediction import predict_risk_score, get_patient_risk_factors

provider_bp = Blueprint('provider', __name__, url_prefix='/provider')

@provider_bp.before_request
def check_provider():
    if not current_user.is_authenticated or not current_user.is_provider():
        flash('Access denied. You must be logged in as a healthcare provider.', 'danger')
        return redirect(url_for('auth.login'))

@provider_bp.route('/dashboard')
@login_required
def dashboard():
    # Get provider profile
    provider = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    
    # Get all patients associated with this provider
    associations = ProviderPatientAssociation.query.filter_by(provider_id=provider.id).all()
    patient_ids = [assoc.patient_id for assoc in associations]
    
    # Get patients with high risk scores
    high_risk_patients = []
    for patient_id in patient_ids:
        patient = PatientProfile.query.get(patient_id)
        risk_score = predict_risk_score(patient_id)
        
        if risk_score > 70:  # Arbitrary threshold for high risk
            high_risk_patients.append({
                'patient': patient,
                'user': User.query.get(patient.user_id),
                'risk_score': risk_score
            })
    
    # Get recent unresolved alerts for all patients
    recent_alerts = Alert.query.filter(
        Alert.patient_id.in_(patient_ids),
        Alert.is_resolved == False
    ).order_by(Alert.timestamp.desc()).limit(10).all()
    
    # Get count summary of patients by diagnosis
    diagnosis_summary = db.session.query(
        PatientProfile.diagnosis, db.func.count(PatientProfile.id)
    ).filter(
        PatientProfile.id.in_(patient_ids)
    ).group_by(PatientProfile.diagnosis).all()
    
    return render_template('provider/dashboard.html',
                           provider=provider,
                           high_risk_patients=high_risk_patients,
                           alerts=recent_alerts,
                           patient_count=len(patient_ids),
                           diagnosis_summary=diagnosis_summary)

@provider_bp.route('/patients')
@login_required
def patients():
    provider = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    
    # Get all patients associated with this provider
    associations = ProviderPatientAssociation.query.filter_by(provider_id=provider.id).all()
    
    patients_data = []
    for assoc in associations:
        patient = PatientProfile.query.get(assoc.patient_id)
        user = User.query.get(patient.user_id)
        risk_score = predict_risk_score(patient.id)
        
        # Get the latest reading of each type
        latest_glucose = HealthReading.query.filter_by(
            patient_id=patient.id, reading_type='blood_glucose'
        ).order_by(HealthReading.timestamp.desc()).first()
        
        latest_bp = HealthReading.query.filter_by(
            patient_id=patient.id, reading_type='blood_pressure'
        ).order_by(HealthReading.timestamp.desc()).first()
        
        patients_data.append({
            'patient': patient,
            'user': user,
            'risk_score': risk_score,
            'latest_glucose': latest_glucose,
            'latest_bp': latest_bp
        })
    
    return render_template('provider/patients.html', 
                           provider=provider, 
                           patients_data=patients_data)

@provider_bp.route('/patient/<int:patient_id>')
@login_required
def patient_detail(patient_id):
    provider = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    
    # Check if this provider is associated with this patient
    assoc = ProviderPatientAssociation.query.filter_by(
        provider_id=provider.id, patient_id=patient_id
    ).first()
    
    if not assoc:
        flash('You are not authorized to view this patient', 'danger')
        return redirect(url_for('provider.patients'))
    
    patient = PatientProfile.query.get_or_404(patient_id)
    user = User.query.get(patient.user_id)
    
    # Get risk score and factors
    risk_score = predict_risk_score(patient_id)
    risk_factors = get_patient_risk_factors(patient_id)
    
    # Get recent readings
    readings = HealthReading.query.filter_by(patient_id=patient_id).order_by(HealthReading.timestamp.desc()).limit(20).all()
    
    # Get readings for charts (last 30 days)
    since_date = datetime.utcnow() - timedelta(days=30)
    
    glucose_readings = HealthReading.query.filter_by(
        patient_id=patient_id, reading_type='blood_glucose'
    ).filter(HealthReading.timestamp >= since_date).order_by(HealthReading.timestamp).all()
    
    bp_readings = HealthReading.query.filter_by(
        patient_id=patient_id, reading_type='blood_pressure'
    ).filter(HealthReading.timestamp >= since_date).order_by(HealthReading.timestamp).all()
    
    # Get medications
    medications = Medication.query.filter_by(patient_id=patient_id).order_by(Medication.is_active.desc()).all()
    
    # Get unresolved alerts
    alerts = Alert.query.filter_by(patient_id=patient_id, is_resolved=False).order_by(Alert.timestamp.desc()).all()
    
    # Get devices
    devices = Device.query.filter_by(patient_id=patient_id).all()
    
    return render_template('provider/patient_detail.html',
                           provider=provider,
                           patient=patient,
                           user=user,
                           risk_score=risk_score,
                           risk_factors=risk_factors,
                           readings=readings,
                           glucose_readings=glucose_readings,
                           bp_readings=bp_readings,
                           medications=medications,
                           alerts=alerts,
                           devices=devices)

@provider_bp.route('/add_patient', methods=['POST'])
@login_required
def add_patient():
    provider = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    
    patient_email = request.form.get('patient_email')
    patient_user = User.query.filter_by(email=patient_email).first()
    
    if not patient_user or not patient_user.is_patient():
        flash('Patient not found with that email address', 'danger')
        return redirect(url_for('provider.patients'))
    
    patient = PatientProfile.query.filter_by(user_id=patient_user.id).first()
    
    # Check if already associated
    existing = ProviderPatientAssociation.query.filter_by(
        provider_id=provider.id, patient_id=patient.id
    ).first()
    
    if existing:
        flash('This patient is already in your care', 'warning')
        return redirect(url_for('provider.patients'))
    
    # Create association
    association = ProviderPatientAssociation(provider_id=provider.id, patient_id=patient.id)
    db.session.add(association)
    db.session.commit()
    
    flash(f'Patient {patient_user.get_full_name()} added to your care', 'success')
    return redirect(url_for('provider.patients'))

@provider_bp.route('/resolve_alert/<int:alert_id>', methods=['POST'])
@login_required
def resolve_alert(alert_id):
    provider = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    alert = Alert.query.get_or_404(alert_id)
    
    # Check if provider is associated with the patient
    assoc = ProviderPatientAssociation.query.filter_by(
        provider_id=provider.id, patient_id=alert.patient_id
    ).first()
    
    if not assoc:
        flash('You are not authorized to modify this alert', 'danger')
        return redirect(url_for('provider.patients'))
    
    alert.is_resolved = True
    alert.resolved_at = datetime.utcnow()
    alert.resolved_by = current_user.id
    db.session.commit()
    
    flash('Alert marked as resolved', 'success')
    
    # Redirect back to the patient detail page if we have a patient_id in the form
    patient_id = request.form.get('patient_id')
    if patient_id:
        return redirect(url_for('provider.patient_detail', patient_id=patient_id))
    
    return redirect(url_for('provider.dashboard'))

@provider_bp.route('/add_medication/<int:patient_id>', methods=['POST'])
@login_required
def add_medication(patient_id):
    provider = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    
    # Check if provider is associated with the patient
    assoc = ProviderPatientAssociation.query.filter_by(
        provider_id=provider.id, patient_id=patient_id
    ).first()
    
    if not assoc:
        flash('You are not authorized to add medications for this patient', 'danger')
        return redirect(url_for('provider.patients'))
    
    medication = Medication(
        patient_id=patient_id,
        name=request.form.get('name'),
        dosage=request.form.get('dosage'),
        frequency=request.form.get('frequency'),
        start_date=datetime.strptime(request.form.get('start_date'), '%Y-%m-%d') if request.form.get('start_date') else datetime.utcnow(),
        end_date=datetime.strptime(request.form.get('end_date'), '%Y-%m-%d') if request.form.get('end_date') else None,
        instructions=request.form.get('instructions'),
        is_active=True
    )
    
    db.session.add(medication)
    db.session.commit()
    
    flash('Medication added successfully', 'success')
    return redirect(url_for('provider.patient_detail', patient_id=patient_id))

@provider_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    provider = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    
    if request.method == 'POST':
        # Update user info
        current_user.first_name = request.form.get('first_name')
        current_user.last_name = request.form.get('last_name')
        
        # Update provider profile
        provider.specialty = request.form.get('specialty')
        provider.license_number = request.form.get('license_number')
        provider.hospital_affiliation = request.form.get('hospital_affiliation')
        provider.contact_number = request.form.get('contact_number')
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('provider.profile'))
    
    return render_template('provider/profile.html', provider=provider)
