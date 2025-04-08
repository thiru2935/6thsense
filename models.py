from app import db
from datetime import datetime, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import enum
import json
import os

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
    content = db.Column(db.Text, nullable=True)  # Can be null if file is attached
    recorded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    file_path = db.Column(db.String(255))  # Path to attached file
    file_type = db.Column(db.String(50))  # pdf, jpg, png, docx, etc.
    file_name = db.Column(db.String(255))  # Original filename
    file_size = db.Column(db.Integer)  # Size in bytes
    is_file_record = db.Column(db.Boolean, default=False)  # Flag to indicate if this is a file-based record
    upload_date = db.Column(db.DateTime)  # When the file was uploaded
    
    # Relationships
    patient = db.relationship('PatientProfile', backref=db.backref('health_records', cascade='all, delete-orphan'))
    
    @property
    def file_extension(self):
        if self.file_name:
            return os.path.splitext(self.file_name)[1].lower()
        return None
        
    @property
    def is_image(self):
        if self.file_extension:
            return self.file_extension in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
        return False
        
    @property
    def is_pdf(self):
        if self.file_extension:
            return self.file_extension == '.pdf'
        return False
        
    @property
    def is_viewable(self):
        return self.is_image or self.is_pdf
        
    @property
    def file_size_formatted(self):
        if not self.file_size:
            return "Unknown"
            
        # Convert bytes to KB, MB as needed
        if self.file_size < 1024:
            return f"{self.file_size} bytes"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        else:
            return f"{self.file_size / (1024 * 1024):.1f} MB"
            
    # Relationships (additional)
    provider = db.relationship('User', foreign_keys=[recorded_by], backref='recorded_health_records')
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


# Models for EMR/Hospital systems integration
class ExternalSystem(db.Model):
    """External EMR/Hospital system that can be integrated with the platform"""
    id = db.Column(db.Integer, primary_key=True)
    system_name = db.Column(db.String(100), nullable=False)
    system_type = db.Column(db.String(50), nullable=False)  # EMR, Hospital, Lab, etc.
    api_endpoint = db.Column(db.String(255), nullable=False)
    api_auth_type = db.Column(db.String(50), nullable=False)  # oauth2, apikey, jwt, etc.
    is_active = db.Column(db.Boolean, default=True)
    is_bidirectional = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    connections = db.relationship('SystemConnection', backref='system', cascade='all, delete-orphan')
    data_mappings = db.relationship('DataMapping', backref='system', cascade='all, delete-orphan')
    integration_logs = db.relationship('IntegrationLog', backref='system', cascade='all, delete-orphan')


class SystemConnection(db.Model):
    """Connection details for external systems"""
    id = db.Column(db.Integer, primary_key=True)
    system_id = db.Column(db.Integer, db.ForeignKey('external_system.id'), nullable=False)
    connection_name = db.Column(db.String(100), nullable=False)
    auth_token = db.Column(db.String(255))
    refresh_token = db.Column(db.String(255))
    token_expires_at = db.Column(db.DateTime)
    connection_status = db.Column(db.String(50), default='pending')  # pending, active, error
    last_sync = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Secure credentials are stored encrypted
    # These fields should be encrypted in a production environment
    api_key = db.Column(db.String(255))
    client_id = db.Column(db.String(255))
    client_secret = db.Column(db.String(255))


