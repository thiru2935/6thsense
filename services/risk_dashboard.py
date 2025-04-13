"""
Interactive Risk Dashboard Service
Provides advanced risk factor analysis for the interactive risk dashboard
"""

import json
import logging
from datetime import datetime, timedelta
from flask import current_app
from app import db
from models import (
    PatientProfile, 
    HealthReading, 
    Prediction, 
    RiskFactorInteraction,
    HealthQuestionnaire,
    QuestionnaireResponse
)


def generate_risk_factors(prediction_id):
    """
    Generate detailed risk factor interactions for a prediction
    
    Args:
        prediction_id: ID of the prediction to analyze
        
    Returns:
        Dictionary with risk factor analysis results
    """
    try:
        # Get the prediction
        prediction = Prediction.query.get(prediction_id)
        if not prediction:
            return {"error": "Prediction not found"}
        
        # Get patient data
        patient = PatientProfile.query.get(prediction.patient_id)
        if not patient:
            return {"error": "Patient not found"}
        
        # Get recent health readings
        recent_date = datetime.utcnow() - timedelta(days=90)
        readings = HealthReading.query.filter_by(
            patient_id=patient.id
        ).filter(
            HealthReading.timestamp > recent_date
        ).all()
        
        # Organize readings by type
        readings_by_type = {}
        for reading in readings:
            if reading.reading_type not in readings_by_type:
                readings_by_type[reading.reading_type] = []
            readings_by_type[reading.reading_type].append(reading)
        
        # Get questionnaire responses
        questionnaires = HealthQuestionnaire.query.filter_by(
            patient_id=patient.id,
            condition=prediction.condition
        ).order_by(
            HealthQuestionnaire.completed_at.desc()
        ).first()
        
        questionnaire_data = {}
        if questionnaires:
            responses = QuestionnaireResponse.query.filter_by(
                questionnaire_id=questionnaires.id
            ).all()
            
            for response in responses:
                questionnaire_data[response.question.question_text] = response.response_text
        
        # Define risk factors based on condition
        risk_factors = []
        
        if prediction.condition == 'diabetes':
            risk_factors = _analyze_diabetes_risk_factors(
                patient, 
                prediction, 
                readings_by_type, 
                questionnaire_data
            )
        elif prediction.condition == 'hypertension':
            risk_factors = _analyze_hypertension_risk_factors(
                patient, 
                prediction, 
                readings_by_type, 
                questionnaire_data
            )
        elif prediction.condition == 'cardiovascular':
            risk_factors = _analyze_cardiovascular_risk_factors(
                patient, 
                prediction, 
                readings_by_type, 
                questionnaire_data
            )
        
        # Save risk factors to database
        saved_factors = []
        for factor in risk_factors:
            # Create risk factor record
            risk_factor = RiskFactorInteraction(
                patient_id=patient.id,
                prediction_id=prediction.id,
                risk_factor=factor['name'],
                current_value=factor['current_value'],
                ideal_value=factor['ideal_value'],
                impact_score=factor['impact_score'],
                recommendations=json.dumps(factor['recommendations'])
            )
            db.session.add(risk_factor)
            saved_factors.append(risk_factor)
        
        db.session.commit()
        
        # Return analysis results
        return {
            "success": True,
            "prediction_value": prediction.prediction_value,
            "condition": prediction.condition,
            "risk_factors": [
                {
                    "id": factor.id,
                    "name": factor.risk_factor,
                    "current_value": factor.current_value,
                    "ideal_value": factor.ideal_value,
                    "impact_score": factor.impact_score,
                    "recommendations": factor.get_recommendations()
                } for factor in saved_factors
            ],
            "count": len(saved_factors)
        }
        
    except Exception as e:
        current_app.logger.error(f"Error generating risk factors: {str(e)}")
        return {"error": f"Failed to generate risk factors: {str(e)}"}


