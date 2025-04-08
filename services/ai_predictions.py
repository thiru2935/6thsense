"""
AI Predictions Service using Google's Generative AI models for health predictions.
This service integrates with Gemini to predict chronic diseases based on health data.
"""
import os
import google.generativeai as genai
from datetime import datetime, timedelta
from app import db
from models import (
    HealthReading, 
    PatientProfile, 
    Medication, 
    HealthRecord, 
    Prediction, 
    PredictionModel
)

# Configure the Gemini API with the provided API key
def configure_genai():
    """Configure the Gemini API with API key"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    genai.configure(api_key=api_key)

# Function to get health data for a patient
def get_patient_health_data(patient_id, days=90):
    """
    Collect comprehensive health data for a specific patient over a given time period.
    
    Args:
        patient_id: ID of the patient
        days: Number of days of history to retrieve (default: 90)
    
    Returns:
        Dictionary containing structured health data
    """
    since_date = datetime.utcnow() - timedelta(days=days)
    
    # Get patient profile
    patient = PatientProfile.query.filter_by(id=patient_id).first()
    
    if not patient:
        return None
    
    # Get user information
    user = patient.user
    
    # Get health readings
    readings = HealthReading.query.filter_by(
        patient_id=patient_id
    ).filter(
        HealthReading.timestamp >= since_date
    ).order_by(HealthReading.timestamp).all()
    
    # Organize readings by type
    readings_by_type = {}
    for reading in readings:
        if reading.reading_type not in readings_by_type:
            readings_by_type[reading.reading_type] = []
        
        reading_data = {
            'value': reading.value,
            'unit': reading.unit,
            'timestamp': reading.timestamp.isoformat(),
            'is_abnormal': reading.is_abnormal
        }
        
        # Add specific blood pressure data if available
        if reading.reading_type == 'blood_pressure' and reading.value_systolic and reading.value_diastolic:
            reading_data['systolic'] = reading.value_systolic
            reading_data['diastolic'] = reading.value_diastolic
            if reading.value_pulse:
                reading_data['pulse'] = reading.value_pulse
                
        readings_by_type[reading.reading_type].append(reading_data)
    
    # Get medications
    medications = Medication.query.filter_by(
        patient_id=patient_id,
        is_active=True
    ).all()
    
    medications_data = []
    for med in medications:
        med_data = {
            'name': med.name,
            'dosage': med.dosage,
            'frequency': med.frequency,
            'start_date': med.start_date.isoformat() if med.start_date else None,
            'end_date': med.end_date.isoformat() if med.end_date else None
        }
        medications_data.append(med_data)
    
    # Get health records
    health_records = HealthRecord.query.filter_by(
        patient_id=patient_id
    ).filter(
        HealthRecord.recorded_at >= since_date
    ).order_by(HealthRecord.recorded_at).all()
    
    records_by_type = {}
    for record in health_records:
        if record.record_type not in records_by_type:
            records_by_type[record.record_type] = []
        
        record_data = {
            'title': record.title,
            'content': record.content,
            'recorded_at': record.recorded_at.isoformat()
        }
        records_by_type[record.record_type].append(record_data)
    
    # Compile all data
    health_data = {
        'patient': {
            'age': (datetime.utcnow().date() - patient.date_of_birth).days // 365 if patient.date_of_birth else None,
            'gender': patient.gender,
            'diagnosis': patient.diagnosis,
        },
        'readings': readings_by_type,
        'medications': medications_data,
        'health_records': records_by_type
    }
    
    return health_data

def generate_prediction_prompt(health_data, condition):
    """
    Create a structured prompt for the Gemini model based on patient health data.
    
    Args:
        health_data: Dictionary containing structured health data
        condition: The condition to predict (diabetes, hypertension, cardiovascular)
    
    Returns:
        Formatted prompt string
    """
    prompt = f"""As a medical AI assistant, analyze the following patient health data and provide an assessment 
of their risk for {condition.upper()}. Consider all the data points, correlations, and medical guidelines.

