from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import current_user, login_required
from datetime import datetime

from app import db
from models import (
    ExternalSystem, SystemConnection, DataMapping, IntegrationLog,
    PatientExternalMapping, PatientProfile, User, ProviderProfile,
    ProviderPatientAssociation
)
from services.emr_integration import emr_service

emr_bp = Blueprint('emr', __name__, url_prefix='/emr')

# Decorator to check provider/admin access
def check_provider_admin():
    if not current_user.is_authenticated:
        flash('Please log in to access this feature.', 'warning')
        return redirect(url_for('auth.login'))
        
    if not (current_user.is_provider() or current_user.is_admin()):
        flash('Access denied. You must be a healthcare provider or admin.', 'danger')
        return redirect(url_for('index'))
    
    return None

@emr_bp.route('/systems')
@login_required
def systems_list():
    """List all configured external systems"""
    check_result = check_provider_admin()
    if check_result:
        return check_result
    
    systems = ExternalSystem.query.all()
    return render_template('emr/systems.html', systems=systems)

@emr_bp.route('/systems/add', methods=['GET', 'POST'])
@login_required
def add_system():
    """Add a new external system"""
    check_result = check_provider_admin()
    if check_result:
        return check_result
    
    if request.method == 'POST':
        system_name = request.form.get('system_name')
        system_type = request.form.get('system_type')
        api_endpoint = request.form.get('api_endpoint')
        api_auth_type = request.form.get('api_auth_type')
        is_bidirectional = request.form.get('is_bidirectional') == 'on'
        
        # Validate required fields
        if not all([system_name, system_type, api_endpoint, api_auth_type]):
            flash('All fields are required', 'danger')
            return redirect(url_for('emr.add_system'))
        
        # Create new system
        system = ExternalSystem(
            system_name=system_name,
            system_type=system_type,
            api_endpoint=api_endpoint,
            api_auth_type=api_auth_type,
            is_bidirectional=is_bidirectional,
            is_active=True
        )
        
        db.session.add(system)
        db.session.commit()
        
        flash(f'External system "{system_name}" added successfully', 'success')
        return redirect(url_for('emr.systems_list'))
    
    # GET request
    system_types = [
        'fhir',
        'epic',
        'cerner',
        'allscripts',
        'meditech',
        'nextgen',
        'athenahealth',
        'eclinicalworks',
        'custom_api'
    ]
    
    auth_types = [
        'oauth2',
        'apikey',
        'basic',
        'jwt',
        'none'
    ]
    
    return render_template(
        'emr/add_system.html',
        system_types=system_types,
        auth_types=auth_types
    )

@emr_bp.route('/systems/<int:system_id>')
@login_required
def system_detail(system_id):
    """View details of an external system"""
    check_result = check_provider_admin()
    if check_result:
        return check_result
    
    system = ExternalSystem.query.get_or_404(system_id)
    connections = SystemConnection.query.filter_by(system_id=system_id).order_by(SystemConnection.id.desc()).all()
    mappings = DataMapping.query.filter_by(system_id=system_id).all()
    recent_logs = IntegrationLog.query.filter_by(system_id=system_id).order_by(IntegrationLog.created_at.desc()).limit(20).all()
    
    return render_template(
        'emr/system_detail.html',
        system=system,
        connections=connections,
        mappings=mappings,
        recent_logs=recent_logs
    )

