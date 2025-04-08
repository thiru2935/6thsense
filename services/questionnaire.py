"""
Health Questionnaire Service

This service manages personalized health questionnaires for different conditions.
Questionnaires are used to gather additional context from patients that can be
used to enhance AI predictions.
"""

import json
from datetime import datetime
from flask import current_app
from app import db
from models import (
    HealthQuestionnaire, 
    QuestionnaireQuestion, 
    QuestionnaireResponse,
    PatientProfile
)


def get_questionnaire_questions(condition):
    """
    Get all questions for a specific condition questionnaire.
    
    Args:
        condition: The condition type (diabetes, hypertension, cardiovascular)
        
    Returns:
        List of QuestionnaireQuestion objects, ordered by their sequence
    """
    return QuestionnaireQuestion.query.filter_by(
        condition=condition,
        is_active=True
    ).order_by(QuestionnaireQuestion.order).all()


def get_latest_questionnaire(patient_id, condition):
    """
    Get the most recent questionnaire completed by a patient for a specific condition.
    
    Args:
        patient_id: ID of the patient
        condition: The condition type
        
    Returns:
        HealthQuestionnaire object or None if not found
    """
    return HealthQuestionnaire.query.filter_by(
        patient_id=patient_id,
        condition=condition
    ).order_by(HealthQuestionnaire.completed_at.desc()).first()


def save_questionnaire_responses(patient_id, condition, responses):
    """
    Save patient responses to a questionnaire.
    
    Args:
        patient_id: ID of the patient
        condition: The condition type (diabetes, hypertension, cardiovascular)
        responses: Dictionary mapping question_id to response
        
    Returns:
        Newly created HealthQuestionnaire object
    """
    # Create new questionnaire record
    questionnaire = HealthQuestionnaire(
        patient_id=patient_id,
        condition=condition,
        completed_at=datetime.utcnow()
    )
    db.session.add(questionnaire)
    db.session.flush()  # Get the ID without committing
    
    # Add responses
    for question_id, response_data in responses.items():
        question = QuestionnaireQuestion.query.get(question_id)
        if not question:
            continue
            
        response_text = str(response_data)
        response_value = None
        
        # Handle different question types
        if question.question_type == 'boolean':
            response_value = 1.0 if response_data.lower() in ['yes', 'true', '1'] else 0.0
        elif question.question_type == 'numeric':
            try:
                response_value = float(response_data)
            except (ValueError, TypeError):
                response_value = None
        elif question.question_type == 'multiple_choice':
            # For multiple choice, get the index of the selected option
            try:
                options = json.loads(question.options)
                if response_data in options:
                    response_value = float(options.index(response_data))
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
                
        # Create response record
        response = QuestionnaireResponse(
            questionnaire_id=questionnaire.id,
            question_id=question_id,
            response_text=response_text,
            response_value=response_value
        )
        db.session.add(response)
    
    db.session.commit()
    return questionnaire


def get_questionnaire_data_for_prediction(patient_id, condition):
    """
    Format questionnaire data to be included in the AI prediction.
    
    Args:
        patient_id: ID of the patient
        condition: The condition type
        
    Returns:
        Dictionary of questionnaire data or None if no questionnaire found
    """
    questionnaire = get_latest_questionnaire(patient_id, condition)
    if not questionnaire:
        return None
        
    # Get all responses with their questions
    responses = QuestionnaireResponse.query.filter_by(
        questionnaire_id=questionnaire.id
    ).all()
    
    result = {
        "completed_at": questionnaire.completed_at.strftime("%Y-%m-%d %H:%M:%S"),
        "responses": []
    }
    
    for response in responses:
        question = response.question
        result["responses"].append({
            "question": question.question_text,
            "answer": response.response_text,
            "value": response.response_value,
            "weight": question.weight
        })
        
    return result