def get_risk_dashboard_data(patient_id, condition):
    """
    Get comprehensive data for the interactive risk dashboard
    
    Args:
        patient_id: ID of the patient
        condition: Target condition (diabetes, hypertension, cardiovascular)
        
    Returns:
        Dictionary with dashboard data
    """
    try:
        # Get most recent prediction
        prediction = Prediction.query.filter_by(
            patient_id=patient_id,
            condition=condition
        ).order_by(
            Prediction.timestamp.desc()
        ).first()
        
        if not prediction:
            return {
                "error": f"No prediction found for {condition}. Please generate a prediction first."
            }
        
        # Get associated risk factors
        risk_factors = RiskFactorInteraction.query.filter_by(
            prediction_id=prediction.id
        ).all()
        
        # If no risk factors exist, generate them
        if not risk_factors:
            result = generate_risk_factors(prediction.id)
            if "error" in result:
                return result
                
            # Get newly created risk factors
            risk_factors = RiskFactorInteraction.query.filter_by(
                prediction_id=prediction.id
            ).all()
        
        # Get historical predictions
        historical_predictions = Prediction.query.filter_by(
            patient_id=patient_id,
            condition=condition
        ).order_by(
            Prediction.timestamp
        ).all()
        
        history_data = [
            {
                "date": pred.timestamp.strftime("%Y-%m-%d"),
                "value": pred.prediction_value
            } for pred in historical_predictions
        ]
        
        # Format risk factors for visualization
        formatted_factors = [
            {
                "id": factor.id,
                "name": _format_factor_name(factor.risk_factor),
                "current_value": factor.current_value,
                "ideal_value": factor.ideal_value,
                "impact_score": factor.impact_score,
                "percentage_of_ideal": _calculate_percentage_of_ideal(
                    factor.risk_factor, 
                    factor.current_value, 
                    factor.ideal_value
                ),
                "recommendations": factor.get_recommendations()
            } for factor in risk_factors
        ]
        
        # Sort factors by impact score (descending)
        formatted_factors.sort(key=lambda x: x["impact_score"], reverse=True)
        
        # Format prediction data
        prediction_data = {
            "id": prediction.id,
            "condition": prediction.condition,
            "value": prediction.prediction_value,
            "timestamp": prediction.timestamp.strftime("%Y-%m-%d %H:%M"),
            "details": prediction.assessment if hasattr(prediction, 'assessment') else '',
            "model_used": prediction.model_id if hasattr(prediction, 'model_id') else None
        }
        
        return {
            "success": True,
            "prediction": prediction_data,
            "risk_factors": formatted_factors,
            "history": history_data,
            "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        }
        
    except Exception as e:
        current_app.logger.error(f"Error getting risk dashboard data: {str(e)}")
        return {"error": f"Failed to get risk dashboard data: {str(e)}"}


def _analyze_diabetes_risk_factors(patient, prediction, readings_by_type, questionnaire_data):
    """
    Analyze risk factors specific to diabetes
    
    Returns:
        List of risk factor dictionaries
    """
    risk_factors = []
    
    # Blood glucose factor
    if 'glucose' in readings_by_type and readings_by_type['glucose']:
        glucose_readings = readings_by_type['glucose']
        avg_glucose = sum(r.value for r in glucose_readings) / len(glucose_readings)
        
        # Determine ideal value (target range)
        ideal_glucose = 100  # mg/dL, typical target
        
        # Calculate impact score (higher for values far from ideal)
        glucose_impact = min(100, abs(avg_glucose - ideal_glucose) * 0.5)
        
        # Adjust based on prediction value
        glucose_impact = glucose_impact * (prediction.prediction_value / 100)
        
        recommendations = [
            "Monitor blood glucose levels regularly",
            "Follow a balanced diet with controlled carbohydrate intake",
            "Stay hydrated and maintain physical activity"
        ]
        
        if avg_glucose > 180:
            recommendations.append("Consider discussing medication adjustments with your doctor")
        
        risk_factors.append({
            "name": "blood_glucose",
            "current_value": avg_glucose,
            "ideal_value": ideal_glucose,
            "impact_score": glucose_impact,
            "recommendations": recommendations
        })
    
    # BMI factor
    if patient.weight and patient.height and patient.height > 0:
        bmi = (patient.weight / ((patient.height/100) ** 2))
        ideal_bmi = 24  # Middle of healthy range
        
        # Calculate impact
        bmi_impact = 0
        if bmi >= 30:  # Obese
            bmi_impact = 80
        elif bmi >= 25:  # Overweight
            bmi_impact = 50
        elif bmi < 18.5:  # Underweight
            bmi_impact = 30
        else:  # Healthy range
            bmi_impact = max(0, (abs(bmi - ideal_bmi) * 10))
        
        # Adjust based on prediction value
        bmi_impact = bmi_impact * (prediction.prediction_value / 100)
        
        recommendations = [
            "Maintain a balanced diet rich in vegetables and lean proteins",
            "Engage in regular physical activity"
        ]
        
        if bmi >= 30:
            recommendations.append("Consider working with a dietitian on a weight management plan")
        elif bmi >= 25:
            recommendations.append("Focus on portion control and increased activity levels")
        
        risk_factors.append({
            "name": "body_mass_index",
            "current_value": bmi,
            "ideal_value": ideal_bmi,
            "impact_score": bmi_impact,
            "recommendations": recommendations
        })
    
    # Physical activity factor (from questionnaire)
    activity_level = None
    for question, answer in questionnaire_data.items():
        if "physical activity" in question.lower() or "exercise" in question.lower():
            activity_level = answer
            break
    
    if activity_level:
        activity_value = 0
        if "none" in activity_level.lower() or "sedentary" in activity_level.lower():
            activity_value = 0
        elif "light" in activity_level.lower() or "1-2" in activity_level:
            activity_value = 2
        elif "moderate" in activity_level.lower() or "3-5" in activity_level:
            activity_value = 5
        elif "active" in activity_level.lower() or "daily" in activity_level.lower():
            activity_value = 7
        
        ideal_activity = 5  # Moderate activity
        
        # Calculate impact (higher for less activity)
        activity_impact = max(0, (ideal_activity - activity_value) * 15)
        
        # Adjust based on prediction value
        activity_impact = activity_impact * (prediction.prediction_value / 100)
        
        recommendations = [
            "Aim for at least 150 minutes of moderate activity per week",
            "Incorporate both cardio and strength training exercises",
            "Start with walking and gradually increase intensity"
        ]
        
        risk_factors.append({
            "name": "physical_activity",
            "current_value": activity_value,
            "ideal_value": ideal_activity,
            "impact_score": activity_impact,
            "recommendations": recommendations
        })
    
    # Family history factor (from questionnaire)
    family_history = None
    for question, answer in questionnaire_data.items():
        if "family history" in question.lower() and "diabetes" in question.lower():
            family_history = answer
            break
    
    if family_history:
        has_family_history = "yes" in family_history.lower() or "true" in family_history.lower()
        
        family_history_value = 1 if has_family_history else 0
        ideal_value = 0  # Ideally no family history, though not controllable
        
        # Calculate impact
        history_impact = 60 if has_family_history else 0
        
        # Adjust based on prediction value
        history_impact = history_impact * (prediction.prediction_value / 100)
        
        recommendations = [
            "Monitor blood glucose more frequently given family history risk",
            "Focus on modifiable risk factors like diet and exercise"
        ]
        
        risk_factors.append({
            "name": "family_history",
            "current_value": family_history_value,
            "ideal_value": ideal_value,
            "impact_score": history_impact,
            "recommendations": recommendations
        })
    
    return risk_factors


def _analyze_hypertension_risk_factors(patient, prediction, readings_by_type, questionnaire_data):
    """
    Analyze risk factors specific to hypertension
    
    Returns:
        List of risk factor dictionaries
    """
    risk_factors = []
    
    # Blood pressure factor
    if 'blood_pressure' in readings_by_type and readings_by_type['blood_pressure']:
        bp_readings = readings_by_type['blood_pressure']
        
        # Calculate average systolic and diastolic
        avg_systolic = sum(r.systolic for r in bp_readings) / len(bp_readings)
        avg_diastolic = sum(r.diastolic for r in bp_readings) / len(bp_readings)
        
        # Determine ideal values
        ideal_systolic = 120
        ideal_diastolic = 80
        
        # Calculate impact score
        systolic_impact = 0
        if avg_systolic >= 180:  # Crisis
            systolic_impact = 100
        elif avg_systolic >= 160:  # Stage 2
            systolic_impact = 80
        elif avg_systolic >= 140:  # Stage 1
            systolic_impact = 60
        elif avg_systolic >= 130:  # Elevated
            systolic_impact = 40
        elif avg_systolic >= 120:  # Normal
            systolic_impact = 10
        
        diastolic_impact = 0
        if avg_diastolic >= 120:  # Crisis
            diastolic_impact = 100
        elif avg_diastolic >= 100:  # Stage 2
            diastolic_impact = 80
        elif avg_diastolic >= 90:  # Stage 1
            diastolic_impact = 60
        elif avg_diastolic >= 80:  # Normal
            diastolic_impact = 10
        
        # Combined impact
        bp_impact = max(systolic_impact, diastolic_impact)
        
        # Adjust based on prediction value
        bp_impact = bp_impact * (prediction.prediction_value / 100)
        
        recommendations = [
            "Monitor blood pressure regularly",
            "Follow a low-sodium diet (DASH diet)",
            "Maintain regular physical activity"
        ]
        
        if avg_systolic >= 140 or avg_diastolic >= 90:
            recommendations.append("Consult with your doctor about medication options")
        
        risk_factors.append({
            "name": "blood_pressure",
            "current_value": f"{avg_systolic:.0f}/{avg_diastolic:.0f}",  # Format as systolic/diastolic
            "ideal_value": f"{ideal_systolic}/{ideal_diastolic}",
            "impact_score": bp_impact,
            "recommendations": recommendations
        })
    
    # Sodium intake factor (from questionnaire)
    sodium_intake = None
    for question, answer in questionnaire_data.items():
        if "salt" in question.lower() or "sodium" in question.lower():
            sodium_intake = answer
            break
    
    if sodium_intake:
        sodium_value = 0
        if "high" in sodium_intake.lower() or "frequent" in sodium_intake.lower():
            sodium_value = 3
        elif "moderate" in sodium_intake.lower() or "sometimes" in sodium_intake.lower():
            sodium_value = 2
        elif "low" in sodium_intake.lower() or "rarely" in sodium_intake.lower():
            sodium_value = 1
        
        ideal_sodium = 1  # Low sodium intake
        
        # Calculate impact
        sodium_impact = (sodium_value - ideal_sodium) * 25
        
        # Adjust based on prediction value
        sodium_impact = sodium_impact * (prediction.prediction_value / 100)
        
        recommendations = [
            "Reduce processed and packaged foods",
            "Use herbs and spices instead of salt for flavoring",
            "Read food labels to track sodium content"
        ]
        
        risk_factors.append({
            "name": "sodium_intake",
            "current_value": sodium_value,
            "ideal_value": ideal_sodium,
            "impact_score": sodium_impact,
            "recommendations": recommendations
        })
    
    # Stress level factor (from questionnaire)
    stress_level = None
    for question, answer in questionnaire_data.items():
        if "stress" in question.lower() or "anxiety" in question.lower():
            stress_level = answer
            break
    
    if stress_level:
        stress_value = 0
        if "high" in stress_level.lower() or "severe" in stress_level.lower():
            stress_value = 3
        elif "moderate" in stress_level.lower() or "some" in stress_level.lower():
            stress_value = 2
        elif "low" in stress_level.lower() or "minimal" in stress_level.lower():
            stress_value = 1
        
        ideal_stress = 1  # Low stress
        
        # Calculate impact
        stress_impact = (stress_value - ideal_stress) * 20
        
        # Adjust based on prediction value
        stress_impact = stress_impact * (prediction.prediction_value / 100)
        
        recommendations = [
            "Practice daily stress management techniques (meditation, deep breathing)",
            "Ensure adequate sleep and rest",
            "Consider mind-body practices like yoga or tai chi"
        ]
        
        risk_factors.append({
            "name": "stress_level",
            "current_value": stress_value,
            "ideal_value": ideal_stress,
            "impact_score": stress_impact,
            "recommendations": recommendations
        })
    
    # BMI factor (similar to diabetes analysis)
    if patient.weight and patient.height and patient.height > 0:
        bmi = (patient.weight / ((patient.height/100) ** 2))
        ideal_bmi = 24
        
        # Calculate impact
        bmi_impact = 0
        if bmi >= 30:
            bmi_impact = 70
        elif bmi >= 25:
            bmi_impact = 40
        elif bmi < 18.5:
            bmi_impact = 20
        else:
            bmi_impact = max(0, (abs(bmi - ideal_bmi) * 8))
        
        # Adjust based on prediction value
        bmi_impact = bmi_impact * (prediction.prediction_value / 100)
        
        recommendations = [
            "Maintain a heart-healthy diet rich in fruits and vegetables",
            "Focus on portion control and regular exercise"
        ]
        
        if bmi >= 30:
            recommendations.append("Consider a structured weight management program")
        
        risk_factors.append({
            "name": "body_mass_index",
            "current_value": bmi,
            "ideal_value": ideal_bmi,
            "impact_score": bmi_impact,
            "recommendations": recommendations
        })
    
    return risk_factors


def _analyze_cardiovascular_risk_factors(patient, prediction, readings_by_type, questionnaire_data):
    """
    Analyze risk factors specific to cardiovascular disease
    
    Returns:
        List of risk factor dictionaries
    """
    risk_factors = []
    
    # Cholesterol factor (if available)
    cholesterol_level = None
    hdl_level = None
    ldl_level = None
    
    if 'cholesterol' in readings_by_type and readings_by_type['cholesterol']:
        chol_readings = readings_by_type['cholesterol']
        
        for reading in chol_readings:
            if reading.value_type == 'total':
                cholesterol_level = reading.value
            elif reading.value_type == 'hdl':
                hdl_level = reading.value
            elif reading.value_type == 'ldl':
                ldl_level = reading.value
    
    if cholesterol_level and ldl_level:
        ideal_cholesterol = 180  # Total cholesterol target
        ideal_ldl = 100  # LDL target
        
        # Calculate impact score
        chol_impact = 0
        if cholesterol_level >= 240:
            chol_impact = 80
        elif cholesterol_level >= 200:
            chol_impact = 50
        else:
            chol_impact = max(0, (cholesterol_level - ideal_cholesterol) * 0.5)
        
        ldl_impact = 0
        if ldl_level >= 160:
            ldl_impact = 80
        elif ldl_level >= 130:
            ldl_impact = 60
        elif ldl_level >= 100:
            ldl_impact = 30
        
        # Combined impact
        lipid_impact = max(chol_impact, ldl_impact)
        
        # Adjust based on prediction value
        lipid_impact = lipid_impact * (prediction.prediction_value / 100)
        
        recommendations = [
            "Limit saturated and trans fats in your diet",
            "Increase fiber intake through whole grains and legumes",
            "Consider omega-3 rich foods like fatty fish"
        ]
        
        if cholesterol_level >= 200 or ldl_level >= 130:
            recommendations.append("Discuss statin or other medication options with your doctor")
        
        risk_factors.append({
            "name": "cholesterol_levels",
            "current_value": f"Total: {cholesterol_level}, LDL: {ldl_level}",
            "ideal_value": f"Total: {ideal_cholesterol}, LDL: {ideal_ldl}",
            "impact_score": lipid_impact,
            "recommendations": recommendations
        })
    
    # Blood pressure factor (similar to hypertension analysis)
    if 'blood_pressure' in readings_by_type and readings_by_type['blood_pressure']:
        bp_readings = readings_by_type['blood_pressure']
        
        avg_systolic = sum(r.systolic for r in bp_readings) / len(bp_readings)
        avg_diastolic = sum(r.diastolic for r in bp_readings) / len(bp_readings)
        
        ideal_systolic = 120
        ideal_diastolic = 80
        
        # Calculate combined impact
        bp_impact = 0
        if avg_systolic >= 160 or avg_diastolic >= 100:  # Stage 2
            bp_impact = 80
        elif avg_systolic >= 140 or avg_diastolic >= 90:  # Stage 1
            bp_impact = 60
        elif avg_systolic >= 130 or avg_diastolic >= 85:  # Elevated
            bp_impact = 40
        elif avg_systolic >= 120 or avg_diastolic >= 80:  # Normal
            bp_impact = 20
        
        # Adjust based on prediction value
        bp_impact = bp_impact * (prediction.prediction_value / 100)
        
        recommendations = [
            "Monitor blood pressure regularly",
            "Maintain a low-sodium, heart-healthy diet",
            "Practice stress management techniques"
        ]
        
        risk_factors.append({
            "name": "blood_pressure",
            "current_value": f"{avg_systolic:.0f}/{avg_diastolic:.0f}",
            "ideal_value": f"{ideal_systolic}/{ideal_diastolic}",
            "impact_score": bp_impact,
            "recommendations": recommendations
        })
    
    # Smoking status (from questionnaire)
    smoking_status = None
    for question, answer in questionnaire_data.items():
        if "smok" in question.lower() or "tobacco" in question.lower():
            smoking_status = answer
            break
    
    if smoking_status:
        is_smoker = "yes" in smoking_status.lower() or "current" in smoking_status.lower()
        
        smoking_value = 1 if is_smoker else 0
        ideal_smoking = 0  # Non-smoking is ideal
        
        # Calculate impact
        smoking_impact = 90 if is_smoker else 0
        
        # Adjust based on prediction value
        smoking_impact = smoking_impact * (prediction.prediction_value / 100)
        
        recommendations = []
        if is_smoker:
            recommendations = [
                "Quit smoking as soon as possible",
                "Consider smoking cessation programs or medications",
                "Avoid secondhand smoke exposure"
            ]
        else:
            recommendations = [
                "Continue avoiding tobacco products",
                "Avoid secondhand smoke exposure"
            ]
        
        risk_factors.append({
            "name": "smoking_status",
            "current_value": smoking_value,
            "ideal_value": ideal_smoking,
            "impact_score": smoking_impact,
            "recommendations": recommendations
        })
    
    # Physical activity factor (from questionnaire)
    activity_level = None
    for question, answer in questionnaire_data.items():
        if "physical activity" in question.lower() or "exercise" in question.lower():
            activity_level = answer
            break
    
    if activity_level:
        activity_value = 0
        if "none" in activity_level.lower() or "sedentary" in activity_level.lower():
            activity_value = 0
        elif "light" in activity_level.lower() or "1-2" in activity_level:
            activity_value = 2
        elif "moderate" in activity_level.lower() or "3-5" in activity_level:
            activity_value = 5
        elif "active" in activity_level.lower() or "daily" in activity_level.lower():
            activity_value = 7
        
        ideal_activity = 5  # Moderate activity
        
        # Calculate impact
        activity_impact = max(0, (ideal_activity - activity_value) * 10)
        
        # Adjust based on prediction value
        activity_impact = activity_impact * (prediction.prediction_value / 100)
        
        recommendations = [
            "Aim for at least 150 minutes of moderate cardio activity per week",
            "Include strength training exercises twice weekly",
            "Begin with short walking sessions and gradually increase"
        ]
        
        risk_factors.append({
            "name": "physical_activity",
            "current_value": activity_value,
            "ideal_value": ideal_activity,
            "impact_score": activity_impact,
            "recommendations": recommendations
        })
    
    return risk_factors


def _format_factor_name(factor_name):
    """Format risk factor name for display"""
    # Convert snake_case to Title Case with spaces
    formatted = factor_name.replace('_', ' ').title()
    
    # Handle specific abbreviations
    formatted = formatted.replace('Bmi', 'BMI')
    formatted = formatted.replace('Ldl', 'LDL')
    formatted = formatted.replace('Hdl', 'HDL')
    
    return formatted


def _calculate_percentage_of_ideal(factor_name, current_value, ideal_value):
    """
    Calculate how close the current value is to the ideal value as a percentage
    
    Returns:
        Integer percentage (0-100)
    """
    try:
        # For blood pressure, which is formatted as "systolic/diastolic"
        if isinstance(current_value, str) and '/' in current_value and '/' in str(ideal_value):
            current_parts = current_value.split('/')
            ideal_parts = str(ideal_value).split('/')
            
            if len(current_parts) == 2 and len(ideal_parts) == 2:
                current_systolic = float(current_parts[0])
                current_diastolic = float(current_parts[1])
                ideal_systolic = float(ideal_parts[0])
                ideal_diastolic = float(ideal_parts[1])
                
                # Calculate percentage for each component
                if current_systolic > ideal_systolic:
                    systolic_pct = max(0, 100 - ((current_systolic - ideal_systolic) / ideal_systolic * 100))
                else:
                    systolic_pct = 100
                    
                if current_diastolic > ideal_diastolic:
                    diastolic_pct = max(0, 100 - ((current_diastolic - ideal_diastolic) / ideal_diastolic * 100))
                else:
                    diastolic_pct = 100
                
                # Use the worse of the two
                return min(int(systolic_pct), int(diastolic_pct))
        
        # For binary factors (0 or 1)
        if factor_name in ['smoking_status', 'family_history']:
            return 100 if current_value == ideal_value else 0
        
        # For cholesterol which may be formatted as "Total: X, LDL: Y"
        if isinstance(current_value, str) and 'Total:' in current_value and 'LDL:' in current_value:
            # Just use a simple scale for now
            if 'high' in current_value.lower():
                return 30
            elif 'borderline' in current_value.lower():
                return 70
            elif 'normal' in current_value.lower():
                return 100
            else:
                return 50  # Default middle value
        
        # For numerical values
        if isinstance(current_value, (int, float)) and isinstance(ideal_value, (int, float)):
            # For factors where lower is better
            if factor_name in ['blood_glucose', 'body_mass_index', 'stress_level', 'sodium_intake']:
                if current_value <= ideal_value:
                    return 100
                else:
                    # Percentage decreases as value increases above ideal
                    max_bad_value = ideal_value * 2  # Set a reasonable upper bound
                    return max(0, int(100 - ((current_value - ideal_value) / (max_bad_value - ideal_value) * 100)))
            
            # For factors where higher is better
            if factor_name in ['physical_activity']:
                if current_value >= ideal_value:
                    return 100
                else:
                    # Percentage decreases as value decreases below ideal
                    return max(0, int((current_value / ideal_value) * 100))
        
        # Default case
        return 50  # Return middle value if we can't determine
    
    except Exception as e:
        current_app.logger.error(f"Error calculating percentage: {str(e)}")
        return 50  # Default to middle value on error