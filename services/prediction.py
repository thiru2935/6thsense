import logging
import numpy as np
from datetime import datetime, timedelta

from app import db
from models import PatientProfile, HealthReading, Prediction, PredictionModel

# This is a simplified implementation for demo purposes
# In a real application, we would use a more sophisticated ML model

def predict_risk_score(patient_id):
    """
    Calculate a diabetes risk score for a patient based on their readings.
    
    For demo purposes, this uses a simple algorithm rather than a trained ML model:
    - High blood glucose readings increase risk
    - High blood pressure readings increase risk
    - Abnormal readings increase risk more
    - More recent readings have higher weight
    
    Returns a score from 0-100, where higher is more at risk
    """
    try:
        # Get patient
        patient = PatientProfile.query.get(patient_id)
        if not patient:
            logging.error(f"Patient not found for ID: {patient_id}")
            return 50  # Default score
        
        # Get recent readings (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        glucose_readings = HealthReading.query.filter_by(
            patient_id=patient_id, 
            reading_type='blood_glucose'
        ).filter(HealthReading.timestamp >= thirty_days_ago).all()
        
        bp_readings = HealthReading.query.filter_by(
            patient_id=patient_id, 
            reading_type='blood_pressure'
        ).filter(HealthReading.timestamp >= thirty_days_ago).all()
        
        # Calculate base risk based on diagnosis
        base_risk = 50  # Default base risk
        if patient.diagnosis:
            if 'type 1 diabetes' in patient.diagnosis.lower():
                base_risk = 60
            elif 'type 2 diabetes' in patient.diagnosis.lower():
                base_risk = 55
            elif 'prediabetes' in patient.diagnosis.lower():
                base_risk = 45
        
        # If we have no readings, return the base risk
        if not glucose_readings and not bp_readings:
            return base_risk
        
        # Calculate risk factors from glucose readings
        glucose_risk = 0
        if glucose_readings:
            glucose_values = []
            for reading in glucose_readings:
                # Convert all to mg/dL for consistency
                value = reading.value
                if reading.unit == 'mmol/L':
                    value = value * 18  # Convert mmol/L to mg/dL
                
                # More recent readings have higher weight
                days_old = (datetime.utcnow() - reading.timestamp).days
                weight = 1.0 - (days_old / 30)  # Weight from 1.0 to 0.0
                
                glucose_values.append((value, weight, reading.is_abnormal))
            
            # Calculate weighted average glucose
            total_weight = sum(weight for _, weight, _ in glucose_values)
            weighted_avg = sum(value * weight for value, weight, _ in glucose_values) / total_weight if total_weight > 0 else 0
            
            # Count abnormal readings
            abnormal_count = sum(1 for _, _, is_abnormal in glucose_values if is_abnormal)
            abnormal_pct = abnormal_count / len(glucose_values) if glucose_values else 0
            
            # Calculate glucose risk (0-25)
            if weighted_avg < 70:  # Hypoglycemia
                glucose_risk = 15 + (10 * abnormal_pct)
            elif weighted_avg < 100:  # Normal
                glucose_risk = 5 + (10 * abnormal_pct)
            elif weighted_avg < 126:  # Prediabetes
                glucose_risk = 10 + (10 * abnormal_pct)
            elif weighted_avg < 180:  # Diabetes under control
                glucose_risk = 15 + (10 * abnormal_pct)
            else:  # Diabetes not under control
                glucose_risk = 20 + (5 * abnormal_pct)
        
        # Calculate risk factors from blood pressure readings
        bp_risk = 0
        if bp_readings:
            bp_values = []
            for reading in bp_readings:
                if reading.value_systolic and reading.value_diastolic:
                    # More recent readings have higher weight
                    days_old = (datetime.utcnow() - reading.timestamp).days
                    weight = 1.0 - (days_old / 30)  # Weight from 1.0 to 0.0
                    
                    bp_values.append((reading.value_systolic, reading.value_diastolic, weight, reading.is_abnormal))
            
            if bp_values:
                # Calculate weighted average BP
                total_weight = sum(weight for _, _, weight, _ in bp_values)
                weighted_avg_systolic = sum(sys * weight for sys, _, weight, _ in bp_values) / total_weight if total_weight > 0 else 0
                weighted_avg_diastolic = sum(dia * weight for _, dia, weight, _ in bp_values) / total_weight if total_weight > 0 else 0
                
                # Count abnormal readings
                abnormal_count = sum(1 for _, _, _, is_abnormal in bp_values if is_abnormal)
                abnormal_pct = abnormal_count / len(bp_values) if bp_values else 0
                
                # Calculate BP risk (0-25)
                if weighted_avg_systolic < 120 and weighted_avg_diastolic < 80:  # Normal
                    bp_risk = 5 + (10 * abnormal_pct)
                elif weighted_avg_systolic < 130 and weighted_avg_diastolic < 85:  # Elevated
                    bp_risk = 10 + (10 * abnormal_pct)
                elif weighted_avg_systolic < 140 and weighted_avg_diastolic < 90:  # Stage 1 Hypertension
                    bp_risk = 15 + (10 * abnormal_pct)
                else:  # Stage 2 Hypertension
                    bp_risk = 20 + (5 * abnormal_pct)
        
        # Combine risks
        if glucose_readings and bp_readings:
            total_risk = base_risk + (glucose_risk * 0.6) + (bp_risk * 0.4)
        elif glucose_readings:
            total_risk = base_risk + glucose_risk
        elif bp_readings:
            total_risk = base_risk + bp_risk
        else:
            total_risk = base_risk
        
        # Cap risk score at 100
        risk_score = min(round(total_risk), 100)
        
        # Save prediction for future reference
        model = PredictionModel.query.filter_by(
            target_condition='diabetes',
            is_active=True
        ).first()
        
        if not model:
            model = PredictionModel(
                name="Basic Diabetes Risk Model",
                description="Simple risk calculation based on glucose and BP readings",
                model_type="rule-based",
                target_condition="diabetes",
                is_active=True
            )
            db.session.add(model)
            db.session.commit()
        
        prediction = Prediction(
            model_id=model.id,
            patient_id=patient_id,
            prediction_value=risk_score,
            confidence=0.7  # Arbitrary confidence for this demo
        )
        db.session.add(prediction)
        db.session.commit()
        
        return risk_score
        
    except Exception as e:
        logging.error(f"Error calculating risk score: {str(e)}")
        return 50  # Default score

