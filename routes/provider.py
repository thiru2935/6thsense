from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_login import current_user, login_required
from datetime import datetime, timedelta
import os

from app import db
from models import (User, PatientProfile, ProviderProfile, ProviderPatientAssociation, 
                    Device, HealthReading, Medication, Alert, Prediction, HealthRecord, 
                    RecordConsent, TestAppointment)
from services.prediction import predict_risk_score, get_patient_risk_factors
from services.file_upload import save_uploaded_file, delete_health_record_file, get_file_path
from services.risk_dashboard import get_risk_dashboard_data
from services.symptom_heatmap import get_symptom_heatmap, get_symptom_history, get_symptom_summary
from services.wellness_journey import get_patient_journey_summary, get_mood_history

# Constants needed for symptom heatmap
COMMON_SYMPTOMS = ['chest_pain', 'fatigue', 'headache', 'dizziness', 'nausea', 'shortness_of_breath',
                    'numbness', 'blurred_vision', 'joint_pain', 'excessive_thirst']
                   
BODY_LOCATIONS = ['head', 'chest', 'abdomen', 'upper_limbs', 'lower_limbs', 'back', 'general']

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
    
    # Get all patients data for display
    patients = []
    high_risk_patients = []
    
    for patient_id in patient_ids:
        patient = PatientProfile.query.get(patient_id)
        user = User.query.get(patient.user_id)
        risk_score = predict_risk_score(patient_id)
        
        # Add to all patients list
        patients.append({
            'patient': patient,
            'user': user,
            'risk_score': risk_score
        })
        
        # Check if high risk
        if risk_score > 70:  # Arbitrary threshold for high risk
            high_risk_patients.append({
                'patient': patient,
                'user': user,
                'risk_score': risk_score
            })
    
    # Get recent unresolved alerts for all patients
    recent_alerts = Alert.query.filter(
        Alert.patient_id.in_(patient_ids),
        Alert.is_resolved == False
    ).order_by(Alert.timestamp.desc()).limit(10).all()
    
    # Get count summary of patients by diagnosis
    diagnosis_query = db.session.query(
        PatientProfile.diagnosis, db.func.count(PatientProfile.id)
    ).filter(
        PatientProfile.id.in_(patient_ids)
    ).group_by(PatientProfile.diagnosis).all()
    
    # Convert SQLAlchemy Row objects to a list of dictionaries for JSON serialization
    diagnosis_summary = [{'diagnosis': row[0], 'count': row[1]} for row in diagnosis_query]
    
    return render_template('provider/dashboard.html',
                           provider=provider,
                           patients=patients,
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
    patient_user = User.query.get(patient.user_id)
    
    # Get risk score and factors
    risk_score = predict_risk_score(patient_id)
    risk_factors = get_patient_risk_factors(patient_id)
    
    # Get recent readings
    readings = HealthReading.query.filter_by(patient_id=patient_id).order_by(HealthReading.timestamp.desc()).limit(20).all()
    
    # Get readings for charts (last 30 days)
    since_date = datetime.utcnow() - timedelta(days=30)
    
    glucose_readings_query = HealthReading.query.filter_by(
        patient_id=patient_id, reading_type='blood_glucose'
    ).filter(HealthReading.timestamp >= since_date).order_by(HealthReading.timestamp).all()
    
    # Convert SQLAlchemy objects to dictionaries for JSON serialization
    glucose_readings = []
    for reading in glucose_readings_query:
        glucose_readings.append({
            'id': reading.id,
            'patient_id': reading.patient_id,
            'reading_type': reading.reading_type,
            'value': reading.value,
            'unit': reading.unit,
            'timestamp': reading.timestamp.isoformat(),
            'is_abnormal': reading.is_abnormal,
            'notes': reading.notes
        })
    
    bp_readings_query = HealthReading.query.filter_by(
        patient_id=patient_id, reading_type='blood_pressure'
    ).filter(HealthReading.timestamp >= since_date).order_by(HealthReading.timestamp).all()
    
    # Convert SQLAlchemy objects to dictionaries for JSON serialization
    bp_readings = []
    for reading in bp_readings_query:
        bp_readings.append({
            'id': reading.id,
            'patient_id': reading.patient_id,
            'reading_type': reading.reading_type,
            'value': reading.value,
            'unit': reading.unit,
            'timestamp': reading.timestamp.isoformat(),
            'is_abnormal': reading.is_abnormal,
            'notes': reading.notes
        })
    
    # Get medications
    medications = Medication.query.filter_by(patient_id=patient_id).order_by(Medication.is_active.desc()).all()
    
    # Get unresolved alerts
    alerts = Alert.query.filter_by(patient_id=patient_id, is_resolved=False).order_by(Alert.timestamp.desc()).all()
    
    # Get devices
    devices = Device.query.filter_by(patient_id=patient_id).all()
    
    return render_template('provider/patient_detail.html',
                           provider=provider,
                           patient=patient,
                           patient_user=patient_user,
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

@provider_bp.route('/patient/<int:patient_id>/health-records')
@login_required
def patient_health_records(patient_id):
    provider = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    
    # Check if this provider is associated with this patient
    assoc = ProviderPatientAssociation.query.filter_by(
        provider_id=provider.id, patient_id=patient_id
    ).first()
    
    if not assoc:
        flash('You are not authorized to view this patient', 'danger')
        return redirect(url_for('provider.patients'))
        
    patient = PatientProfile.query.get_or_404(patient_id)
    patient_user = User.query.get(patient.user_id)
    
    # Get all records where the provider has active consent
    consented_record_ids = db.session.query(RecordConsent.record_id).filter(
        RecordConsent.provider_id == provider.id,
        RecordConsent.is_active == True,
        RecordConsent.expires_at > datetime.utcnow()
    ).all()
    
    consented_record_ids = [r[0] for r in consented_record_ids]  # Flatten query result
    
    record_type = request.args.get('type', 'all')
    
    # Filter records by type if specified
    query = HealthRecord.query.filter(
        HealthRecord.patient_id == patient_id,
        HealthRecord.id.in_(consented_record_ids)
    )
    
    if record_type != 'all':
        query = query.filter_by(record_type=record_type)
        
    records = query.order_by(HealthRecord.recorded_at.desc()).all()
    
    return render_template('provider/patient_health_records.html',
                          provider=provider,
                          patient=patient,
                          patient_user=patient_user,
                          records=records,
                          record_type=record_type)

@provider_bp.route('/patient/<int:patient_id>/health-records/<int:record_id>')
@login_required
def view_patient_health_record(patient_id, record_id):
    provider = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    
    # Check provider-patient association
    assoc = ProviderPatientAssociation.query.filter_by(
        provider_id=provider.id, patient_id=patient_id
    ).first()
    
    if not assoc:
        flash('You are not authorized to view this patient', 'danger')
        return redirect(url_for('provider.patients'))
    
    # Check if provider has consent for this specific record
    consent = RecordConsent.query.filter_by(
        record_id=record_id,
        provider_id=provider.id,
        is_active=True
    ).filter(RecordConsent.expires_at > datetime.utcnow()).first()
    
    if not consent:
        flash('You do not have consent to view this health record', 'danger')
        return redirect(url_for('provider.patient_health_records', patient_id=patient_id))
    
    record = HealthRecord.query.get_or_404(record_id)
    patient = PatientProfile.query.get_or_404(patient_id)
    patient_user = User.query.get(patient.user_id)
    recorded_by = User.query.get(record.recorded_by)
    
    return render_template('provider/view_patient_health_record.html',
                          provider=provider,
                          patient=patient,
                          patient_user=patient_user,
                          record=record,
                          recorded_by=recorded_by,
                          consent=consent)
                          
@provider_bp.route('/patient/<int:patient_id>/health-records/download/<int:record_id>')
@login_required
def download_patient_health_record(patient_id, record_id):
    provider = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    
    # Check provider-patient association
    assoc = ProviderPatientAssociation.query.filter_by(
        provider_id=provider.id, patient_id=patient_id
    ).first()
    
    if not assoc:
        flash('You are not authorized to download records for this patient', 'danger')
        return redirect(url_for('provider.patients'))
    
    # Check if provider has consent for this specific record
    consent = RecordConsent.query.filter_by(
        record_id=record_id,
        provider_id=provider.id,
        is_active=True
    ).filter(RecordConsent.expires_at > datetime.utcnow()).first()
    
    if not consent:
        flash('You do not have consent to download this health record', 'danger')
        return redirect(url_for('provider.patient_health_records', patient_id=patient_id))
    
    record = HealthRecord.query.get_or_404(record_id)
    
    # Check if this is a file record
    if not record.is_file_record or not record.file_path:
        flash('No file associated with this record', 'warning')
        return redirect(url_for('provider.view_patient_health_record', patient_id=patient_id, record_id=record_id))
    
    file_path = get_file_path(record_id)
    if not file_path or not os.path.exists(file_path):
        flash('File not found', 'danger')
        return redirect(url_for('provider.view_patient_health_record', patient_id=patient_id, record_id=record_id))
    
    return send_file(file_path, 
                    download_name=record.file_name,
                    as_attachment=True)

@provider_bp.route('/patient/<int:patient_id>/add-health-record', methods=['GET', 'POST'])
@login_required
def add_patient_health_record(patient_id):
    provider = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    
    # Check if provider is associated with this patient
    assoc = ProviderPatientAssociation.query.filter_by(
        provider_id=provider.id, patient_id=patient_id
    ).first()
    
    if not assoc:
        flash('You are not authorized to modify records for this patient', 'danger')
        return redirect(url_for('provider.patients'))
    
    patient = PatientProfile.query.get_or_404(patient_id)
    
    if request.method == 'POST':
        record_type = request.form.get('record_type')
        title = request.form.get('title')
        
        # Check if we're handling a file upload or text content
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            
            # Use the file upload service
            success, message, record_id = save_uploaded_file(
                file=file,
                patient_id=patient_id,
                record_type=record_type,
                title=title,
                provider_id=provider.id
            )
            
            if success:
                flash('Health record with file uploaded successfully', 'success')
            else:
                flash(message, 'danger')
                
            return redirect(url_for('provider.patient_health_records', patient_id=patient_id))
        else:
            # Regular text content record
            content = request.form.get('content')
            
            if not all([record_type, title, content]):
                flash('Please fill in all required fields', 'danger')
                return redirect(url_for('provider.add_patient_health_record', patient_id=patient_id))
            
            # Create new health record
            record = HealthRecord(
                patient_id=patient_id,
                record_type=record_type,
                title=title,
                content=content,
                recorded_by=current_user.id
            )
            
            db.session.add(record)
            db.session.commit()
            
            flash('Health record added successfully', 'success')
            return redirect(url_for('provider.patient_health_records', patient_id=patient_id))
    
    # Define record types for selection
    record_types = [
        'lab_result',
        'clinical_note',
        'prescription',
        'radiology',
        'surgery_note',
        'follow_up',
        'consultation'
    ]
    
    return render_template('provider/add_health_record.html',
                          provider=provider,
                          patient=patient,
                          record_types=record_types)

@provider_bp.route('/patient/<int:patient_id>/test-appointments')
@login_required
def view_patient_test_appointments(patient_id):
    provider = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    
    # Check if provider is associated with this patient
    assoc = ProviderPatientAssociation.query.filter_by(
        provider_id=provider.id, patient_id=patient_id
    ).first()
    
    if not assoc:
        flash('You are not authorized to view this patient', 'danger')
        return redirect(url_for('provider.patients'))
    
    patient = PatientProfile.query.get_or_404(patient_id)
    patient_user = User.query.get(patient.user_id)
    
    show_past = request.args.get('show_past', 'false') == 'true'
    
    query = TestAppointment.query.filter_by(patient_id=patient_id)
    
    if not show_past:
        query = query.filter(TestAppointment.scheduled_date >= datetime.utcnow())
        
    appointments = query.order_by(TestAppointment.scheduled_date).all()
    
    return render_template('provider/patient_test_appointments.html',
                          provider=provider,
                          patient=patient,
                          patient_user=patient_user,
                          appointments=appointments,
                          show_past=show_past)

@provider_bp.route('/patient/<int:patient_id>/schedule-test', methods=['GET', 'POST'])
@login_required
def schedule_patient_test(patient_id):
    provider = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    
    # Check if provider is associated with this patient
    assoc = ProviderPatientAssociation.query.filter_by(
        provider_id=provider.id, patient_id=patient_id
    ).first()
    
    if not assoc:
        flash('You are not authorized to schedule tests for this patient', 'danger')
        return redirect(url_for('provider.patients'))
    
    patient = PatientProfile.query.get_or_404(patient_id)
    patient_user = User.query.get(patient.user_id)
    
    if request.method == 'POST':
        # Get form data
        test_type = request.form.get('test_type')
        date_str = request.form.get('date')
        time_str = request.form.get('time')
        location = request.form.get('location')
        notes = request.form.get('notes', '')
        
        # Validate required fields
        if not all([test_type, date_str, time_str, location]):
            flash('All fields are required', 'danger')
            return redirect(url_for('provider.schedule_patient_test', patient_id=patient_id))
        
        # Create datetime from date and time
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            time_obj = datetime.strptime(time_str, '%H:%M').time()
            scheduled_date = datetime.combine(date_obj.date(), time_obj)
        except ValueError:
            flash('Invalid date or time format', 'danger')
            return redirect(url_for('provider.schedule_patient_test', patient_id=patient_id))
        
        # Create new appointment (confirmed by provider)
        appointment = TestAppointment(
            patient_id=patient_id,
            test_type=test_type,
            scheduled_date=scheduled_date,
            location=location,
            notes=notes,
            is_confirmed=True
        )
        
        db.session.add(appointment)
        db.session.commit()
        
        flash('Test appointment scheduled successfully', 'success')
        return redirect(url_for('provider.view_patient_test_appointments', patient_id=patient_id))
    
    # GET request - show booking form
    # Define test types
    test_types = [
        'HbA1c Test',
        'Fasting Blood Glucose',
        'Oral Glucose Tolerance Test',
        'Random Blood Glucose Test',
        'Kidney Function Test',
        'Lipid Profile',
        'Blood Pressure Check',
        'Eye Examination',
        'Foot Examination'
    ]
    
    return render_template('provider/schedule_test.html',
                          provider=provider,
                          patient=patient,
                          patient_user=patient_user,
                          test_types=test_types)

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

@provider_bp.route('/patient/<int:patient_id>/health-matrix')
@login_required
def patient_health_matrix(patient_id):
    """Health Matrix Visualization for provider to view patient data"""
    provider = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    
    # Check if this provider is associated with this patient
    assoc = ProviderPatientAssociation.query.filter_by(
        provider_id=provider.id, patient_id=patient_id
    ).first()
    
    if not assoc:
        flash('You are not authorized to view this patient', 'danger')
        return redirect(url_for('provider.patients'))
        
    patient = PatientProfile.query.get_or_404(patient_id)
    patient_user = User.query.get(patient.user_id)
    
    # Get the most recent health readings of each type (formatted as a dictionary)
    readings = {}
    reading_types = db.session.query(HealthReading.reading_type).filter_by(patient_id=patient.id).distinct().all()
    for type_tuple in reading_types:
        reading_type = type_tuple[0]
        latest = HealthReading.query.filter_by(
            patient_id=patient.id, 
            reading_type=reading_type
        ).order_by(HealthReading.timestamp.desc()).first()
        
        if latest:
            readings[reading_type] = latest
    
    # Get active medications
    medications = Medication.query.filter_by(
        patient_id=patient.id,
        is_active=True
    ).all()
    
    # Get recent health records
    health_records = HealthRecord.query.filter_by(
        patient_id=patient.id
    ).order_by(HealthRecord.recorded_at.desc()).limit(5).all()
    
    # Get latest predictions
    predictions = Prediction.query.filter_by(
        patient_id=patient.id
    ).order_by(Prediction.timestamp.desc()).limit(3).all()
    
    return render_template('patient/health_matrix.html', 
                          patient=patient,
                          provider=provider,
                          patient_user=patient_user,
                          is_provider_view=True,
                          readings=readings,
                          medications=medications,
                          health_records=health_records,
                          predictions=predictions)

@provider_bp.route('/patient/<int:patient_id>/risk-dashboard/<condition>')
@login_required
def patient_risk_dashboard(patient_id, condition):
    """Interactive Risk Dashboard for provider to view patient risk data"""
    provider = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    
    # Check if this provider is associated with this patient
    assoc = ProviderPatientAssociation.query.filter_by(
        provider_id=provider.id, patient_id=patient_id
    ).first()
    
    if not assoc:
        flash('You are not authorized to view this patient', 'danger')
        return redirect(url_for('provider.patients'))
        
    patient = PatientProfile.query.get_or_404(patient_id)
    patient_user = User.query.get(patient.user_id)
    
    # Validate condition parameter
    valid_conditions = ['diabetes', 'hypertension', 'cardiovascular']
    if condition not in valid_conditions:
        flash('Invalid condition specified', 'danger')
        return redirect(url_for('provider.patient_detail', patient_id=patient_id))
    
    # Get the most recent prediction for this condition
    prediction = Prediction.query.filter_by(
        patient_id=patient.id,
        condition=condition
    ).order_by(Prediction.timestamp.desc()).first()
    
    if not prediction:
        flash(f'No risk assessment available for {condition}. Please have the patient complete a questionnaire first.', 'warning')
        return redirect(url_for('provider.patient_detail', patient_id=patient_id))
    
    # Get risk dashboard data
    dashboard_data = get_risk_dashboard_data(patient.id, condition)
    
    # Get related readings
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    related_readings = {}
    if condition == 'diabetes':
        reading_types = ['blood_glucose', 'weight', 'hba1c']
    elif condition == 'hypertension':
        reading_types = ['blood_pressure', 'heart_rate']
    elif condition == 'cardiovascular':
        reading_types = ['blood_pressure', 'heart_rate', 'cholesterol', 'weight']
    
    for rtype in reading_types:
        related_readings[rtype] = HealthReading.query.filter_by(
            patient_id=patient.id,
            reading_type=rtype
        ).filter(HealthReading.timestamp >= thirty_days_ago).order_by(HealthReading.timestamp).all()
    
    return render_template('patient/risk_dashboard.html',
                          patient=patient,
                          provider=provider,
                          patient_user=patient_user,
                          condition=condition,
                          prediction=prediction,
                          dashboard_data=dashboard_data,
                          related_readings=related_readings,
                          is_provider_view=True)

@provider_bp.route('/patient/<int:patient_id>/symptom-heatmap')
@login_required
def patient_symptom_heatmap(patient_id):
    """Symptom Severity Heatmap for provider to view patient symptoms"""
    provider = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    
    # Check if this provider is associated with this patient
    assoc = ProviderPatientAssociation.query.filter_by(
        provider_id=provider.id, patient_id=patient_id
    ).first()
    
    if not assoc:
        flash('You are not authorized to view this patient', 'danger')
        return redirect(url_for('provider.patients'))
        
    patient = PatientProfile.query.get_or_404(patient_id)
    patient_user = User.query.get(patient.user_id)
    
    # Get time period from query params (default 30 days)
    days = int(request.args.get('days', 30))
    condition = request.args.get('condition', 'general')
    
    # Get heatmap data
    heatmap_data = get_symptom_heatmap(patient.id, condition, days)
    
    # Get symptom history for the selected symptom if provided
    selected_symptom = request.args.get('symptom')
    selected_body_part = request.args.get('body_part')
    
    symptom_history = None
    if selected_symptom or selected_body_part:
        symptom_history = get_symptom_history(
            patient_id=patient.id,
            symptom_type=selected_symptom,
            body_location=selected_body_part,
            days=days
        )
    
    # Get summary for sidebar
    symptom_summary = get_symptom_summary(patient.id, days)
    
    return render_template('patient/symptom_heatmap.html',
                          patient=patient,
                          provider=provider,
                          patient_user=patient_user,
                          heatmap_data=heatmap_data,
                          symptom_history=symptom_history,
                          symptom_summary=symptom_summary,
                          common_symptoms=COMMON_SYMPTOMS,
                          body_locations=BODY_LOCATIONS,
                          selected_condition=condition,
                          selected_symptom=selected_symptom,
                          selected_body_part=selected_body_part,
                          days=days,
                          is_provider_view=True)

@provider_bp.route('/patient/<int:patient_id>/wellness-journey')
@login_required
def patient_wellness_journey(patient_id):
    """Wellness Journey and Achievement Tracker for provider to view patient data"""
    provider = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    
    # Check if this provider is associated with this patient
    assoc = ProviderPatientAssociation.query.filter_by(
        provider_id=provider.id, patient_id=patient_id
    ).first()
    
    if not assoc:
        flash('You are not authorized to view this patient', 'danger')
        return redirect(url_for('provider.patients'))
        
    patient = PatientProfile.query.get_or_404(patient_id)
    patient_user = User.query.get(patient.user_id)
    
    # Get journey data
    journey_summary = get_patient_journey_summary(patient.id)
    
    # Get mood history data (last 30 days)
    mood_history = get_mood_history(patient.id)
    
    return render_template('patient/wellness_journey.html',
                          patient=patient,
                          provider=provider,
                          patient_user=patient_user,
                          journey_summary=journey_summary,
                          mood_history=mood_history,
                          is_provider_view=True)