class DataMapping(db.Model):
    """Maps data fields between our system and external systems"""
    id = db.Column(db.Integer, primary_key=True)
    system_id = db.Column(db.Integer, db.ForeignKey('external_system.id'), nullable=False)
    our_field = db.Column(db.String(100), nullable=False)  # Field name in our system
    external_field = db.Column(db.String(100), nullable=False)  # Field name in external system
    data_type = db.Column(db.String(50), nullable=False)  # string, integer, date, etc.
    entity_type = db.Column(db.String(50), nullable=False)  # patient, reading, medication, etc.
    is_required = db.Column(db.Boolean, default=False)
    transformation_rule = db.Column(db.Text)  # JSON string with transformation rules if needed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class IntegrationLog(db.Model):
    """Logs all data exchange with external systems"""
    id = db.Column(db.Integer, primary_key=True)
    system_id = db.Column(db.Integer, db.ForeignKey('external_system.id'), nullable=False)
    direction = db.Column(db.String(10), nullable=False)  # inbound, outbound
    status = db.Column(db.String(20), nullable=False)  # success, error, pending
    entity_type = db.Column(db.String(50), nullable=False)  # patient, reading, medication, etc.
    entity_id = db.Column(db.Integer)  # ID of the affected entity
    message = db.Column(db.Text)
    details = db.Column(db.Text)  # JSON string with detailed information
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # If the integration involved a patient, link it
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profile.id'))
    patient = db.relationship('PatientProfile', backref=db.backref('integration_logs', lazy='dynamic'))


class PatientExternalMapping(db.Model):
    """Maps patients in our system to their records in external systems"""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profile.id'), nullable=False)
    system_id = db.Column(db.Integer, db.ForeignKey('external_system.id'), nullable=False)
    external_patient_id = db.Column(db.String(100), nullable=False)  # ID in the external system
    last_sync = db.Column(db.DateTime)
    sync_status = db.Column(db.String(20), default='pending')  # pending, synced, error
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    patient = db.relationship('PatientProfile')
    system = db.relationship('ExternalSystem')
    
    # Unique constraint to ensure a patient can only be mapped once to a specific external system
    __table_args__ = (db.UniqueConstraint('patient_id', 'system_id', name='uix_patient_system'),)


# Advanced Features Models

class MoodEntry(db.Model):
    """User's daily mood log with emoji-based representation"""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profile.id'), nullable=False)
    mood_emoji = db.Column(db.String(10), nullable=False)  # Unicode emoji character
    mood_value = db.Column(db.Integer, nullable=False)  # 1-5 scale (1:very bad, 5:excellent)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = db.relationship('PatientProfile', backref=db.backref('mood_entries', cascade='all, delete-orphan'))
    
    @property
    def emoji_description(self):
        """Returns human-readable description based on mood value"""
        descriptions = {
            1: "Feeling very low",
            2: "Not great",
            3: "Okay",
            4: "Good",
            5: "Excellent"
        }
        return descriptions.get(self.mood_value, "Unknown")


class WellnessJourney(db.Model):
    """Tracks patient's progress through wellness milestones and achievements"""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profile.id'), nullable=False)
    total_points = db.Column(db.Integer, default=0)
    current_level = db.Column(db.Integer, default=1)
    milestone_progress = db.Column(db.Text)  # JSON of current milestone progress
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    patient = db.relationship('PatientProfile', backref=db.backref('wellness_journey', uselist=False))
    badges = db.relationship('WellnessBadge', backref='journey', cascade='all, delete-orphan')


class WellnessBadge(db.Model):
    """Achievement badges awarded to patients for health goals"""
    id = db.Column(db.Integer, primary_key=True)
    journey_id = db.Column(db.Integer, db.ForeignKey('wellness_journey.id'), nullable=False)
    badge_type = db.Column(db.String(50), nullable=False)  # e.g., "consistent_readings", "medication_adherence"
    badge_level = db.Column(db.Integer, default=1)  # Bronze (1), Silver (2), Gold (3), etc.
    badge_name = db.Column(db.String(100), nullable=False)
    badge_description = db.Column(db.Text)
    awarded_at = db.Column(db.DateTime, default=datetime.utcnow)
    icon_path = db.Column(db.String(255))
    
    @property
    def level_name(self):
        levels = {1: "Bronze", 2: "Silver", 3: "Gold", 4: "Platinum", 5: "Diamond"}
        return levels.get(self.badge_level, "Level " + str(self.badge_level))