@emr_bp.route('/systems/<int:system_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_system(system_id):
    """Edit an external system"""
    check_result = check_provider_admin()
    if check_result:
        return check_result
    
    system = ExternalSystem.query.get_or_404(system_id)
    
    if request.method == 'POST':
        system.system_name = request.form.get('system_name')
        system.system_type = request.form.get('system_type')
        system.api_endpoint = request.form.get('api_endpoint')
        system.api_auth_type = request.form.get('api_auth_type')
        system.is_bidirectional = request.form.get('is_bidirectional') == 'on'
        system.is_active = request.form.get('is_active') == 'on'
        
        db.session.commit()
        
        flash('System updated successfully', 'success')
        return redirect(url_for('emr.system_detail', system_id=system_id))
    
    # GET request
    system_types = [
        'fhir',
        'epic',
        'cerner',
        'allscripts',
        'meditech',
        'nextgen',
        'athenahealth',
        'eclinicalworks',
        'custom_api'
    ]
    
    auth_types = [
        'oauth2',
        'apikey',
        'basic',
        'jwt',
        'none'
    ]
    
    return render_template(
        'emr/edit_system.html',
        system=system,
        system_types=system_types,
        auth_types=auth_types
    )

@emr_bp.route('/systems/<int:system_id>/connections/add', methods=['GET', 'POST'])
@login_required
def add_connection(system_id):
    """Add a new connection to an external system"""
    check_result = check_provider_admin()
    if check_result:
        return check_result
    
    system = ExternalSystem.query.get_or_404(system_id)
    
    if request.method == 'POST':
        connection_name = request.form.get('connection_name')
        
        # Different fields based on auth type
        auth_data = {}
        if system.api_auth_type == 'oauth2':
            auth_data = {
                'client_id': request.form.get('client_id'),
                'client_secret': request.form.get('client_secret'),
                'auth_token': request.form.get('auth_token'),
                'refresh_token': request.form.get('refresh_token')
            }
        elif system.api_auth_type == 'apikey':
            auth_data = {
                'api_key': request.form.get('api_key')
            }
        elif system.api_auth_type == 'basic':
            auth_data = {
                'client_id': request.form.get('username'),
                'client_secret': request.form.get('password')
            }
        
        # Create new connection
        connection = SystemConnection(
            system_id=system_id,
            connection_name=connection_name,
            connection_status='active',
            **auth_data
        )
        
        # Handle expiry for OAuth tokens
        if system.api_auth_type == 'oauth2' and request.form.get('token_expires_at'):
            try:
                connection.token_expires_at = datetime.strptime(
                    request.form.get('token_expires_at'),
                    '%Y-%m-%dT%H:%M'
                )
            except:
                flash('Invalid token expiration date format', 'warning')
        
        db.session.add(connection)
        db.session.commit()
        
        flash('Connection added successfully', 'success')
        return redirect(url_for('emr.system_detail', system_id=system_id))
    
    # GET request
    return render_template(
        'emr/add_connection.html',
        system=system
    )

@emr_bp.route('/systems/<int:system_id>/test_connection')
@login_required
def test_connection(system_id):
    """Test connection to an external system"""
    check_result = check_provider_admin()
    if check_result:
        return check_result
    
    success, message = emr_service.test_connection(system_id)
    
    if success:
        flash(f'Connection test successful: {message}', 'success')
    else:
        flash(f'Connection test failed: {message}', 'danger')
    
    return redirect(url_for('emr.system_detail', system_id=system_id))

@emr_bp.route('/systems/<int:system_id>/mappings/add', methods=['GET', 'POST'])
@login_required
def add_mapping(system_id):
    """Add a new data field mapping"""
    check_result = check_provider_admin()
    if check_result:
        return check_result
    
    system = ExternalSystem.query.get_or_404(system_id)
    
    if request.method == 'POST':
        our_field = request.form.get('our_field')
        external_field = request.form.get('external_field')
        entity_type = request.form.get('entity_type')
        data_type = request.form.get('data_type')
        is_required = request.form.get('is_required') == 'on'
        transformation_rule = request.form.get('transformation_rule')
        
        # Validate required fields
        if not all([our_field, external_field, entity_type, data_type]):
            flash('Required fields missing', 'danger')
            return redirect(url_for('emr.add_mapping', system_id=system_id))
        
        # Create new mapping
        mapping = DataMapping(
            system_id=system_id,
            our_field=our_field,
            external_field=external_field,
            entity_type=entity_type,
            data_type=data_type,
            is_required=is_required,
            transformation_rule=transformation_rule
        )
        
        db.session.add(mapping)
        db.session.commit()
        
        flash('Data mapping added successfully', 'success')
        return redirect(url_for('emr.system_detail', system_id=system_id))
    
    # GET request
    entity_types = [
        'patient',
        'health_reading',
        'medication',
        'health_record',
        'device'
    ]
    
    data_types = [
        'string',
        'integer',
        'float',
        'boolean',
        'date',
        'datetime',
        'json'
    ]
    
    return render_template(
        'emr/add_mapping.html',
        system=system,
        entity_types=entity_types,
        data_types=data_types
    )

@emr_bp.route('/patient/<int:patient_id>/external')
@login_required
def patient_external_systems(patient_id):
    """Manage external system links for a patient"""
    # Check if current user is provider for this patient or is the patient
    is_authorized = False
    patient = PatientProfile.query.get_or_404(patient_id)
    
    if current_user.is_patient() and patient.user_id == current_user.id:
        is_authorized = True
    elif current_user.is_provider():
        provider = ProviderProfile.query.filter_by(user_id=current_user.id).first()
        if provider:
            assoc = ProviderPatientAssociation.query.filter_by(
                provider_id=provider.id, patient_id=patient_id
            ).first()
            if assoc:
                is_authorized = True
    elif current_user.is_admin():
        is_authorized = True
    
    if not is_authorized:
        flash('You are not authorized to access this patient\'s data', 'danger')
        return redirect(url_for('index'))
    
    # Get patient's external system mappings
    mappings = PatientExternalMapping.query.filter_by(patient_id=patient_id).all()
    systems = ExternalSystem.query.filter_by(is_active=True).all()
    
    patient_user = User.query.get(patient.user_id)
    
    return render_template(
        'emr/patient_external_systems.html',
        patient=patient,
        patient_user=patient_user,
        mappings=mappings,
        systems=systems
    )

@emr_bp.route('/patient/<int:patient_id>/external/link', methods=['POST'])
@login_required
def link_patient_external(patient_id):
    """Link a patient to an external system"""
    # Check authorization (same as patient_external_systems)
    is_authorized = False
    patient = PatientProfile.query.get_or_404(patient_id)
    
    if current_user.is_patient() and patient.user_id == current_user.id:
        is_authorized = True
    elif current_user.is_provider():
        provider = ProviderProfile.query.filter_by(user_id=current_user.id).first()
        if provider:
            assoc = ProviderPatientAssociation.query.filter_by(
                provider_id=provider.id, patient_id=patient_id
            ).first()
            if assoc:
                is_authorized = True
    elif current_user.is_admin():
        is_authorized = True
    
    if not is_authorized:
        flash('You are not authorized to modify this patient\'s data', 'danger')
        return redirect(url_for('index'))
    
    # Process form data
    system_id = request.form.get('system_id')
    external_patient_id = request.form.get('external_patient_id')
    
    if not all([system_id, external_patient_id]):
        flash('System and external ID are required', 'danger')
        return redirect(url_for('emr.patient_external_systems', patient_id=patient_id))
    
    success, message = emr_service.link_patient_to_external_system(
        patient_id, int(system_id), external_patient_id
    )
    
    if success:
        flash(message, 'success')
    else:
        flash(f'Error: {message}', 'danger')
    
    return redirect(url_for('emr.patient_external_systems', patient_id=patient_id))

@emr_bp.route('/patient/<int:patient_id>/external/<int:system_id>/sync')
@login_required
def sync_patient_data(patient_id, system_id):
    """Synchronize patient data with an external system"""
    # Check authorization (same as patient_external_systems)
    is_authorized = False
    patient = PatientProfile.query.get_or_404(patient_id)
    
    if current_user.is_patient() and patient.user_id == current_user.id:
        is_authorized = True
    elif current_user.is_provider():
        provider = ProviderProfile.query.filter_by(user_id=current_user.id).first()
        if provider:
            assoc = ProviderPatientAssociation.query.filter_by(
                provider_id=provider.id, patient_id=patient_id
            ).first()
            if assoc:
                is_authorized = True
    elif current_user.is_admin():
        is_authorized = True
    
    if not is_authorized:
        flash('You are not authorized to sync this patient\'s data', 'danger')
        return redirect(url_for('index'))
    
    success, message, details = emr_service.synchronize_patient_data(patient_id, system_id)
    
    if success:
        flash(message, 'success')
    else:
        flash(f'Sync error: {message}', 'danger')
    
    return redirect(url_for('emr.patient_external_systems', patient_id=patient_id))

# API endpoints for system integration
@emr_bp.route('/api/systems', methods=['GET'])
@login_required
def api_get_systems():
    """API: Get all external systems"""
    check_result = check_provider_admin()
    if check_result:
        return jsonify({'error': 'Unauthorized'}), 401
    
    systems = ExternalSystem.query.all()
    
    result = [{
        'id': system.id,
        'name': system.system_name,
        'type': system.system_type,
        'active': system.is_active,
        'bidirectional': system.is_bidirectional
    } for system in systems]
    
    return jsonify(result)

@emr_bp.route('/api/logs/<int:system_id>', methods=['GET'])
@login_required
def api_get_logs(system_id):
    """API: Get integration logs for a system"""
    check_result = check_provider_admin()
    if check_result:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Optional filter by status
    status = request.args.get('status')
    
    query = IntegrationLog.query.filter_by(system_id=system_id)
    
    if status:
        query = query.filter_by(status=status)
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    logs = query.order_by(IntegrationLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    result = {
        'items': [{
            'id': log.id,
            'direction': log.direction,
            'status': log.status,
            'entity_type': log.entity_type,
            'message': log.message,
            'created_at': log.created_at.isoformat()
        } for log in logs.items],
        'total': logs.total,
        'pages': logs.pages,
        'page': page
    }
    
    return jsonify(result)

@emr_bp.route('/api/integration/stats', methods=['GET'])
@login_required
def api_integration_stats():
    """API: Get integration statistics"""
    check_result = check_provider_admin()
    if check_result:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Count systems
    active_systems = ExternalSystem.query.filter_by(is_active=True).count()
    total_systems = ExternalSystem.query.count()
    
    # Count patients with external mappings
    patients_with_mappings = db.session.query(PatientExternalMapping.patient_id).distinct().count()
    total_patients = PatientProfile.query.count()
    
    # Count recent integrations
    recent_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    recent_integrations = IntegrationLog.query.filter(IntegrationLog.created_at >= recent_date).count()
    
    # Success/error ratio
    success_count = IntegrationLog.query.filter_by(status='success').count()
    error_count = IntegrationLog.query.filter_by(status='error').count()
    total_logs = success_count + error_count
    success_rate = (success_count / total_logs * 100) if total_logs > 0 else 0
    
    result = {
        'systems': {
            'active': active_systems,
            'total': total_systems
        },
        'patients': {
            'integrated': patients_with_mappings,
            'total': total_patients
        },
        'integration': {
            'recent': recent_integrations,
            'success_rate': round(success_rate, 2)
        }
    }
    
    return jsonify(result)