PATIENT INFORMATION:
- Age: {health_data['patient'].get('age', 'Unknown')}
- Gender: {health_data['patient'].get('gender', 'Unknown')}
- Current Diagnosis: {health_data['patient'].get('diagnosis', 'None')}

"""
    
    # Add readings section if available
    if health_data['readings']:
        prompt += "HEALTH READINGS:\n"
        for reading_type, readings in health_data['readings'].items():
            if readings:
                prompt += f"- {reading_type.replace('_', ' ').title()}:\n"
                # Add last 10 readings with timestamps
                for reading in readings[-10:]:
                    date = datetime.fromisoformat(reading['timestamp']).strftime('%Y-%m-%d')
                    if reading_type == 'blood_pressure':
                        prompt += f"  * {date}: {reading.get('systolic', 'N/A')}/{reading.get('diastolic', 'N/A')} mmHg"
                        if 'pulse' in reading:
                            prompt += f", Pulse: {reading['pulse']} bpm"
                        prompt += f" {'(Abnormal)' if reading.get('is_abnormal') else ''}\n"
                    else:
                        prompt += f"  * {date}: {reading['value']} {reading['unit']} {'(Abnormal)' if reading.get('is_abnormal') else ''}\n"
    
    # Add medications if available
    if health_data['medications']:
        prompt += "\nCURRENT MEDICATIONS:\n"
        for med in health_data['medications']:
            prompt += f"- {med['name']}, {med['dosage']}, {med['frequency']}\n"
    
    # Add relevant health records
    if health_data['health_records']:
        prompt += "\nRELEVANT HEALTH RECORDS:\n"
        relevant_types = ['lab_result', 'clinical_note', 'assessment']
        for record_type in relevant_types:
            if record_type in health_data['health_records']:
                prompt += f"- {record_type.replace('_', ' ').title()}:\n"
                for record in health_data['health_records'][record_type][-5:]:  # Get the 5 most recent
                    date = datetime.fromisoformat(record['recorded_at']).strftime('%Y-%m-%d')
                    prompt += f"  * {date} - {record['title']}: {record['content'][:100]}...\n"
    
    # Add specific request based on condition
    if condition.lower() == 'diabetes':
        prompt += """
Based on this patient's data, please assess their diabetes risk considering factors such as:
1. Blood glucose patterns
2. HbA1c levels if available
3. Medication history
4. Family history if mentioned
5. Weight, diet, and lifestyle factors if available

Please provide:
1. A risk score from 0-100 (where 100 is highest risk)
2. Key risk factors identified
3. Brief explanation of your assessment
4. Recommended monitoring or preventive measures
        """
    elif condition.lower() == 'hypertension':
        prompt += """
Based on this patient's data, please assess their hypertension risk considering factors such as:
1. Blood pressure patterns
2. Heart rate variability
3. Medication history
4. Lifestyle factors if available
5. Comorbidities

Please provide:
1. A risk score from 0-100 (where 100 is highest risk)
2. Key risk factors identified
3. Brief explanation of your assessment
4. Recommended monitoring or preventive measures
        """
    elif condition.lower() == 'cardiovascular':
        prompt += """
Based on this patient's data, please assess their cardiovascular disease risk considering factors such as:
1. Blood pressure patterns
2. Cholesterol levels if available
3. Smoking status if mentioned
4. Family history if available
5. Existing conditions like diabetes or hypertension

Please provide:
1. A risk score from 0-100 (where 100 is highest risk)
2. Key risk factors identified
3. Brief explanation of your assessment
4. Recommended monitoring or preventive measures
        """
    
    prompt += """