class SymptomHeatmapEntry(db.Model):
    """AI-powered symptom severity tracking with color coding"""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profile.id'), nullable=False)
    symptom_type = db.Column(db.String(100), nullable=False)  # e.g., "fatigue", "pain", "dizziness"
    severity = db.Column(db.Integer, nullable=False)  # 0-10 scale
    body_location = db.Column(db.String(100))  # For localized symptoms
    color_code = db.Column(db.String(7))  # HTML color code (#RRGGBB)
    reported_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    
    # Relationships
    patient = db.relationship('PatientProfile', backref=db.backref('symptom_entries', cascade='all, delete-orphan'))
    
    @property
    def severity_text(self):
        """Returns text representation of severity level"""
        severity_map = {
            0: "None",
            1: "Minimal",
            2: "Very Mild",
            3: "Mild",
            4: "Mild to Moderate",
            5: "Moderate",
            6: "Moderate to Severe",
            7: "Severe",
            8: "Very Severe",
            9: "Extreme",
            10: "Unbearable"
        }
        return severity_map.get(self.severity, "Unknown")
    
    @property
    def severity_color(self):
        """Returns color based on severity if not explicitly set"""
        if self.color_code:
            return self.color_code
            
        # Generate color from green (low) to red (high)
        if self.severity <= 3:
            return "#4CAF50"  # Green
        elif self.severity <= 5:
            return "#FFC107"  # Yellow/Amber
        elif self.severity <= 7:
            return "#FF9800"  # Orange
        else:
            return "#F44336"  # Red


class TreatmentRecommendation(db.Model):
    """Advanced ML-generated personalized treatment recommendations"""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profile.id'), nullable=False)
    condition = db.Column(db.String(100), nullable=False)  # Target condition for this recommendation
    recommendation_type = db.Column(db.String(50), nullable=False)  # medication, lifestyle, diet, exercise, monitoring
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    evidence_level = db.Column(db.String(50))  # e.g., "strong", "moderate", "limited"
    confidence_score = db.Column(db.Float)  # AI model confidence (0-1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    is_viewed = db.Column(db.Boolean, default=False)
    viewed_at = db.Column(db.DateTime)
    
    # Store model parameters as JSON
    model_parameters = db.Column(db.Text)  # JSON string of parameters used for this recommendation
    
    # Relationships
    patient = db.relationship('PatientProfile', backref=db.backref('treatment_recommendations', cascade='all, delete-orphan'))
    
    def get_parameters(self):
        """Return model parameters as dictionary"""
        if self.model_parameters:
            try:
                return json.loads(self.model_parameters)
            except:
                return {}
        return {}
    
    def set_parameters(self, params_dict):
        """Set model parameters from dictionary"""
        if params_dict:
            self.model_parameters = json.dumps(params_dict)


class RiskFactorInteraction(db.Model):
    """For interactive risk factor drill-down in animated health risk dashboard"""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profile.id'), nullable=False)
    prediction_id = db.Column(db.Integer, db.ForeignKey('prediction.id'), nullable=False)
    risk_factor = db.Column(db.String(100), nullable=False)  # e.g., "blood_pressure", "glucose_levels"
    current_value = db.Column(db.Float)  # Current value for this factor
    ideal_value = db.Column(db.Float)  # Target/ideal value 
    impact_score = db.Column(db.Float)  # How much this factor contributes to overall risk (0-100)
    recommendations = db.Column(db.Text)  # JSON string of specific recommendations for this factor
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = db.relationship('PatientProfile', backref=db.backref('risk_factor_interactions', cascade='all, delete-orphan'))
    prediction = db.relationship('Prediction', backref=db.backref('risk_factors', cascade='all, delete-orphan'))
    
    def get_recommendations(self):
        """Return recommendations as a list"""
        if self.recommendations:
            try:
                return json.loads(self.recommendations)
            except:
                return []
        return []


# PatientExternalMapping is defined above


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