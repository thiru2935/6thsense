from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import current_user, login_required
from datetime import datetime, timedelta
from functools import wraps

from app import db
from models import User, PatientProfile, Device, HealthReading, Medication, MedicationLog, Alert, HealthRecord, RecordConsent, TestAppointment, ProviderProfile, Prediction, PredictionModel
from services.prediction import predict_risk_score
from services.device_integration import sync_devices
from services.alerts import check_readings_for_alerts
from services.ai_predictions import predict_disease_risk

patient_bp = Blueprint('patient', __name__, url_prefix='/patient')

@patient_bp.before_request
def check_patient_access():
    if not current_user.is_authenticated or not current_user.is_patient():
        flash('Access denied. You must be logged in as a patient.', 'danger')
        return redirect(url_for('auth.login'))

def check_patient(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_patient():
            flash('Access denied. You must be logged in as a patient.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

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
    
    # Get reading data for charts - last 30 days of readings
    from datetime import datetime, timedelta
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    # Get glucose readings
    glucose_readings = HealthReading.query.filter_by(
        patient_id=patient.id, 
        reading_type='blood_glucose'
    ).filter(HealthReading.timestamp >= thirty_days_ago).order_by(HealthReading.timestamp).all()
    
    # Get blood pressure readings
    bp_readings = HealthReading.query.filter_by(
        patient_id=patient.id, 
        reading_type='blood_pressure'
    ).filter(HealthReading.timestamp >= thirty_days_ago).order_by(HealthReading.timestamp).all()
    
    # Get health records for charts
    health_records = HealthRecord.query.filter_by(
        patient_id=patient.id
    ).order_by(HealthRecord.recorded_at.desc()).limit(20).all()
    
    # Get data about medications intake
    medication_logs = db.session.query(
        MedicationLog, Medication
    ).join(
        Medication, MedicationLog.medication_id == Medication.id
    ).filter(
        Medication.patient_id == patient.id
    ).filter(
        MedicationLog.taken_at >= thirty_days_ago
    ).order_by(MedicationLog.taken_at).all()
    
    # Get data for device readings by type
    device_readings = db.session.query(
        HealthReading.reading_type, 
        db.func.count(HealthReading.id).label('count')
    ).filter(
        HealthReading.patient_id == patient.id
    ).filter(
        HealthReading.timestamp >= thirty_days_ago
    ).group_by(HealthReading.reading_type).all()
    
    reading_types_dict = {r[0]: r[1] for r in device_readings}
    
    # Get health record types for pie chart
    record_types = db.session.query(
        HealthRecord.record_type, 
        db.func.count(HealthRecord.id).label('count')
    ).filter(
        HealthRecord.patient_id == patient.id
    ).group_by(HealthRecord.record_type).all()
    
    record_types_dict = {r[0]: r[1] for r in record_types}
    
    # Get resolved vs unresolved alerts
    alert_statuses = db.session.query(
        Alert.is_resolved,
        db.func.count(Alert.id).label('count')
    ).filter(
        Alert.patient_id == patient.id
    ).filter(
        Alert.timestamp >= thirty_days_ago
    ).group_by(Alert.is_resolved).all()
    
    alert_statuses_dict = {bool(r[0]): r[1] for r in alert_statuses}
    
    return render_template('patient/dashboard.html',
                           patient=patient,
                           readings=recent_readings,
                           medications=medications,
                           alerts=alerts,
                           risk_score=risk_score,
                           glucose_readings=glucose_readings,
                           bp_readings=bp_readings,
                           health_records=health_records,
                           medication_logs=medication_logs,
                           reading_types_dict=reading_types_dict,
                           record_types_dict=record_types_dict,
                           alert_statuses_dict=alert_statuses_dict)

@patient_bp.route('/devices')
@login_required
def devices():
    patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
    devices = Device.query.filter_by(patient_id=patient.id).all()
    return render_template('patient/devices.html', patient=patient, devices=devices)

@patient_bp.route('/sync_patient_devices', methods=['POST'])
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

@patient_bp.route('/health-records')
@login_required
def health_records():
    patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
    record_type = request.args.get('type', 'all')
    
    query = HealthRecord.query.filter_by(patient_id=patient.id)
    
    if record_type != 'all':
        query = query.filter_by(record_type=record_type)
    
    records = query.order_by(HealthRecord.recorded_at.desc()).all()
    
    # Get providers that can be granted consent
    associated_providers = [assoc.provider for assoc in patient.providers]
    
    return render_template('patient/health_records.html', 
                          patient=patient, 
                          records=records, 
                          record_type=record_type,
                          providers=associated_providers)

@patient_bp.route('/health-records/<int:record_id>')
@login_required
def view_health_record(record_id):
    patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
    record = HealthRecord.query.get_or_404(record_id)
    
    if record.patient_id != patient.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('patient.health_records'))
    
    # Get consents for this record
    consents = RecordConsent.query.filter_by(record_id=record_id, is_active=True).all()
    
    # Get providers that aren't already granted consent
    granted_provider_ids = [consent.provider_id for consent in consents]
    associated_providers = [assoc.provider for assoc in patient.providers if assoc.provider_id not in granted_provider_ids]
    
    return render_template('patient/view_health_record.html', 
                          patient=patient, 
                          record=record,
                          consents=consents,
                          available_providers=associated_providers)

@patient_bp.route('/health-records/<int:record_id>/grant-consent', methods=['POST'])
@login_required
def grant_record_consent(record_id):
    patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
    record = HealthRecord.query.get_or_404(record_id)
    
    if record.patient_id != patient.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('patient.health_records'))
    
    provider_id = request.form.get('provider_id')
    if not provider_id:
        flash('Provider selection is required', 'danger')
        return redirect(url_for('patient.view_health_record', record_id=record_id))
    
    # Calculate expiration date (default 30 days)
    duration_days = int(request.form.get('duration', 30))
    expires_at = datetime.utcnow() + timedelta(days=duration_days)
    
    consent = RecordConsent(
        record_id=record_id,
        provider_id=provider_id,
        granted_by=current_user.id,
        expires_at=expires_at,
        is_active=True
    )
    
    db.session.add(consent)
    db.session.commit()
    
    flash('Access granted to provider', 'success')
    return redirect(url_for('patient.view_health_record', record_id=record_id))

