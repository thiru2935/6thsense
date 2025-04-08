"""
Advanced ML-based Treatment Recommendations Service
This service provides personalized treatment recommendations based on patient data and ML models.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from flask import current_app
from app import db
from models import (
    PatientProfile, 
    HealthReading, 
    Medication,
    Prediction,
    TreatmentRecommendation
)

from services.ai_predictions import configure_genai, get_patient_health_data
import google.generativeai as genai

def generate_treatment_recommendation(patient_id, condition):
    """
    Generate personalized treatment recommendations for a specific patient's condition
    
    Args:
        patient_id: ID of the patient
        condition: Type of condition (diabetes, hypertension, cardiovascular)
        
    Returns:
        Dictionary with recommendation results or error
    """
    try:
        # Get comprehensive patient health data
        health_data = get_patient_health_data(patient_id)
        if not health_data:
            return {
                "error": "Could not retrieve patient health data for treatment recommendations."
            }
        
        # Get existing predictions for this condition
        patient_predictions = Prediction.query.filter_by(
            patient_id=patient_id,
            condition=condition
        ).order_by(Prediction.timestamp.desc()).first()
        
        if not patient_predictions:
            return {
                "error": f"No risk predictions available for {condition}. Please generate a prediction first."
            }
        
        # Get patient's current medications
        patient = PatientProfile.query.get(patient_id)
        current_medications = Medication.query.filter_by(
            patient_id=patient_id, 
            is_active=True
        ).all()
        
        medication_list = [
            {
                "name": med.name,
                "dosage": med.dosage,
                "frequency": med.frequency,
                "instructions": med.instructions
            } for med in current_medications
        ]
        
        # Configure GenAI
        use_ai_model = True
        if not configure_genai():
            current_app.logger.warning("Gemini API configuration failed. Using rule-based treatment recommendations.")
            use_ai_model = False
            
        recommendations = []
            
        if use_ai_model:
            try:
                # Build prompt for treatment recommendations
                prompt = _build_treatment_recommendation_prompt(
                    health_data, 
                    condition,
                    patient_predictions,
                    medication_list
                )
                
                # Try different Gemini models in order of preference
                response = None
                model_error = None
                
                model_preferences = [
                    'gemini-1.5-pro',
                    'gemini-pro',
                    'gemini-1.0-pro',
                    'models/gemini-1.5-pro',
                    'models/gemini-pro'
                ]
                
                # Try each model in order until one works
                for model_name in model_preferences:
                    try:
                        current_app.logger.info(f"Trying model for treatment recommendations: {model_name}")
                        model = genai.GenerativeModel(model_name)
                        response = model.generate_content(prompt)
                        current_app.logger.info(f"Successfully used model: {model_name}")
                        break  # Exit the loop if successful
                    except Exception as err:
                        model_error = err
                        current_app.logger.error(f"Error with {model_name} model: {str(err)}")
                        continue  # Try the next model
                
                # If all models failed, use rule-based approach
                if response is None:
                    raise Exception(f"Failed to generate content with any available Gemini model. Last error: {str(model_error)}")
                
                # Process the AI response into structured recommendations
                recommendations = _process_treatment_recommendations(response.text, condition)
                
            except Exception as e:
                current_app.logger.error(f"Error generating AI treatment recommendations: {str(e)}")
                use_ai_model = False
        
        # If AI approach failed, use rule-based recommendations
        if not use_ai_model:
            current_app.logger.info(f"Using rule-based treatment recommendations for {condition}")
            recommendations = _generate_rule_based_recommendations(health_data, condition, medication_list)
        
        # Save treatment recommendations to database
        saved_recommendations = []
        
        for rec in recommendations:
            # Create recommendation record
            treatment_rec = TreatmentRecommendation(
                patient_id=patient_id,
                condition=condition,
                recommendation_type=rec['type'],
                title=rec['title'],
                content=rec['description'],
                evidence_level=rec.get('evidence_level', 'moderate'),
                confidence_score=rec.get('confidence', 0.75 if use_ai_model else 0.6),
                created_at=datetime.utcnow(),
                is_active=True,
                is_viewed=False
            )
            
            # Set model parameters
            treatment_rec.set_parameters({
                "model_used": "Gemini AI" if use_ai_model else "Rule-based",
                "health_metrics": {k: v for k, v in health_data.items() if k in ['average_glucose', 'avg_systolic', 'avg_diastolic', 'bmi']},
                "condition": condition
            })
            
            db.session.add(treatment_rec)
            saved_recommendations.append(treatment_rec)
        
        db.session.commit()
        
        # Return the created recommendations
        return {
            "success": True,
            "recommendations": [
                {
                    "id": rec.id,
                    "type": rec.recommendation_type,
                    "title": rec.title,
                    "description": rec.content,
                    "evidence_level": rec.evidence_level,
                    "confidence": rec.confidence_score
                } for rec in saved_recommendations
            ],
            "ai_powered": use_ai_model,
            "count": len(saved_recommendations)
        }
        
    except Exception as e:
        current_app.logger.error(f"Error in generate_treatment_recommendation: {str(e)}")
        return {
            "error": f"Failed to generate treatment recommendations: {str(e)}"
        }


def _build_treatment_recommendation_prompt(health_data, condition, prediction, medications):
    """
    Create a structured prompt for the Gemini model to generate treatment recommendations
    
    Args:
        health_data: Dictionary containing patient health data
        condition: Target condition (diabetes, hypertension, cardiovascular)
        prediction: Risk prediction model result 
        medications: List of patient's current medications
        
    Returns:
        Formatted prompt string
    """
    # Build intro based on condition
    if condition == 'diabetes':
        intro = "As an AI medical assistant, provide personalized diabetes management recommendations"
    elif condition == 'hypertension':
        intro = "As an AI medical assistant, provide personalized hypertension management recommendations"
    elif condition == 'cardiovascular':
        intro = "As an AI medical assistant, provide personalized cardiovascular disease management recommendations"
    else:
        intro = f"As an AI medical assistant, provide personalized health recommendations for {condition}"
    
    # Add patient info
    patient_info = f"""