def get_patient_risk_factors(patient_id):
    """
    Identify key risk factors for a patient
    """
    try:
        # Get patient
        patient = PatientProfile.query.get(patient_id)
        if not patient:
            return []
        
        risk_factors = []
        
        # Get recent readings (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        # Check glucose control
        high_glucose_readings = HealthReading.query.filter_by(
            patient_id=patient_id, 
            reading_type='blood_glucose',
            is_abnormal=True
        ).filter(HealthReading.timestamp >= thirty_days_ago).count()
        
        if high_glucose_readings > 0:
            risk_factors.append({
                'name': 'High Blood Glucose',
                'description': f'{high_glucose_readings} abnormal readings in the last 30 days',
                'severity': 'high' if high_glucose_readings > 5 else 'medium'
            })
        
        # Check blood pressure control
        high_bp_readings = HealthReading.query.filter_by(
            patient_id=patient_id, 
            reading_type='blood_pressure',
            is_abnormal=True
        ).filter(HealthReading.timestamp >= thirty_days_ago).count()
        
        if high_bp_readings > 0:
            risk_factors.append({
                'name': 'High Blood Pressure',
                'description': f'{high_bp_readings} abnormal readings in the last 30 days',
                'severity': 'high' if high_bp_readings > 5 else 'medium'
            })
        
        # More risk factors would be added in a real implementation
        
        return risk_factors
        
    except Exception as e:
        logging.error(f"Error identifying risk factors: {str(e)}")
        return []
