from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required, current_user
from datetime import datetime

from app import db
from models import User, ChatSession, ChatMessage, PatientProfile

chatbot_bp = Blueprint('chatbot', __name__, url_prefix='/chatbot')

# Simple responses for demonstration purposes
CHATBOT_RESPONSES = {
    'greeting': [
        "Hello! How can I help you today?",
        "Hi there! I'm your health assistant. What can I help you with?"
    ],
    'diabetes_info': [
        "Diabetes is a disease that occurs when your blood glucose (blood sugar) is too high. "
        "Blood glucose is your main source of energy and comes from the food you eat. "
        "Insulin, a hormone made by the pancreas, helps glucose get into your cells to be used for energy.",
        "There are several types of diabetes: Type 1, Type 2, and gestational diabetes. "
        "Type 2 is the most common form. Risk factors include being overweight, being 45 years or older, "
        "having a family history of diabetes, or not being physically active."
    ],
    'medication_reminder': [
        "It's important to take your medications as prescribed by your doctor. "
        "Set reminders on your phone or use a pill organizer to help remember.",
        "Taking your medication at the same time each day helps maintain steady levels in your system. "
        "Consider using our reminder feature in the app for alerts."
    ],
    'blood_glucose': [
        "For most people with diabetes, the target blood glucose level before meals is between 70-130 mg/dL. "
        "After meals, the target is less than 180 mg/dL. However, your specific targets may be different.",
        "Regularly checking your blood glucose helps you know if your diabetes management plan is working. "
        "Keep a record of your readings to share with your healthcare provider."
    ],
    'diet': [
        "A healthy diet for diabetes includes fruits, vegetables, whole grains, lean protein, and healthy fats. "
        "It's also important to limit refined carbs, sugary foods, and processed foods.",
        "Consider working with a dietitian to create a meal plan that works for you. "
        "Portion control and consistent carbohydrate intake can help manage blood sugar levels."
    ],
    'exercise': [
        "Regular physical activity is important for managing diabetes. Aim for at least 150 minutes "
        "of moderate-intensity exercise per week, spread across at least 3 days.",
        "Activities like walking, swimming, and cycling can help lower blood glucose levels and "
        "improve your body's use of insulin. Always check with your doctor before starting a new exercise program."
    ],
    'fallback': [
        "I'm sorry, I don't have specific information about that. Please consult with your healthcare provider for personalized advice.",
        "I don't have enough information to help with that specific question. For medical advice, please speak with your doctor."
    ]
}

def get_topic_from_message(message):
    message = message.lower()
    
    if any(word in message for word in ['hello', 'hi', 'hey', 'greetings']):
        return 'greeting'
    elif any(word in message for word in ['diabetes', 'diabetic', 'sugar disease']):
        return 'diabetes_info'
    elif any(word in message for word in ['medicine', 'medication', 'pill', 'tablet', 'drug', 'prescription']):
        return 'medication_reminder'
    elif any(word in message for word in ['glucose', 'sugar', 'blood sugar', 'reading']):
        return 'blood_glucose'
    elif any(word in message for word in ['food', 'eat', 'diet', 'meal', 'nutrition']):
        return 'diet'
    elif any(word in message for word in ['exercise', 'activity', 'workout', 'fitness', 'walk']):
        return 'exercise'
    else:
        return 'fallback'

def get_response(message):
    topic = get_topic_from_message(message)
    
    # For a real implementation, we would use NLP here to better understand the query
    # and potentially query a knowledge base for more accurate responses
    
    import random
    responses = CHATBOT_RESPONSES.get(topic, CHATBOT_RESPONSES['fallback'])
    return random.choice(responses)

@chatbot_bp.route('/')
@login_required
def index():
    # Get or create a chat session
    active_session = ChatSession.query.filter_by(
        user_id=current_user.id, 
        session_end=None
    ).first()
    
    if not active_session:
        language = 'English'
        if current_user.is_patient():
            patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
            if patient:
                language = patient.preferred_language
        
        active_session = ChatSession(
            user_id=current_user.id,
            language=language
        )
        db.session.add(active_session)
        db.session.commit()
    
    # Get previous messages for this session
    messages = ChatMessage.query.filter_by(session_id=active_session.id).order_by(ChatMessage.timestamp).all()
    
    return render_template('chatbot/index.html', session=active_session, messages=messages)

@chatbot_bp.route('/send', methods=['POST'])
@login_required
def send_message():
    message = request.form.get('message')
    if not message:
        return jsonify({'error': 'No message provided'}), 400
    
    # Get the active session or create one
    active_session = ChatSession.query.filter_by(
        user_id=current_user.id, 
        session_end=None
    ).first()
    
    if not active_session:
        language = 'English'
        if current_user.is_patient():
            patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
            if patient:
                language = patient.preferred_language
        
        active_session = ChatSession(
            user_id=current_user.id,
            language=language
        )
        db.session.add(active_session)
        db.session.commit()
    
    # Save the user message
    user_message = ChatMessage(
        session_id=active_session.id,
        sender_type='user',
        message=message
    )
    db.session.add(user_message)
    
    # Generate and save the bot response
    bot_response = get_response(message)
    bot_message = ChatMessage(
        session_id=active_session.id,
        sender_type='bot',
        message=bot_response
    )
    db.session.add(bot_message)
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'user_message': {
            'id': user_message.id,
            'message': user_message.message,
            'timestamp': user_message.timestamp.isoformat()
        },
        'bot_message': {
            'id': bot_message.id,
            'message': bot_message.message,
            'timestamp': bot_message.timestamp.isoformat()
        }
    })

@chatbot_bp.route('/end_session', methods=['POST'])
@login_required
def end_session():
    active_session = ChatSession.query.filter_by(
        user_id=current_user.id, 
        session_end=None
    ).first()
    
    if active_session:
        active_session.session_end = datetime.utcnow()
        db.session.commit()
        
    return jsonify({'status': 'success'})