PATIENT INFORMATION:
- Age: {health_data.get('age', 'unknown')}
- Gender: {health_data.get('gender', 'unknown')}
- BMI: {health_data.get('bmi', 'unknown')}
- Risk score: {prediction.prediction_value}/100 for {condition}
"""

    # Add health metrics
    health_metrics = "HEALTH METRICS:\n"
    
    if condition == 'diabetes':
        health_metrics += f"- Average blood glucose: {health_data.get('average_glucose', 'unknown')} mg/dL\n"
        health_metrics += f"- Last HbA1c: {health_data.get('last_hba1c', 'unknown')}\n"
    elif condition == 'hypertension' or condition == 'cardiovascular':
        health_metrics += f"- Average blood pressure: {health_data.get('avg_systolic', 'unknown')}/{health_data.get('avg_diastolic', 'unknown')} mmHg\n"
        health_metrics += f"- Average pulse: {health_data.get('avg_pulse', 'unknown')} BPM\n"
    
    # Add current medications
    meds_text = "CURRENT MEDICATIONS:\n"
    if medications:
        for med in medications:
            meds_text += f"- {med['name']} {med['dosage']}, {med['frequency']}\n"
    else:
        meds_text += "- No current medications recorded\n"
    
    # Output instructions
    output_instructions = f"""
Based on this information, provide 4-6 evidence-based recommendations for managing {condition}. For each recommendation:
1. Provide a concise title (e.g., "Increase Aerobic Exercise")
2. Provide a detailed description with specific actions
3. Include the type (medication, lifestyle, diet, exercise, monitoring)
4. Include evidence level (strong, moderate, limited)
5. Include a confidence score between 0 and 1

Format each recommendation as:
{{
  "title": "Title here",
  "description": "Detailed recommendation here",
  "type": "type here",
  "evidence_level": "level here",
  "confidence": confidence_score
}}