Provide your response in a structured format with clear sections for:
RISK_SCORE: [0-100]
KEY_FACTORS: [bulleted list]
ASSESSMENT: [detailed explanation]
RECOMMENDATIONS: [bulleted list]
"""
    
    return prompt

def extract_risk_score_from_response(response_text):
    """
    Extract the risk score and key insights from the Gemini model's response.
    
    Args:
        response_text: The full text response from the model
    
    Returns:
        Tuple of (risk_score, key_factors, assessment, recommendations)
    """
    risk_score = None
    key_factors = []
    assessment = ""
    recommendations = []
    
    # Look for the risk score value
    if "RISK_SCORE:" in response_text:
        risk_score_line = response_text.split("RISK_SCORE:")[1].split("\n")[0].strip()
        try:
            # Extract numeric value
            risk_score = int(''.join(filter(str.isdigit, risk_score_line)))
            # Ensure the score is within 0-100 range
            risk_score = max(0, min(100, risk_score))
        except (ValueError, IndexError):
            risk_score = 50  # Default to middle value if parsing fails
    
    # Extract key factors
    if "KEY_FACTORS:" in response_text:
        factors_section = response_text.split("KEY_FACTORS:")[1].split("ASSESSMENT:")[0].strip()
        for line in factors_section.split("\n"):
            line = line.strip()
            if line and (line.startswith("*") or line.startswith("-") or line.startswith("•")):
                key_factors.append(line.lstrip("*-•").strip())
    
    # Extract assessment
    if "ASSESSMENT:" in response_text:
        if "RECOMMENDATIONS:" in response_text:
            assessment = response_text.split("ASSESSMENT:")[1].split("RECOMMENDATIONS:")[0].strip()
        else:
            assessment = response_text.split("ASSESSMENT:")[1].strip()
    
    # Extract recommendations
    if "RECOMMENDATIONS:" in response_text:
        recommendations_section = response_text.split("RECOMMENDATIONS:")[1].strip()
        for line in recommendations_section.split("\n"):
            line = line.strip()
            if line and (line.startswith("*") or line.startswith("-") or line.startswith("•")):
                recommendations.append(line.lstrip("*-•").strip())
    
    return risk_score, key_factors, assessment, recommendations

def predict_disease_risk(patient_id, condition, save_to_db=True):
    """
    Generate a prediction for a specific chronic disease condition using Gemini AI.
    
    Args:
        patient_id: ID of the patient
        condition: Type of condition to predict (diabetes, hypertension, cardiovascular)
        save_to_db: Whether to save the prediction to the database
        
    Returns:
        Dictionary with prediction results
    """
    try:
        # Configure the Gemini API
        configure_genai()
        
        # Get patient data
        health_data = get_patient_health_data(patient_id)
        if not health_data:
            return {
                'success': False,
                'message': 'Patient data not found',
                'risk_score': None
            }
        
        # Generate prompt for the model
        prompt = generate_prediction_prompt(health_data, condition)
        
        # Use Gemini model to generate prediction
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        
        # Process the response to extract structured information
        risk_score, key_factors, assessment, recommendations = extract_risk_score_from_response(response.text)
        
        # Save prediction to database if requested
        if save_to_db and risk_score is not None:
            # Find or create prediction model
            model_obj = PredictionModel.query.filter_by(
                name=f"{condition.title()} Risk Assessment",
                target_condition=condition.lower()
            ).first()
            
            if not model_obj:
                model_obj = PredictionModel(
                    name=f"{condition.title()} Risk Assessment",
                    description=f"AI-based risk assessment for {condition}",
                    model_type="classification",
                    target_condition=condition.lower(),
                    is_active=True
                )
                db.session.add(model_obj)
                db.session.commit()
            
            # Create prediction record
            prediction = Prediction(
                model_id=model_obj.id,
                patient_id=patient_id,
                prediction_value=risk_score,
                confidence=0.85,  # Default confidence value
                notes=f"Key factors: {', '.join(key_factors[:3])}... Assessment: {assessment[:100]}..."
            )
            db.session.add(prediction)
            db.session.commit()
        
        return {
            'success': True,
            'risk_score': risk_score,
            'key_factors': key_factors,
            'assessment': assessment,
            'recommendations': recommendations
        }
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return {
            'success': False,
            'message': f'Error generating prediction: {str(e)}',
            'details': error_details,
            'risk_score': None
        }