@patient_bp.route('/health-records/<int:record_id>/revoke-consent/<int:consent_id>', methods=['POST'])
@login_required
def revoke_record_consent(record_id, consent_id):
    patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
    record = HealthRecord.query.get_or_404(record_id)
    consent = RecordConsent.query.get_or_404(consent_id)
    
    if record.patient_id != patient.id or consent.record_id != record_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('patient.health_records'))
    
    consent.is_active = False
    db.session.commit()
    
    flash('Provider access revoked', 'success')
    return redirect(url_for('patient.view_health_record', record_id=record_id))

@patient_bp.route('/test-appointments')
@login_required
def test_appointments():
    patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
    show_past = request.args.get('show_past', 'false') == 'true'
    
    query = TestAppointment.query.filter_by(patient_id=patient.id)
    
    if not show_past:
        query = query.filter(TestAppointment.scheduled_date >= datetime.utcnow())
        
    appointments = query.order_by(TestAppointment.scheduled_date).all()
    
    return render_template('patient/test_appointments.html', 
                          patient=patient, 
                          appointments=appointments, 
                          show_past=show_past)

@patient_bp.route('/book-test', methods=['GET', 'POST'])
@login_required
def book_test():
    patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
    
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
            return redirect(url_for('patient.book_test'))
        
        # Create datetime from date and time
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            time_obj = datetime.strptime(time_str, '%H:%M').time()
            scheduled_date = datetime.combine(date_obj.date(), time_obj)
        except ValueError:
            flash('Invalid date or time format', 'danger')
            return redirect(url_for('patient.book_test'))
        
        # Create new appointment
        appointment = TestAppointment(
            patient_id=patient.id,
            test_type=test_type,
            scheduled_date=scheduled_date,
            location=location,
            notes=notes
        )
        
        db.session.add(appointment)
        db.session.commit()
        
        flash('Appointment booked successfully', 'success')
        return redirect(url_for('patient.test_appointments'))
    
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
    
    return render_template('patient/book_test.html', 
                          patient=patient, 
                          test_types=test_types)