Return a JSON array of recommendations like this:
[
  {{recommendation1}},
  {{recommendation2}},
  ...
]
"""
    
    # Combine all parts
    full_prompt = f"{intro}\n\n{patient_info}\n{health_metrics}\n{meds_text}\n{output_instructions}"
    return full_prompt


def _process_treatment_recommendations(response_text, condition):
    """
    Process and extract the recommendations from the Gemini AI response
    
    Args:
        response_text: The response text from the AI model
        condition: The target condition
        
    Returns:
        List of recommendation dictionaries
    """
    try:
        # Extract JSON array from the response (the AI might include explanatory text)
        json_str = response_text
        
        # Find the beginning of the JSON array
        start_index = response_text.find('[')
        if start_index == -1:
            # Try with triple backticks for code block
            code_start = response_text.find('```json')
            if code_start != -1:
                code_start = response_text.find('[', code_start)
                code_end = response_text.find('```', code_start)
                if code_start != -1 and code_end != -1:
                    json_str = response_text[code_start:code_end].strip()
            else:
                # No JSON array found, handle the error
                raise ValueError("Could not find JSON array in response")
        else:
            # Find the matching closing bracket
            open_brackets = 0
            for i, char in enumerate(response_text[start_index:]):
                if char == '[':
                    open_brackets += 1
                elif char == ']':
                    open_brackets -= 1
                    if open_brackets == 0:
                        json_str = response_text[start_index:start_index + i + 1]
                        break
        
        # Parse the JSON array
        recommendations = json.loads(json_str)
        
        # Validate and clean the recommendations
        valid_recommendations = []
        for rec in recommendations:
            # Ensure all required fields are present
            if not all(k in rec for k in ['title', 'description', 'type']):
                continue
                
            # Normalize the recommendation type
            rec_type = rec['type'].lower()
            if 'medic' in rec_type:
                rec_type = 'medication'
            elif 'life' in rec_type:
                rec_type = 'lifestyle'
            elif 'diet' in rec_type or 'nutri' in rec_type:
                rec_type = 'diet'
            elif 'exer' in rec_type:
                rec_type = 'exercise'
            elif 'moni' in rec_type:
                rec_type = 'monitoring'
            else:
                rec_type = 'other'
                
            # Normalize evidence level
            evidence = rec.get('evidence_level', 'moderate').lower()
            if 'strong' in evidence:
                evidence = 'strong'
            elif 'limit' in evidence or 'weak' in evidence:
                evidence = 'limited'
            else:
                evidence = 'moderate'
                
            # Ensure confidence is a float between 0 and 1
            confidence = float(rec.get('confidence', 0.7))
            confidence = max(0.0, min(1.0, confidence))
            
            # Add the cleaned recommendation
            valid_recommendations.append({
                'title': rec['title'],
                'description': rec['description'],
                'type': rec_type,
                'evidence_level': evidence,
                'confidence': confidence
            })
        
        return valid_recommendations
        
    except Exception as e:
        current_app.logger.error(f"Error processing treatment recommendations: {str(e)}")
        # Return empty list, will trigger rule-based recommendations
        return []


def _generate_rule_based_recommendations(health_data, condition, medications):
    """
    Generate rule-based treatment recommendations when AI is not available
    
    Args:
        health_data: Dictionary with patient health data
        condition: Target condition (diabetes, hypertension, cardiovascular)
        medications: List of current medications
        
    Returns:
        List of recommendation dictionaries
    """
    recommendations = []
    
    # Common recommendation for all conditions
    recommendations.append({
        'title': 'Regular Physical Activity',
        'description': 'Aim for at least 150 minutes of moderate-intensity aerobic activity per week, spread across at least 3 days. Include strength training exercises twice a week.',
        'type': 'exercise',
        'evidence_level': 'strong',
        'confidence': 0.9
    })
    
    recommendations.append({
        'title': 'Balanced Diet',
        'description': 'Focus on vegetables, fruits, whole grains, lean proteins, and healthy fats. Limit processed foods, added sugars, and sodium.',
        'type': 'diet',
        'evidence_level': 'strong',
        'confidence': 0.9
    })
    
    # Condition-specific recommendations
    if condition == 'diabetes':
        # Check if glucose is high
        avg_glucose = health_data.get('average_glucose', 0)
        if avg_glucose > 180:
            recommendations.append({
                'title': 'Blood Glucose Monitoring',
                'description': 'Monitor your blood glucose more frequently, aiming for 3-4 times daily. Keep a log to identify patterns and share with your healthcare provider.',
                'type': 'monitoring',
                'evidence_level': 'strong',
                'confidence': 0.85
            })
            
        recommendations.append({
            'title': 'Carbohydrate Management',
            'description': 'Count carbohydrates and maintain consistent carb intake at each meal. Focus on complex carbohydrates with low glycemic index.',
            'type': 'diet',
            'evidence_level': 'moderate',
            'confidence': 0.8
        })
        
    elif condition == 'hypertension':
        # Check if blood pressure is high
        systolic = health_data.get('avg_systolic', 0)
        diastolic = health_data.get('avg_diastolic', 0)
        
        if systolic > 140 or diastolic > 90:
            recommendations.append({
                'title': 'DASH Diet Approach',
                'description': 'Follow the DASH (Dietary Approaches to Stop Hypertension) diet, which emphasizes fruits, vegetables, whole grains, lean proteins, and limits sodium to 1,500-2,300 mg per day.',
                'type': 'diet',
                'evidence_level': 'strong',
                'confidence': 0.9
            })
        
        recommendations.append({
            'title': 'Regular Blood Pressure Monitoring',
            'description': 'Monitor your blood pressure daily, preferably at the same time. Keep a log to track patterns and share with your healthcare provider.',
            'type': 'monitoring',
            'evidence_level': 'moderate',
            'confidence': 0.8
        })
        
    elif condition == 'cardiovascular':
        recommendations.append({
            'title': 'Heart-Healthy Nutrition',
            'description': 'Emphasize a Mediterranean-style diet rich in olive oil, nuts, fish, fruits, vegetables, and whole grains. Limit red meat and foods high in saturated fats.',
            'type': 'diet',
            'evidence_level': 'strong',
            'confidence': 0.85
        })
        
        recommendations.append({
            'title': 'Cardiac Rehabilitation',
            'description': 'Consider participating in a cardiac rehabilitation program which includes supervised exercise, education, and counseling to improve heart health.',
            'type': 'lifestyle',
            'evidence_level': 'strong',
            'confidence': 0.8
        })
    
    # Common recommendations for all conditions
    recommendations.append({
        'title': 'Stress Management',
        'description': 'Practice stress-reduction techniques such as mindfulness meditation, deep breathing exercises, or yoga. Chronic stress can worsen many health conditions.',
        'type': 'lifestyle',
        'evidence_level': 'moderate',
        'confidence': 0.75
    })
    
    recommendations.append({
        'title': 'Adequate Sleep',
        'description': 'Aim for 7-9 hours of quality sleep each night. Establish a regular sleep schedule and create a restful environment.',
        'type': 'lifestyle',
        'evidence_level': 'moderate',
        'confidence': 0.75
    })
    
    return recommendations