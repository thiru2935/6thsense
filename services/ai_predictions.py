"""
AI Predictions Service using Google's Generative AI models for health predictions.
This service integrates with Gemini to predict chronic diseases based on health data.
"""

import os
import json
import logging
import re
from datetime import datetime, timedelta
import google.generativeai as genai
from flask import current_app
from app import db
from models import (
    HealthReading, 
    
    # Additional imports for questionnaire integration
    HealthQuestionnaire,
    QuestionnaireQuestion,
    QuestionnaireResponse,
    Prediction, 
    PredictionModel, 
    PatientProfile,
    Device
)
from services.questionnaire import get_questionnaire_data_for_prediction


def configure_genai():
    """Configure the Gemini API with API key"""
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        logging.error("GEMINI_API_KEY not found in environment variables")
        return False
    
    try:
        # Log key length for debugging (don't log the actual key)
        logging.info(f"Configuring Gemini API with key of length: {len(api_key)}")
        
        genai.configure(api_key=api_key)
        
        # Test API connectivity by listing available models
        available_models = [model.name for model in genai.list_models()]
        logging.info(f"Available Gemini models: {available_models}")
        
        return True
    except Exception as e:
        logging.error(f"Error configuring Gemini API: {str(e)}")
        return False


def get_patient_health_data(patient_id, days=90):
    """
    Collect comprehensive health data for a specific patient over a given time period.
    
    Args:
        patient_id: ID of the patient
        days: Number of days of history to retrieve (default: 90)
    
    Returns:
        Dictionary containing structured health data
    """
    try:
        # Get patient profile
        patient = PatientProfile.query.get(patient_id)
        if not patient:
            return None
            
        # Calculate the start date for the data retrieval
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get all readings in the time period
        readings = HealthReading.query.filter(
            HealthReading.patient_id == patient_id,
            HealthReading.timestamp >= start_date,
            HealthReading.timestamp <= end_date
        ).order_by(HealthReading.timestamp.desc()).all()
        
        # Get patient's devices
        devices = Device.query.filter_by(patient_id=patient_id).all()
        
        # Structured health data
        health_data = {
            "patient_info": {
                "id": patient_id,
                "age": calculate_age(patient.date_of_birth) if patient.date_of_birth else None,
                "gender": patient.gender,
                "primary_diagnosis": patient.diagnosis
            },
            "device_info": [
                {
                    "device_type": device.device_type,
                    "manufacturer": device.manufacturer,
                    "model": device.model,
                    "last_synced": device.last_synced.isoformat() if device.last_synced else None
                }
                for device in devices
            ],
            "readings": {
                "blood_glucose": [],
                "blood_pressure": [],
                "weight": [],
                "heart_rate": [],
                "activity": [],
                "other": []
            },
            "abnormal_readings_count": 0,
            "reading_trends": {},
            "metadata": {
                "data_period_days": days,
                "total_readings_count": len(readings),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }
        }
        
        # Process and categorize readings
        for reading in readings:
            reading_data = {
                "value": reading.value,
                "unit": reading.unit,
                "timestamp": reading.timestamp.isoformat(),
                "is_abnormal": reading.is_abnormal
            }
            
            # Add special readings for blood pressure
            if reading.reading_type == "blood_pressure":
                reading_data["systolic"] = reading.value_systolic
                reading_data["diastolic"] = reading.value_diastolic
                reading_data["pulse"] = reading.value_pulse
            
            # Increment abnormal count if applicable
            if reading.is_abnormal:
                health_data["abnormal_readings_count"] += 1
            
            # Add to appropriate category
            if reading.reading_type in health_data["readings"]:
                health_data["readings"][reading.reading_type].append(reading_data)
            else:
                health_data["readings"]["other"].append({
                    **reading_data,
                    "reading_type": reading.reading_type
                })
        
        # Calculate trends
        for reading_type, readings_list in health_data["readings"].items():
            if not readings_list:
                continue
                
            # Sort by timestamp if needed
            readings_list.sort(key=lambda x: x["timestamp"], reverse=True)
            
            # For blood pressure, we need to handle systolic and diastolic
            if reading_type == "blood_pressure":
                # Calculate systolic trend
                systolic_values = [r.get("systolic") for r in readings_list if r.get("systolic") is not None]
                if len(systolic_values) > 1:
                    systolic_trend = calculate_trend(systolic_values)
                    health_data["reading_trends"]["systolic"] = systolic_trend
                
                # Calculate diastolic trend
                diastolic_values = [r.get("diastolic") for r in readings_list if r.get("diastolic") is not None]
                if len(diastolic_values) > 1:
                    diastolic_trend = calculate_trend(diastolic_values)
                    health_data["reading_trends"]["diastolic"] = diastolic_trend
            else:
                # For other readings, use the main value
                values = [r["value"] for r in readings_list]
                if len(values) > 1:
                    trend = calculate_trend(values)
                    health_data["reading_trends"][reading_type] = trend
        
        # Get questionnaire data for all conditions
        conditions = ["diabetes", "hypertension", "cardiovascular"]
        health_data["questionnaires"] = {}
        
        for cond in conditions:
            questionnaire_data = get_questionnaire_data_for_prediction(patient_id, cond)
            if questionnaire_data:
                health_data["questionnaires"][cond] = questionnaire_data
        
        return health_data
    
    except Exception as e:
        current_app.logger.error(f"Error getting patient health data: {str(e)}")
        return None