@patient_bp.route('/ai-prediction/<condition>')
@login_required
def ai_prediction(condition):
    """
    Generate AI-based disease prediction for the specified condition.
    Conditions: diabetes, hypertension, cardiovascular
    """
    patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
    
    # Validate condition
    valid_conditions = ['diabetes', 'hypertension', 'cardiovascular']
    if condition not in valid_conditions:
        flash(f'Invalid condition type. Must be one of: {", ".join(valid_conditions)}', 'danger')
        return redirect(url_for('patient.dashboard'))
    
    # Get the most recent prediction, if any
    recent_prediction = Prediction.query.join(PredictionModel).filter(
        Prediction.patient_id == patient.id,
        PredictionModel.target_condition == condition
    ).order_by(Prediction.timestamp.desc()).first()
    
    # Check if we have a recent prediction (less than 7 days old)
    use_cached = False
    if recent_prediction and (datetime.utcnow() - recent_prediction.timestamp).days < 7:
        use_cached = True
        prediction_result = {
            'success': True,
            'risk_score': recent_prediction.prediction_value,
            'key_factors': recent_prediction.notes.split('Key factors: ')[1].split('...')[0].split(', ') if 'Key factors: ' in recent_prediction.notes else [],
            'assessment': recent_prediction.notes.split('Assessment: ')[1].split('...')[0] if 'Assessment: ' in recent_prediction.notes else 'No detailed assessment available.'
        }
    else:
        # Generate a new prediction
        try:
            prediction_result = predict_disease_risk(patient.id, condition)
        except Exception as e:
            flash(f'Error generating prediction: {str(e)}', 'danger')
            return redirect(url_for('patient.dashboard'))
    
    # Check if API key is missing
    if not prediction_result['success'] and 'API_KEY' in prediction_result.get('message', ''):
        flash('Gemini API key is required for AI predictions. Please contact your administrator.', 'warning')
        return redirect(url_for('patient.dashboard'))
    
    return render_template('patient/ai_prediction.html',
                          patient=patient,
                          condition=condition,
                          prediction=prediction_result,
                          use_cached=use_cached,
                          prediction_date=recent_prediction.timestamp if use_cached else datetime.utcnow())

@patient_bp.route('/predictions')
@login_required
def predictions():
    """View all predictions for the current patient"""
    patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
    
    # Get all predictions, grouped by condition
    predictions = db.session.query(
        Prediction, PredictionModel
    ).join(
        PredictionModel
    ).filter(
        Prediction.patient_id == patient.id
    ).order_by(
        PredictionModel.target_condition,
        Prediction.timestamp.desc()
    ).all()
    
    # Group predictions by condition
    predictions_by_condition = {}
    for prediction, model in predictions:
        condition = model.target_condition
        if condition not in predictions_by_condition:
            predictions_by_condition[condition] = []
        predictions_by_condition[condition].append((prediction, model))
    
    return render_template('patient/predictions.html',
                          patient=patient,
                          predictions_by_condition=predictions_by_condition)

@patient_bp.route('/questionnaire/<condition>')
@login_required
@check_patient
def questionnaire(condition):
    """Show questionnaire for a specific condition"""
    patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
    
    # Validate condition
    valid_conditions = ['diabetes', 'hypertension', 'cardiovascular']
    if condition not in valid_conditions:
        flash(f'Invalid condition type. Must be one of: {", ".join(valid_conditions)}', 'danger')
        return redirect(url_for('patient.dashboard'))
    
    # Get questions for this condition
    from services.questionnaire import get_questionnaire_questions
    questions = get_questionnaire_questions(condition)
    
    return render_template('patient/questionnaire.html',
                          patient=patient,
                          condition=condition,
                          questions=questions)

@patient_bp.route('/questionnaire/<condition>/submit', methods=['POST'])
@login_required
@check_patient
def submit_questionnaire(condition):
    """Process questionnaire submission and generate prediction"""
    patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
    
    # Validate condition
    valid_conditions = ['diabetes', 'hypertension', 'cardiovascular']
    if condition not in valid_conditions:
        flash(f'Invalid condition type. Must be one of: {", ".join(valid_conditions)}', 'danger')
        return redirect(url_for('patient.dashboard'))
    
    # Collect responses
    responses = {}
    for key, value in request.form.items():
        if key.startswith('q_'):
            question_id = int(key.split('_')[1])
            responses[question_id] = value
    
    # Save responses to database
    from services.questionnaire import save_questionnaire_responses
    save_questionnaire_responses(patient.id, condition, responses)
    
    # Redirect to prediction page to generate a new prediction with the questionnaire data
    flash('Thank you for completing the questionnaire. Generating your personalized health assessment...', 'success')
    return redirect(url_for('patient.ai_prediction', condition=condition))
@patient_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@check_patient
def profile():
    """Patient profile page"""
    patient = current_user.patient_profile
    if not patient:
        flash('Patient profile not found.', 'danger')
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        # Process form data
        current_user.first_name = request.form.get('first_name')
        current_user.last_name = request.form.get('last_name')
        
        patient.date_of_birth = datetime.strptime(request.form.get('date_of_birth'), '%Y-%m-%d').date() if request.form.get('date_of_birth') else None
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