def create_default_questions():
    """
    Create default questionnaire questions for all conditions.
    Should be run once during app initialization.
    """
    # Check if questions already exist
    if QuestionnaireQuestion.query.count() > 0:
        return
        
    # Diabetes questions
    diabetes_questions = [
        {
            "question_text": "Do you have a family history of diabetes?",
            "question_type": "boolean",
            "options": None,
            "weight": 2,
            "order": 1
        },
        {
            "question_text": "How many hours of sleep do you typically get each night?",
            "question_type": "numeric",
            "options": None,
            "weight": 1,
            "order": 2
        },
        {
            "question_text": "How would you describe your diet?",
            "question_type": "multiple_choice",
            "options": json.dumps([
                "Very healthy (mostly whole foods)",
                "Moderately healthy (mix of whole foods and processed foods)",
                "Unhealthy (mostly processed foods)",
                "Poor (high in sugar and fats)"
            ]),
            "weight": 2,
            "order": 3
        },
        {
            "question_text": "How many times per week do you engage in physical activity for at least 30 minutes?",
            "question_type": "numeric",
            "options": None,
            "weight": 2,
            "order": 4
        },
        {
            "question_text": "Do you experience increased thirst and frequent urination?",
            "question_type": "boolean",
            "options": None,
            "weight": 3,
            "order": 5
        },
        {
            "question_text": "Have you noticed unexplained weight loss?",
            "question_type": "boolean",
            "options": None,
            "weight": 2,
            "order": 6
        },
        {
            "question_text": "Do you often feel fatigued or low on energy?",
            "question_type": "boolean",
            "options": None,
            "weight": 1,
            "order": 7
        },
        {
            "question_text": "How would you rate your stress level on a scale from 1 (very low) to 10 (very high)?",
            "question_type": "numeric",
            "options": None,
            "weight": 1,
            "order": 8
        }
    ]
    
    # Hypertension questions
    hypertension_questions = [
        {
            "question_text": "Do you have a family history of hypertension or heart disease?",
            "question_type": "boolean",
            "options": None,
            "weight": 2,
            "order": 1
        },
        {
            "question_text": "How would you describe your salt intake?",
            "question_type": "multiple_choice",
            "options": json.dumps([
                "Very low (rarely add salt)",
                "Moderate (occasionally add salt)",
                "High (regularly add salt)",
                "Very high (prefer salty foods)"
            ]),
            "weight": 3,
            "order": 2
        },
        {
            "question_text": "How many alcoholic drinks do you consume in a typical week?",
            "question_type": "numeric",
            "options": None,
            "weight": 2,
            "order": 3
        },
        {
            "question_text": "Do you smoke or use tobacco products?",
            "question_type": "boolean",
            "options": None,
            "weight": 3,
            "order": 4
        },
        {
            "question_text": "Do you experience frequent headaches?",
            "question_type": "boolean",
            "options": None,
            "weight": 1,
            "order": 5
        },
        {
            "question_text": "How many hours per week do you engage in cardiovascular exercise?",
            "question_type": "numeric",
            "options": None,
            "weight": 2,
            "order": 6
        },
        {
            "question_text": "On a scale from 1 to 10, how would you rate your stress level during a typical day?",
            "question_type": "numeric",
            "options": None,
            "weight": 2,
            "order": 7
        },
        {
            "question_text": "Do you have difficulty sleeping or suffer from sleep apnea?",
            "question_type": "boolean",
            "options": None,
            "weight": 1,
            "order": 8
        }
    ]
    
    # Cardiovascular questions
    cardiovascular_questions = [
        {
            "question_text": "Do you have a family history of heart disease, heart attack, or stroke?",
            "question_type": "boolean",
            "options": None,
            "weight": 3,
            "order": 1
        },
        {
            "question_text": "How would you describe your cholesterol levels based on your most recent test?",
            "question_type": "multiple_choice",
            "options": json.dumps([
                "Normal/Healthy",
                "Borderline high",
                "High",
                "Unknown/Never tested"
            ]),
            "weight": 3,
            "order": 2
        },
        {
            "question_text": "Do you ever experience chest pain or discomfort, especially during physical activity?",
            "question_type": "boolean",
            "options": None,
            "weight": 3,
            "order": 3
        },
        {
            "question_text": "Do you ever feel heart palpitations (rapid or irregular heartbeats)?",
            "question_type": "boolean",
            "options": None,
            "weight": 2,
            "order": 4
        },
        {
            "question_text": "How many days per week do you consume vegetables?",
            "question_type": "numeric",
            "options": None,
            "weight": 1,
            "order": 5
        },
        {
            "question_text": "How many days per week do you consume fruits?",
            "question_type": "numeric",
            "options": None,
            "weight": 1,
            "order": 6
        },
        {
            "question_text": "Do you ever experience shortness of breath during normal activities?",
            "question_type": "boolean",
            "options": None,
            "weight": 2,
            "order": 7
        },
        {
            "question_text": "How would you rate your overall stress management on a scale from 1 (poor) to 10 (excellent)?",
            "question_type": "numeric",
            "options": None,
            "weight": 1,
            "order": 8
        }
    ]
    
    # Add all questions to database
    for questions in [
        (diabetes_questions, "diabetes"), 
        (hypertension_questions, "hypertension"), 
        (cardiovascular_questions, "cardiovascular")
    ]:
        for q_data in questions[0]:
            question = QuestionnaireQuestion(
                condition=questions[1],
                question_text=q_data["question_text"],
                question_type=q_data["question_type"],
                options=q_data["options"],
                weight=q_data["weight"],
                order=q_data["order"],
                is_active=True
            )
            db.session.add(question)
    
    db.session.commit()
    current_app.logger.info(f"Created default questionnaire questions for all conditions")