def calculate_age(birth_date):
    """Calculate age from birth_date"""
    if not birth_date:
        return None
    today = datetime.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def calculate_trend(values):
    """
    Calculate the trend of a series of values.
    Returns 'increasing', 'decreasing', 'stable', or None if not enough data
    """
    if len(values) < 2:
        return None
    
    # Simple trend: compare first and last value
    first_value = values[-1]  # Oldest value
    last_value = values[0]    # Newest value
    
    # Calculate percentage change
    if first_value == 0:
        return None
    
    percent_change = ((last_value - first_value) / abs(first_value)) * 100
    
    # Categorize the trend
    if abs(percent_change) < 5:
        return "stable"
    elif percent_change > 0:
        return "increasing"
    else:
        return "decreasing"


def generate_prediction_prompt(health_data, condition):
    """
    Create a structured prompt for the Gemini model based on patient health data.
    
    Args:
        health_data: Dictionary containing structured health data
        condition: The condition to predict (diabetes, hypertension, cardiovascular)
    
    Returns:
        Formatted prompt string
    """
    if not health_data:
        return "Unable to retrieve patient health data."
    
    # Base prompt structure
    prompt = f"""
You are a medical AI assistant specialized in chronic disease risk assessment. Analyze the following patient data and provide a risk assessment for {condition.upper()}.

PATIENT INFORMATION:
- Age: {health_data['patient_info']['age'] if health_data['patient_info']['age'] else 'Unknown'}
- Gender: {health_data['patient_info']['gender'] if health_data['patient_info']['gender'] else 'Unknown'}
- Primary Diagnosis: {health_data['patient_info']['primary_diagnosis'] if health_data['patient_info']['primary_diagnosis'] else 'None'}

HEALTH READINGS SUMMARY (Past {health_data['metadata']['data_period_days']} days):
- Total Readings: {health_data['metadata']['total_readings_count']}
- Abnormal Readings: {health_data['abnormal_readings_count']}
"""

    # Add Blood Glucose Data
    bg_readings = health_data['readings']['blood_glucose']
    if bg_readings:
        latest_bg = bg_readings[0]
        avg_bg = sum(r['value'] for r in bg_readings) / len(bg_readings)
        abnormal_bg = sum(1 for r in bg_readings if r['is_abnormal'])
        
        bg_trend = health_data['reading_trends'].get('blood_glucose', 'Unknown')
        
        prompt += f"""
BLOOD GLUCOSE DATA:
- Latest Reading: {latest_bg['value']} {latest_bg['unit']} ({latest_bg['timestamp']})
- Average Value: {avg_bg:.1f} {latest_bg['unit']}
- Abnormal Readings: {abnormal_bg} out of {len(bg_readings)}
- Trend: {bg_trend.title() if bg_trend else 'Insufficient data for trend analysis'}
"""

    # Add Blood Pressure Data
    bp_readings = health_data['readings']['blood_pressure']
    if bp_readings:
        latest_bp = bp_readings[0]
        avg_systolic = sum(r.get('systolic', 0) for r in bp_readings if 'systolic' in r) / len(bp_readings)
        avg_diastolic = sum(r.get('diastolic', 0) for r in bp_readings if 'diastolic' in r) / len(bp_readings)
        abnormal_bp = sum(1 for r in bp_readings if r['is_abnormal'])
        
        systolic_trend = health_data['reading_trends'].get('systolic', 'Unknown')
        diastolic_trend = health_data['reading_trends'].get('diastolic', 'Unknown')
        
        prompt += f"""
BLOOD PRESSURE DATA:
- Latest Reading: {latest_bp.get('systolic', 'N/A')}/{latest_bp.get('diastolic', 'N/A')} mmHg ({latest_bp['timestamp']})
- Average Value: {avg_systolic:.1f}/{avg_diastolic:.1f} mmHg
- Abnormal Readings: {abnormal_bp} out of {len(bp_readings)}
- Systolic Trend: {systolic_trend.title() if systolic_trend else 'Insufficient data'}
- Diastolic Trend: {diastolic_trend.title() if diastolic_trend else 'Insufficient data'}
"""

    # Add Heart Rate Data
    hr_readings = health_data['readings']['heart_rate']
    if hr_readings:
        latest_hr = hr_readings[0]
        avg_hr = sum(r['value'] for r in hr_readings) / len(hr_readings)
        abnormal_hr = sum(1 for r in hr_readings if r['is_abnormal'])
        
        hr_trend = health_data['reading_trends'].get('heart_rate', 'Unknown')
        
        prompt += f"""
HEART RATE DATA:
- Latest Reading: {latest_hr['value']} {latest_hr['unit']} ({latest_hr['timestamp']})
- Average Value: {avg_hr:.1f} {latest_hr['unit']}
- Abnormal Readings: {abnormal_hr} out of {len(hr_readings)}
- Trend: {hr_trend.title() if hr_trend else 'Insufficient data for trend analysis'}
"""

    # Add Weight Data
    weight_readings = health_data['readings']['weight']
    if weight_readings:
        latest_weight = weight_readings[0]
        weight_trend = health_data['reading_trends'].get('weight', 'Unknown')
        
        prompt += f"""
WEIGHT DATA:
- Latest Reading: {latest_weight['value']} {latest_weight['unit']} ({latest_weight['timestamp']})
- Trend: {weight_trend.title() if weight_trend else 'Insufficient data for trend analysis'}
"""

    # Add Questionnaire Data if available for this condition
    if 'questionnaires' in health_data and condition in health_data['questionnaires']:
        questionnaire = health_data['questionnaires'][condition]
        prompt += f"\nQUESTIONNAIRE RESPONSES (completed on {questionnaire['completed_at']}):\n"
        for response in questionnaire['responses']:
            prompt += f"- Question: {response['question']}\n"
            prompt += f"  Answer: {response['answer']}\n"

    # Condition-specific instructions
    if condition.lower() == 'diabetes':
        prompt += """
TASK: Based on the above data, please provide:
1. A diabetes risk assessment score from 0-100 (where 0 is lowest risk and 100 is highest risk)
2. The key contributing factors to this patient's diabetes risk
3. A detailed assessment of their current health status related to diabetes risk
4. Specific, actionable recommendations for reducing their diabetes risk

FORMAT YOUR RESPONSE AS:
Risk Score: [0-100]
Key Factors: [List 3-5 primary factors contributing to risk]
Assessment: [Detailed assessment of current health status]
Recommendations: [Specific, actionable advice for risk reduction]
"""
    elif condition.lower() == 'hypertension':
        prompt += """
TASK: Based on the above data, please provide:
1. A hypertension risk assessment score from 0-100 (where 0 is lowest risk and 100 is highest risk)
2. The key contributing factors to this patient's hypertension risk
3. A detailed assessment of their current blood pressure status
4. Specific, actionable recommendations for blood pressure management

FORMAT YOUR RESPONSE AS:
Risk Score: [0-100]
Key Factors: [List 3-5 primary factors contributing to risk]
Assessment: [Detailed assessment of current blood pressure status]
Recommendations: [Specific, actionable advice for blood pressure management]
"""
    elif condition.lower() == 'cardiovascular':
        prompt += """
TASK: Based on the above data, please provide:
1. A cardiovascular disease risk assessment score from 0-100 (where 0 is lowest risk and 100 is highest risk)
2. The key contributing factors to this patient's cardiovascular risk
3. A detailed assessment of their current heart health
4. Specific, actionable recommendations for heart health improvement

FORMAT YOUR RESPONSE AS:
Risk Score: [0-100]
Key Factors: [List 3-5 primary factors contributing to risk]
Assessment: [Detailed assessment of current heart health]
Recommendations: [Specific, actionable advice for heart health improvement]
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
    # Extract risk score
    risk_score_match = re.search(r'Risk Score:\s*(\d+)', response_text)
    risk_score = int(risk_score_match.group(1)) if risk_score_match else 50
    
    # Ensure risk score is within 0-100
    risk_score = max(0, min(100, risk_score))
    
    # Extract key factors
    key_factors_match = re.search(r'Key Factors:(.*?)(?:Assessment:|$)', response_text, re.DOTALL)
    key_factors_text = key_factors_match.group(1).strip() if key_factors_match else ""
    
    # Process into a list
    key_factors = []
    for line in key_factors_text.split("\n"):
        cleaned_line = line.strip().lstrip("*-").strip()
        if cleaned_line:
            key_factors.append(cleaned_line)
    
    # Extract assessment
    assessment_match = re.search(r'Assessment:(.*?)(?:Recommendations:|$)', response_text, re.DOTALL)
    assessment = assessment_match.group(1).strip() if assessment_match else ""
    
    # Extract recommendations
    recommendations_match = re.search(r'Recommendations:(.*?)(?:$)', response_text, re.DOTALL)
    recommendations_text = recommendations_match.group(1).strip() if recommendations_match else ""
    
    # Process into a list
    recommendations = []
    for line in recommendations_text.split("\n"):
        cleaned_line = line.strip().lstrip("*-").strip()
        if cleaned_line:
            recommendations.append(cleaned_line)
    
    return (risk_score, key_factors, assessment, recommendations)


def generate_rule_based_prediction(health_data, condition):
    """
    Generate a fallback prediction using a rule-based approach when AI is unavailable.
    This is a simple heuristic model based on health data readings.
    
    Args:
        health_data: Dictionary containing patient health data
        condition: Type of condition (diabetes, hypertension, cardiovascular)
        
    Returns:
        Tuple of (risk_score, key_factors, assessment, recommendations)
    """
    if not health_data:
        return (50, ["Insufficient data"], "Unable to provide detailed assessment due to limited data.", 
                ["Consult with your healthcare provider for a professional evaluation."])
    
    # Default values
    risk_score = 50
    key_factors = []
    assessment = "This is a basic assessment based on your health readings."
    recommendations = [
        "Maintain a balanced diet",
        "Exercise regularly",
        "Get regular check-ups with your healthcare provider"
    ]
    
    # Basic risk calculation based on abnormal readings
    abnormal_count = health_data.get('abnormal_readings_count', 0)
    total_readings = health_data.get('metadata', {}).get('total_readings_count', 0)
    
    # Age risk factor
    age = health_data.get('patient_info', {}).get('age')
    if age:
        if age > 65:
            risk_score += 15
            key_factors.append(f"Advanced age ({age} years)")
        elif age > 50:
            risk_score += 10
            key_factors.append(f"Age over 50 ({age} years)")
    
    # Readings risk factors
    if total_readings > 0:
        abnormal_percent = (abnormal_count / total_readings) * 100
        if abnormal_percent > 30:
            risk_score += 20
            key_factors.append(f"High percentage of abnormal readings ({abnormal_percent:.1f}%)")
        elif abnormal_percent > 10:
            risk_score += 10
            key_factors.append(f"Moderate percentage of abnormal readings ({abnormal_percent:.1f}%)")
    
    # Condition-specific risk factors
    if condition == 'diabetes':
        # Check blood glucose readings
        bg_readings = health_data.get('readings', {}).get('blood_glucose', [])
        if bg_readings:
            avg_bg = sum(r['value'] for r in bg_readings) / len(bg_readings)
            if avg_bg > 180:
                risk_score += 25
                key_factors.append(f"Elevated average blood glucose ({avg_bg:.1f} mg/dL)")
            elif avg_bg > 140:
                risk_score += 15
                key_factors.append(f"Moderately elevated blood glucose ({avg_bg:.1f} mg/dL)")
                
            assessment = f"Based on your average blood glucose level of {avg_bg:.1f} mg/dL and other factors, "
            if avg_bg > 180:
                assessment += "your diabetes risk appears to be elevated. Consistently high blood glucose readings may indicate poor glycemic control."
            elif avg_bg > 140:
                assessment += "your diabetes risk appears to be moderate. Your glucose readings show room for improvement."
            else:
                assessment += "your diabetes risk appears to be relatively controlled based on your readings."
                
            # Add diabetes-specific recommendations
            recommendations = [
                "Monitor your blood glucose regularly",
                "Limit intake of refined carbohydrates and sugars",
                "Stay physically active to help manage blood glucose levels",
                "Consult with your healthcare provider about your diabetes management plan"
            ]
            
    elif condition == 'hypertension':
        # Check blood pressure readings
        bp_readings = health_data.get('readings', {}).get('blood_pressure', [])
        if bp_readings:
            # Extract systolic and diastolic values
            systolic_values = [r.get('systolic') for r in bp_readings if r.get('systolic') is not None]
            diastolic_values = [r.get('diastolic') for r in bp_readings if r.get('diastolic') is not None]
            
            if systolic_values:
                avg_systolic = sum(systolic_values) / len(systolic_values)
                if avg_systolic > 140:
                    risk_score += 25
                    key_factors.append(f"Elevated average systolic BP ({avg_systolic:.1f} mmHg)")
                elif avg_systolic > 130:
                    risk_score += 15
                    key_factors.append(f"Moderately elevated systolic BP ({avg_systolic:.1f} mmHg)")
            
            if diastolic_values:
                avg_diastolic = sum(diastolic_values) / len(diastolic_values)
                if avg_diastolic > 90:
                    risk_score += 25
                    key_factors.append(f"Elevated average diastolic BP ({avg_diastolic:.1f} mmHg)")
                elif avg_diastolic > 80:
                    risk_score += 15
                    key_factors.append(f"Moderately elevated diastolic BP ({avg_diastolic:.1f} mmHg)")
                    
            if systolic_values and diastolic_values:
                assessment = f"Based on your average blood pressure of {avg_systolic:.1f}/{avg_diastolic:.1f} mmHg, "
                if avg_systolic > 140 or avg_diastolic > 90:
                    assessment += "your hypertension risk appears to be elevated. Consistently high blood pressure readings may increase your risk of cardiovascular complications."
                elif avg_systolic > 130 or avg_diastolic > 80:
                    assessment += "your hypertension risk appears to be moderate. Your blood pressure readings show room for improvement."
                else:
                    assessment += "your blood pressure appears to be within a healthier range based on your readings."
                
            # Add hypertension-specific recommendations
            recommendations = [
                "Monitor your blood pressure regularly",
                "Reduce sodium intake in your diet",
                "Maintain a healthy weight through diet and exercise",
                "Avoid excessive alcohol consumption",
                "Practice stress-management techniques"
            ]
            
    elif condition == 'cardiovascular':
        # Combined BP and HR assessment
        bp_readings = health_data.get('readings', {}).get('blood_pressure', [])
        hr_readings = health_data.get('readings', {}).get('heart_rate', [])
        
        cv_factors = []
        
        if bp_readings:
            systolic_values = [r.get('systolic') for r in bp_readings if r.get('systolic') is not None]
            if systolic_values:
                avg_systolic = sum(systolic_values) / len(systolic_values)
                if avg_systolic > 140:
                    risk_score += 20
                    cv_factors.append(f"Elevated systolic BP ({avg_systolic:.1f} mmHg)")
        
        if hr_readings:
            avg_hr = sum(r['value'] for r in hr_readings) / len(hr_readings)
            if avg_hr > 100:
                risk_score += 15
                cv_factors.append(f"Elevated resting heart rate ({avg_hr:.1f} bpm)")
        
        if cv_factors:
            key_factors.extend(cv_factors)
            
        assessment = "Based on your cardiovascular health indicators, "
        if risk_score > 70:
            assessment += "your cardiovascular risk appears to be elevated. Several risk factors have been identified that may increase your risk of heart disease."
        elif risk_score > 50:
            assessment += "your cardiovascular risk appears to be moderate. Some risk factors have been identified that could be addressed to improve your heart health."
        else:
            assessment += "your cardiovascular risk appears to be relatively lower based on available readings."
            
        # Add cardiovascular-specific recommendations
        recommendations = [
            "Maintain a heart-healthy diet rich in fruits, vegetables, and whole grains",
            "Exercise regularly, aiming for at least 150 minutes of moderate activity per week",
            "Monitor your blood pressure and cholesterol levels",
            "Avoid smoking and limit alcohol consumption",
            "Manage stress through relaxation techniques"
        ]
    
    # Ensure risk score is within 0-100 range
    risk_score = max(0, min(100, risk_score))
    
    # Limit to 5 key factors max
    key_factors = key_factors[:5]
    
    return (risk_score, key_factors, assessment, recommendations)


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
        # Get patient health data first (needed for either approach)
        health_data = get_patient_health_data(patient_id)
        if not health_data:
            return {
                "error": "Could not retrieve patient health data."
            }
        
        use_ai_model = True
        ai_error = None
        
        # Try to configure Gemini API
        if not configure_genai():
            current_app.logger.warning("Gemini API configuration failed. Falling back to rule-based prediction.")
            use_ai_model = False
            ai_error = "Gemini API configuration failed. Using rule-based prediction instead."
        
        # Variables to store prediction results
        risk_score = 0
        key_factors = []
        assessment = ""
        recommendations = []
        
        if use_ai_model:
            try:
                # Generate prompt
                prompt = generate_prediction_prompt(health_data, condition)
                
                # Try gemini-1.5-pro first
                try:
                    model = genai.GenerativeModel('gemini-1.5-pro')
                    response = model.generate_content(prompt)
                except Exception as model_error:
                    current_app.logger.error(f"Error with gemini-1.5-pro model: {str(model_error)}")
                    # Fall back to gemini-pro
                    try:
                        model = genai.GenerativeModel('gemini-pro')
                        response = model.generate_content(prompt)
                    except Exception as fallback_error:
                        current_app.logger.error(f"Error with fallback model: {str(fallback_error)}")
                        # If both models fail, use rule-based approach
                        raise Exception(f"Failed to generate content with any available Gemini model: {str(model_error)}")
                
                # Process AI response
                response_text = response.text
                risk_score, key_factors, assessment, recommendations = extract_risk_score_from_response(response_text)
                
            except Exception as e:
                current_app.logger.error(f"Error using Gemini AI model: {str(e)}")
                use_ai_model = False
                ai_error = f"AI prediction failed: {str(e)}. Using rule-based prediction instead."
        
        # If AI approach failed, use rule-based approach
        if not use_ai_model:
            current_app.logger.info(f"Using rule-based prediction for {condition}")
            risk_score, key_factors, assessment, recommendations = generate_rule_based_prediction(health_data, condition)
        
        # Convert key factors and recommendations to JSON strings for database storage
        key_factors_json = json.dumps(key_factors)
        recommendations_json = json.dumps(recommendations)
        
        # Save to database if requested
        if save_to_db:
            # Find or create prediction model
            model_name = f"{condition.title()} Risk Model"
            pred_model = PredictionModel.query.filter_by(
                name=model_name,
                target_condition=condition
            ).first()
            
            if not pred_model:
                pred_model = PredictionModel(
                    name=model_name,
                    description=f"Risk assessment model for {condition}",
                    model_type="classification",
                    target_condition=condition,
                    is_active=True
                )
                db.session.add(pred_model)
                db.session.flush()
            
            # Create prediction record
            prediction = Prediction(
                model_id=pred_model.id,
                patient_id=patient_id,
                prediction_value=risk_score,
                confidence=0.85 if use_ai_model else 0.70,  # Lower confidence for rule-based
                timestamp=datetime.utcnow(),
                notes=f"Generated using {'Gemini AI' if use_ai_model else 'rule-based'} model",
                key_factors=key_factors_json,
                recommendations=recommendations_json,
                assessment=assessment,
                condition=condition
            )
            
            db.session.add(prediction)
            db.session.commit()
        
        # Return prediction results
        result = {
            "risk_score": risk_score,
            "key_factors": key_factors,
            "assessment": assessment,
            "recommendations": recommendations,
            "condition": condition,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add a note if we used the fallback approach
        if not use_ai_model:
            result["note"] = ai_error
            
        return result
        
    except Exception as e:
        current_app.logger.error(f"Error in predict_disease_risk: {str(e)}")
        return {
            "error": f"Prediction failed: {str(e)}"
        }