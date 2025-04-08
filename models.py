from app import db
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# User role constants
USER_ROLE_PATIENT = 'patient'
USER_ROLE_PROVIDER = 'provider'
USER_ROLE_ADMIN = 'admin'


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    role = db.Column(db.String(20), nullable=False)  # patient, provider, or admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    patient_profile = db.relationship('PatientProfile', backref='user', uselist=False, cascade='all, delete-orphan')
    provider_profile = db.relationship('ProviderProfile', backref='user', uselist=False, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_patient(self):
        return self.role == 'patient'
    
    def is_provider(self):
        return self.role == 'provider'
    
    def is_admin(self):
        return self.role == 'admin'
    
    def get_full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username


class PatientProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(20))
    contact_number = db.Column(db.String(20))
    emergency_contact = db.Column(db.String(20))
    address = db.Column(db.String(200))
    preferred_language = db.Column(db.String(50), default='English')
    diagnosis = db.Column(db.String(100))  # Primary diagnosis (e.g., Type 1 Diabetes)
    
    # Relationships
    devices = db.relationship('Device', backref='patient', cascade='all, delete-orphan')
    readings = db.relationship('HealthReading', backref='patient', cascade='all, delete-orphan')
    alerts = db.relationship('Alert', backref='patient', cascade='all, delete-orphan')
    medications = db.relationship('Medication', backref='patient', cascade='all, delete-orphan')
    health_questionnaires = db.relationship('HealthQuestionnaire', backref='patient', cascade='all, delete-orphan')


class ProviderProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    specialty = db.Column(db.String(100))
    license_number = db.Column(db.String(50))
    hospital_affiliation = db.Column(db.String(100))
    contact_number = db.Column(db.String(20))
    
    # Relationships
    patients = db.relationship('ProviderPatientAssociation', back_populates='provider')


class ProviderPatientAssociation(db.Model):
    provider_id = db.Column(db.Integer, db.ForeignKey('provider_profile.id'), primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profile.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    provider = db.relationship('ProviderProfile', back_populates='patients')
    patient = db.relationship('PatientProfile', backref=db.backref('providers', cascade='all, delete-orphan'))


class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profile.id'), nullable=False)
    device_type = db.Column(db.String(50), nullable=False)  # glucometer, BP monitor, etc.
    device_id = db.Column(db.String(100), nullable=False)  # Unique identifier for the device
    manufacturer = db.Column(db.String(100))
    model = db.Column(db.String(100))
    last_synced = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    readings = db.relationship('HealthReading', backref='device', cascade='all, delete-orphan')


class HealthReading(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profile.id'), nullable=False)
    device_id = db.Column(db.Integer, db.ForeignKey('device.id'))
    reading_type = db.Column(db.String(50), nullable=False)  # blood glucose, blood pressure, etc.
    value = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=False)  # mg/dL, mmHg, etc.
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    is_abnormal = db.Column(db.Boolean, default=False)
    
    # Additional values for specific reading types
    value_systolic = db.Column(db.Float)  # For blood pressure
    value_diastolic = db.Column(db.Float)  # For blood pressure
    value_pulse = db.Column(db.Float)  # For pulse rate


class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profile.id'), nullable=False)
    alert_type = db.Column(db.String(50), nullable=False)  # abnormal reading, missed medication, etc.
    message = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(20), nullable=False)  # low, medium, high
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_resolved = db.Column(db.Boolean, default=False)
    resolved_at = db.Column(db.DateTime)
    resolved_by = db.Column(db.Integer, db.ForeignKey('user.id'))


class Medication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profile.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    dosage = db.Column(db.String(50))
    frequency = db.Column(db.String(50))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    instructions = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    logs = db.relationship('MedicationLog', backref='medication', cascade='all, delete-orphan')


class MedicationLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    medication_id = db.Column(db.Integer, db.ForeignKey('medication.id'), nullable=False)
    taken_at = db.Column(db.DateTime, default=datetime.utcnow)
    was_taken = db.Column(db.Boolean, default=True)  # False if missed
    notes = db.Column(db.Text)


class PredictionModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    model_type = db.Column(db.String(50))  # classification, regression, etc.
    target_condition = db.Column(db.String(50))  # diabetes, hypertension, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    predictions = db.relationship('Prediction', backref='model', cascade='all, delete-orphan')


class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    model_id = db.Column(db.Integer, db.ForeignKey('prediction_model.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profile.id'), nullable=False)
    prediction_value = db.Column(db.Float, nullable=False)
    confidence = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    
    # Relationships
    patient = db.relationship('PatientProfile', backref=db.backref('predictions', cascade='all, delete-orphan'))
    key_factors = db.Column(db.Text)  # Stored as JSON
    recommendations = db.Column(db.Text)  # Stored as JSON
    assessment = db.Column(db.Text)
    condition = db.Column(db.String(50))  # diabetes, hypertension, cardiovascular


class ChatSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    session_start = db.Column(db.DateTime, default=datetime.utcnow)
    session_end = db.Column(db.DateTime)
    language = db.Column(db.String(50), default='English')
    
    # Relationships
    messages = db.relationship('ChatMessage', backref='session', cascade='all, delete-orphan')
    user = db.relationship('User', backref='chat_sessions')


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id'), nullable=False)
    sender_type = db.Column(db.String(20), nullable=False)  # user or bot
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class HealthRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profile.id'), nullable=False)
    record_type = db.Column(db.String(50), nullable=False)  # lab_result, clinical_note, prescription, radiology, etc.
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    recorded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    file_path = db.Column(db.String(255))  # Optional path to attached file
    
    # Relationships
    patient = db.relationship('PatientProfile', backref=db.backref('health_records', cascade='all, delete-orphan'))
    provider = db.relationship('User', backref='recorded_health_records')
    consents = db.relationship('RecordConsent', backref='health_record', cascade='all, delete-orphan')


class RecordConsent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.Integer, db.ForeignKey('health_record.id'), nullable=False)
    provider_id = db.Column(db.Integer, db.ForeignKey('provider_profile.id'), nullable=False)
    granted_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Patient who granted consent
    granted_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    provider = db.relationship('ProviderProfile', backref='record_consents')
    patient = db.relationship('User', backref='granted_consents')


class TestAppointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profile.id'), nullable=False)
    test_type = db.Column(db.String(100), nullable=False)  # e.g., HbA1c, Glucose Tolerance, etc.
    scheduled_date = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(200))
    notes = db.Column(db.Text)
    is_confirmed = db.Column(db.Boolean, default=False)
    is_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = db.relationship('PatientProfile', backref=db.backref('test_appointments', cascade='all, delete-orphan'))


# New models for health questionnaires
class HealthQuestionnaire(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profile.id'), nullable=False)
    condition = db.Column(db.String(50), nullable=False)  # diabetes, hypertension, cardiovascular
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    responses = db.relationship('QuestionnaireResponse', backref='questionnaire', cascade='all, delete-orphan')


class QuestionnaireQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    condition = db.Column(db.String(50), nullable=False)  # diabetes, hypertension, cardiovascular
    question_text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(20), nullable=False)  # multiple_choice, boolean, text, numeric
    options = db.Column(db.Text)  # JSON string for multiple choice options
    weight = db.Column(db.Integer, default=1)  # Importance weight for AI prediction
    order = db.Column(db.Integer)  # Order in the questionnaire
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    responses = db.relationship('QuestionnaireResponse', backref='question')


class QuestionnaireResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    questionnaire_id = db.Column(db.Integer, db.ForeignKey('health_questionnaire.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questionnaire_question.id'), nullable=False)
    response_text = db.Column(db.Text, nullable=False)  # String representation of answer
    response_value = db.Column(db.Float)  # Numerical value if applicable
    created_at = db.Column(db.DateTime, default=datetime.utcnow)