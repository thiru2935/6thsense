"""
EMR Integration Service

This service handles bidirectional data flow between the 6th Sense platform and
external Electronic Medical Record (EMR) and hospital systems.

Key functionalities:
1. Connection management for external systems
2. Patient data synchronization
3. Health record exchange
4. Secure API communication
5. Data transformation and mapping
"""

import json
import logging
import requests
from datetime import datetime, timedelta
from requests.exceptions import RequestException
from typing import Dict, List, Optional, Tuple, Union

from app import db
from models import (
    ExternalSystem, SystemConnection, DataMapping, IntegrationLog,
    PatientExternalMapping, PatientProfile, User, HealthRecord,
    HealthReading, Medication, MedicationLog, Device
)


class EMRIntegrationService:
    """
    Service for handling bidirectional data flow with external EMR systems
    """
    
    @staticmethod
    def get_all_systems():
        """Get all configured external systems"""
        return ExternalSystem.query.filter_by(is_active=True).all()
    
    @staticmethod
    def get_system(system_id):
        """Get a specific external system by ID"""
        return ExternalSystem.query.get(system_id)
    
    @staticmethod
    def get_system_connection(system_id):
        """Get active connection for a system"""
        return SystemConnection.query.filter_by(
            system_id=system_id,
            connection_status='active'
        ).order_by(SystemConnection.id.desc()).first()
    
    @staticmethod
    def log_integration_event(
        system_id: int,
        direction: str,
        status: str,
        entity_type: str,
        entity_id: Optional[int] = None,
        patient_id: Optional[int] = None,
        message: str = "",
        details: Optional[Dict] = None
    ) -> IntegrationLog:
        """
        Log an integration event for auditing and troubleshooting
        """
        log_entry = IntegrationLog(
            system_id=system_id,
            direction=direction,
            status=status,
            entity_type=entity_type,
            entity_id=entity_id,
            patient_id=patient_id,
            message=message,
            details=json.dumps(details) if details else None
        )
        
        db.session.add(log_entry)
        db.session.commit()
        return log_entry
    
    @classmethod
    def test_connection(cls, system_id: int) -> Tuple[bool, str]:
        """
        Test connection to an external system
        
        Returns:
            Tuple[bool, str]: (success, message)
        """
        system = cls.get_system(system_id)
        if not system:
            return False, "System not found"
            
        connection = cls.get_system_connection(system_id)
        if not connection:
            return False, "No active connection found"
        
        try:
            # Implement system-specific ping endpoints based on system type
            if system.system_type == 'fhir':
                response = cls._make_api_request(
                    system, connection, 'GET', '/metadata',
                    expected_status_code=200
                )
                if response and response.status_code == 200:
                    return True, "Connection successful"
            else:
                # Generic endpoint test
                response = cls._make_api_request(
                    system, connection, 'GET', '/ping',
                    expected_status_code=200
                )
                if response and response.status_code == 200:
                    return True, "Connection successful"
                    
            return False, f"Connection failed: {response.status_code if response else 'No response'}"
            
        except Exception as e:
            error_msg = f"Connection error: {str(e)}"
            logging.error(error_msg)
            cls.log_integration_event(
                system_id=system_id,
                direction='outbound',
                status='error',
                entity_type='system',
                message=error_msg
            )
            return False, error_msg
    
    @classmethod
    def _make_api_request(
        cls,
        system: ExternalSystem,
        connection: SystemConnection,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        expected_status_code: int = 200
    ) -> Optional[requests.Response]:
        """
        Make an authenticated API request to the external system
        
        Args:
            system: ExternalSystem object
            connection: SystemConnection object
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (relative to base URL)
            data: Request payload
            params: URL parameters
            headers: Additional headers
            expected_status_code: Expected HTTP status code for success
            
        Returns:
            requests.Response or None if failed
        """
        if not headers:
            headers = {}
            
        # Build the full URL
        url = system.api_endpoint.rstrip('/') + '/' + endpoint.lstrip('/')
        
        # Handle authentication based on the system's auth type
        if system.api_auth_type == 'oauth2':
            # Check if token is expired and refresh if needed
            if connection.token_expires_at and connection.token_expires_at <= datetime.utcnow():
                cls._refresh_oauth_token(system, connection)
                
            headers['Authorization'] = f"Bearer {connection.auth_token}"
            
        elif system.api_auth_type == 'apikey':
            headers['X-API-Key'] = connection.api_key
            
        elif system.api_auth_type == 'basic':
            # Requests will handle Basic Auth
            auth = (connection.client_id, connection.client_secret)
        else:
            auth = None
            
        # Add content type for JSON data
        if data:
            headers['Content-Type'] = 'application/json'
            
        try:
            if method.upper() == 'GET':
                response = requests.get(url, params=params, headers=headers, timeout=30)
            elif method.upper() == 'POST':
                response = requests.post(url, json=data, params=params, headers=headers, timeout=30)
            elif method.upper() == 'PUT':
                response = requests.put(url, json=data, params=params, headers=headers, timeout=30)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, params=params, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            # Log the API call
            log_status = 'success' if response.status_code == expected_status_code else 'error'
            cls.log_integration_event(
                system_id=system.id,
                direction='outbound',
                status=log_status,
                entity_type='api_request',
                message=f"{method} {endpoint} - Status: {response.status_code}",
                details={
                    'url': url,
                    'status_code': response.status_code,
                    'response': response.text[:500] if response.text else None  # Truncate long responses
                }
            )
            
            return response
            
        except RequestException as e:
            error_msg = f"API request failed: {str(e)}"
            logging.error(error_msg)
            cls.log_integration_event(
                system_id=system.id,
                direction='outbound',
                status='error',
                entity_type='api_request',
                message=error_msg,
                details={'url': url, 'error': str(e)}
            )
            return None
    
    @classmethod
    def _refresh_oauth_token(cls, system: ExternalSystem, connection: SystemConnection) -> bool:
        """
        Refresh an expired OAuth2 token
        
        Returns:
            bool: Success status
        """
        # OAuth2 token refresh endpoint is typically /oauth/token or /token
        token_endpoint = '/oauth/token'
        
        refresh_data = {
            'grant_type': 'refresh_token',
            'refresh_token': connection.refresh_token,
            'client_id': connection.client_id,
            'client_secret': connection.client_secret
        }
        
        try:
            # Make request with minimal headers for token refresh
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            url = system.api_endpoint.rstrip('/') + '/' + token_endpoint.lstrip('/')
            
            response = requests.post(url, data=refresh_data, headers=headers, timeout=30)
            
            if response.status_code == 200:
                token_data = response.json()
                
                # Update token information
                connection.auth_token = token_data.get('access_token')
                connection.refresh_token = token_data.get('refresh_token', connection.refresh_token)
                
                # Calculate expiry time - default to 1 hour if not provided
                expires_in = token_data.get('expires_in', 3600)
                connection.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                
                db.session.commit()
                
                cls.log_integration_event(
                    system_id=system.id,
                    direction='outbound',
                    status='success',
                    entity_type='token_refresh',
                    message="OAuth token refreshed successfully"
                )
                
                return True
            else:
                error_msg = f"Token refresh failed: {response.status_code} - {response.text}"
                logging.error(error_msg)
                
                cls.log_integration_event(
                    system_id=system.id,
                    direction='outbound',
                    status='error',
                    entity_type='token_refresh',
                    message=error_msg
                )
                
                return False
                
        except Exception as e:
            error_msg = f"Token refresh error: {str(e)}"
            logging.error(error_msg)
            
            cls.log_integration_event(
                system_id=system.id,
                direction='outbound',
                status='error',
                entity_type='token_refresh',
                message=error_msg
            )
            
            return False
    
    @classmethod
    def get_patient_external_mappings(cls, patient_id: int) -> List[PatientExternalMapping]:
        """Get all external system mappings for a patient"""
        return PatientExternalMapping.query.filter_by(patient_id=patient_id).all()
    
    @classmethod
    def link_patient_to_external_system(
        cls, 
        patient_id: int, 
        system_id: int, 
        external_patient_id: str
    ) -> Tuple[bool, str]:
        """
        Link a patient in our system to their record in an external system
        
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            # Check if mapping already exists
            existing = PatientExternalMapping.query.filter_by(
                patient_id=patient_id,
                system_id=system_id
            ).first()
            
            if existing:
                existing.external_patient_id = external_patient_id
                existing.updated_at = datetime.utcnow()
                existing.sync_status = 'synced'
                db.session.commit()
                return True, "Patient mapping updated"
            
            # Create new mapping
            mapping = PatientExternalMapping(
                patient_id=patient_id,
                system_id=system_id,
                external_patient_id=external_patient_id,
                sync_status='synced',
                last_sync=datetime.utcnow()
            )
            
            db.session.add(mapping)
            db.session.commit()
            
            cls.log_integration_event(
                system_id=system_id,
                direction='inbound',
                status='success',
                entity_type='patient_link',
                entity_id=patient_id,
                patient_id=patient_id,
                message=f"Patient linked to external ID {external_patient_id}"
            )
            
            return True, "Patient linked successfully"
            
        except Exception as e:
            error_msg = f"Failed to link patient: {str(e)}"
            logging.error(error_msg)
            
            cls.log_integration_event(
                system_id=system_id,
                direction='inbound',
                status='error',
                entity_type='patient_link',
                entity_id=patient_id,
                patient_id=patient_id,
                message=error_msg
            )
            
            return False, error_msg
    
    @classmethod
    def synchronize_patient_data(cls, patient_id: int, system_id: int) -> Tuple[bool, str, Dict]:
        """
        Synchronize patient data with an external system
        
        Args:
            patient_id: ID of the patient in our system
            system_id: ID of the external system
            
        Returns:
            Tuple[bool, str, Dict]: (success, message, sync_details)
        """
        system = cls.get_system(system_id)
        if not system:
            return False, "System not found", {}
            
        connection = cls.get_system_connection(system_id)
        if not connection:
            return False, "No active connection found", {}
            
        # Get patient mapping
        mapping = PatientExternalMapping.query.filter_by(
            patient_id=patient_id,
            system_id=system_id
        ).first()
        
        if not mapping:
            return False, "Patient not linked to this system", {}
            
        # Get patient data
        patient = PatientProfile.query.get(patient_id)
        user = User.query.get(patient.user_id)
        
        if not patient or not user:
            return False, "Patient data not found", {}
            
        # Start sync process
        sync_details = {
            'inbound': {'success': 0, 'failed': 0, 'items': []},
            'outbound': {'success': 0, 'failed': 0, 'items': []}
        }
        
        try:
            # STEP 1: Push our data to external system (outbound sync)
            if system.is_bidirectional:
                outbound_result = cls._push_patient_data_to_external(
                    system, connection, patient, user, mapping
                )
                sync_details['outbound'] = outbound_result
            
            # STEP 2: Pull data from external system (inbound sync)
            inbound_result = cls._pull_patient_data_from_external(
                system, connection, patient, user, mapping
            )
            sync_details['inbound'] = inbound_result
            
            # Update mapping sync status
            mapping.last_sync = datetime.utcnow()
            mapping.sync_status = 'synced'
            db.session.commit()
            
            total_success = sync_details['inbound']['success'] + sync_details['outbound']['success']
            total_failed = sync_details['inbound']['failed'] + sync_details['outbound']['failed']
            
            message = f"Sync completed with {total_success} successful items and {total_failed} failures"
            
            cls.log_integration_event(
                system_id=system_id,
                direction='both',
                status='success' if total_failed == 0 else 'partial',
                entity_type='patient_sync',
                entity_id=patient_id,
                patient_id=patient_id,
                message=message,
                details=sync_details
            )
            
            return True, message, sync_details
            
        except Exception as e:
            error_msg = f"Sync error: {str(e)}"
            logging.error(error_msg)
            
            mapping.sync_status = 'error'
            db.session.commit()
            
            cls.log_integration_event(
                system_id=system_id,
                direction='both',
                status='error',
                entity_type='patient_sync',
                entity_id=patient_id,
                patient_id=patient_id,
                message=error_msg
            )
            
            return False, error_msg, sync_details
    
    @classmethod
    def _push_patient_data_to_external(
        cls,
        system: ExternalSystem,
        connection: SystemConnection,
        patient: PatientProfile,
        user: User,
        mapping: PatientExternalMapping
    ) -> Dict:
        """
        Push patient data to the external system
        
        Returns:
            Dict with sync results
        """
        result = {'success': 0, 'failed': 0, 'items': []}
        
        # 1. Push health readings
        recent_readings = HealthReading.query.filter_by(patient_id=patient.id)\
            .order_by(HealthReading.timestamp.desc())\
            .limit(100)\
            .all()
            
        for reading in recent_readings:
            try:
                # Map readings to external system format
                reading_data = cls._map_entity_to_external(
                    system.id, 'health_reading', reading
                )
                
                # Make API call to push reading
                endpoint = f"/patients/{mapping.external_patient_id}/observations"
                
                response = cls._make_api_request(
                    system, connection, 'POST', endpoint,
                    data=reading_data
                )
                
                if response and response.status_code in (200, 201):
                    result['success'] += 1
                    result['items'].append({
                        'type': 'health_reading',
                        'id': reading.id,
                        'status': 'success'
                    })
                else:
                    result['failed'] += 1
                    result['items'].append({
                        'type': 'health_reading',
                        'id': reading.id,
                        'status': 'failed',
                        'error': f"API error: {response.status_code if response else 'No response'}"
                    })
            except Exception as e:
                result['failed'] += 1
                result['items'].append({
                    'type': 'health_reading',
                    'id': reading.id,
                    'status': 'failed',
                    'error': str(e)
                })
        
        # 2. Push medications (simplified, real implementation would be more extensive)
        active_medications = Medication.query.filter_by(
            patient_id=patient.id,
            is_active=True
        ).all()
        
        for medication in active_medications:
            try:
                medication_data = cls._map_entity_to_external(
                    system.id, 'medication', medication
                )
                
                endpoint = f"/patients/{mapping.external_patient_id}/medications"
                
                response = cls._make_api_request(
                    system, connection, 'POST', endpoint,
                    data=medication_data
                )
                
                if response and response.status_code in (200, 201):
                    result['success'] += 1
                    result['items'].append({
                        'type': 'medication',
                        'id': medication.id,
                        'status': 'success'
                    })
                else:
                    result['failed'] += 1
                    result['items'].append({
                        'type': 'medication',
                        'id': medication.id,
                        'status': 'failed',
                        'error': f"API error: {response.status_code if response else 'No response'}"
                    })
            except Exception as e:
                result['failed'] += 1
                result['items'].append({
                    'type': 'medication',
                    'id': medication.id,
                    'status': 'failed',
                    'error': str(e)
                })
                
        return result
    
    @classmethod
    def _pull_patient_data_from_external(
        cls,
        system: ExternalSystem,
        connection: SystemConnection,
        patient: PatientProfile,
        user: User,
        mapping: PatientExternalMapping
    ) -> Dict:
        """
        Pull patient data from the external system
        
        Returns:
            Dict with sync results
        """
        result = {'success': 0, 'failed': 0, 'items': []}
        
        # Endpoints to pull from (varies by system type)
        endpoints = {
            'health_records': f"/patients/{mapping.external_patient_id}/documents",
            'medications': f"/patients/{mapping.external_patient_id}/medications",
            'observations': f"/patients/{mapping.external_patient_id}/observations"
        }
        
        # 1. Pull health records
        try:
            response = cls._make_api_request(
                system, connection, 'GET', endpoints['health_records']
            )
            
            if response and response.status_code == 200:
                records_data = response.json()
                
                # Process each record (simplified, real implementation would be more robust)
                for record_data in records_data.get('records', []):
                    try:
                        # Map external data to our system's format
                        record_obj = cls._map_external_to_entity(
                            system.id, 'health_record', record_data
                        )
                        
                        if record_obj:
                            # Check if we already have this record
                            # This is a simplified approach - real implementation would use external IDs
                            existing = HealthRecord.query.filter_by(
                                patient_id=patient.id,
                                title=record_obj.get('title'),
                                recorded_at=record_obj.get('recorded_at')
                            ).first()
                            
                            if not existing:
                                # Create new record
                                record = HealthRecord(
                                    patient_id=patient.id,
                                    record_type=record_obj.get('record_type', 'clinical_note'),
                                    title=record_obj.get('title', 'External Record'),
                                    content=record_obj.get('content', ''),
                                    recorded_by=user.id,  # Use patient's user ID as placeholder
                                    recorded_at=record_obj.get('recorded_at', datetime.utcnow())
                                )
                                
                                db.session.add(record)
                                db.session.commit()
                                
                                result['success'] += 1
                                result['items'].append({
                                    'type': 'health_record',
                                    'id': record.id,
                                    'action': 'created',
                                    'status': 'success'
                                })
                            else:
                                result['items'].append({
                                    'type': 'health_record',
                                    'id': existing.id,
                                    'action': 'skipped',
                                    'status': 'success',
                                    'note': 'Record already exists'
                                })
                    except Exception as e:
                        result['failed'] += 1
                        result['items'].append({
                            'type': 'health_record',
                            'action': 'failed',
                            'status': 'error',
                            'error': f"Processing error: {str(e)}"
                        })
            else:
                result['items'].append({
                    'type': 'health_records',
                    'status': 'failed',
                    'error': f"API error: {response.status_code if response else 'No response'}"
                })
        except Exception as e:
            result['items'].append({
                'type': 'health_records',
                'status': 'failed',
                'error': f"Request error: {str(e)}"
            })
                
        # 2. Pull and process medications (simplified)
        try:
            response = cls._make_api_request(
                system, connection, 'GET', endpoints['medications']
            )
            
            if response and response.status_code == 200:
                meds_data = response.json()
                
                for med_data in meds_data.get('medications', []):
                    try:
                        med_obj = cls._map_external_to_entity(
                            system.id, 'medication', med_data
                        )
                        
                        if med_obj:
                            # Check if medication already exists by name and dosage
                            existing = Medication.query.filter_by(
                                patient_id=patient.id,
                                name=med_obj.get('name'),
                                dosage=med_obj.get('dosage')
                            ).first()
                            
                            if not existing:
                                medication = Medication(
                                    patient_id=patient.id,
                                    name=med_obj.get('name'),
                                    dosage=med_obj.get('dosage'),
                                    frequency=med_obj.get('frequency'),
                                    start_date=med_obj.get('start_date'),
                                    end_date=med_obj.get('end_date'),
                                    instructions=med_obj.get('instructions'),
                                    is_active=True
                                )
                                
                                db.session.add(medication)
                                db.session.commit()
                                
                                result['success'] += 1
                                result['items'].append({
                                    'type': 'medication',
                                    'id': medication.id,
                                    'action': 'created',
                                    'status': 'success'
                                })
                            else:
                                # Update existing if needed
                                if med_obj.get('end_date') and not existing.end_date:
                                    existing.end_date = med_obj.get('end_date')
                                    db.session.commit()
                                    
                                    result['success'] += 1
                                    result['items'].append({
                                        'type': 'medication',
                                        'id': existing.id,
                                        'action': 'updated',
                                        'status': 'success'
                                    })
                                else:
                                    result['items'].append({
                                        'type': 'medication',
                                        'id': existing.id,
                                        'action': 'skipped',
                                        'status': 'success',
                                        'note': 'Medication already exists'
                                    })
                    except Exception as e:
                        result['failed'] += 1
                        result['items'].append({
                            'type': 'medication',
                            'action': 'failed',
                            'status': 'error',
                            'error': f"Processing error: {str(e)}"
                        })
            else:
                result['items'].append({
                    'type': 'medications',
                    'status': 'failed',
                    'error': f"API error: {response.status_code if response else 'No response'}"
                })
        except Exception as e:
            result['items'].append({
                'type': 'medications',
                'status': 'failed',
                'error': f"Request error: {str(e)}"
            })
        
        return result
    
    @classmethod
    def _map_entity_to_external(cls, system_id: int, entity_type: str, entity_obj) -> Dict:
        """
        Map an entity from our system to the external system's format
        
        Args:
            system_id: External system ID
            entity_type: Type of entity (patient, health_reading, etc.)
            entity_obj: The entity object from our database
            
        Returns:
            Dict: Mapped data in external system format
        """
        # Get data mappings for this entity type and system
        mappings = DataMapping.query.filter_by(
            system_id=system_id,
            entity_type=entity_type
        ).all()
        
        result = {}
        
        # Handle each entity type
        if entity_type == 'health_reading':
            # Default mapping for health readings
            reading = entity_obj
            result = {
                "observationType": reading.reading_type,
                "value": reading.value,
                "unit": reading.unit,
                "timestamp": reading.timestamp.isoformat(),
                "source": "6th Sense Platform"
            }
            
            # Add blood pressure specific fields
            if reading.reading_type == 'blood_pressure' and reading.value_systolic and reading.value_diastolic:
                result.update({
                    "systolic": reading.value_systolic,
                    "diastolic": reading.value_diastolic,
                    "pulse": reading.value_pulse
                })
                
        elif entity_type == 'medication':
            # Default mapping for medications
            medication = entity_obj
            result = {
                "medicationName": medication.name,
                "dosage": medication.dosage,
                "frequency": medication.frequency,
                "startDate": medication.start_date.isoformat() if medication.start_date else None,
                "endDate": medication.end_date.isoformat() if medication.end_date else None,
                "instructions": medication.instructions,
                "isActive": medication.is_active
            }
            
        # Apply custom mappings if defined
        for mapping in mappings:
            field_value = cls._get_field_value(entity_obj, mapping.our_field)
            
            # Transform value if needed
            if mapping.transformation_rule:
                try:
                    transform_rules = json.loads(mapping.transformation_rule)
                    field_value = cls._apply_transformation(field_value, transform_rules)
                except:
                    logging.error(f"Failed to apply transformation for {mapping.our_field}")
            
            result[mapping.external_field] = field_value
            
        return result
    
    @classmethod
    def _map_external_to_entity(cls, system_id: int, entity_type: str, external_data: Dict) -> Dict:
        """
        Map data from an external system to our internal format
        
        Args:
            system_id: External system ID
            entity_type: Type of entity (patient, health_record, etc.)
            external_data: Data from the external system
            
        Returns:
            Dict: Mapped data for our system
        """
        # Get data mappings for this entity type and system
        mappings = DataMapping.query.filter_by(
            system_id=system_id,
            entity_type=entity_type
        ).all()
        
        result = {}
        
        # Default mappings based on entity type
        if entity_type == 'health_record':
            result = {
                'record_type': 'clinical_note',
                'title': external_data.get('title', 'External Record'),
                'content': external_data.get('content', external_data.get('text', '')),
                'recorded_at': datetime.utcnow()
            }
            
            # Try to parse date if provided
            record_date = external_data.get('date')
            if record_date:
                try:
                    result['recorded_at'] = datetime.fromisoformat(record_date)
                except:
                    # Handle different date formats
                    try:
                        result['recorded_at'] = datetime.strptime(record_date, '%Y-%m-%d')
                    except:
                        pass
        
        elif entity_type == 'medication':
            result = {
                'name': external_data.get('medicationName', external_data.get('name', '')),
                'dosage': external_data.get('dosage', ''),
                'frequency': external_data.get('frequency', external_data.get('sig', '')),
                'instructions': external_data.get('instructions', '')
            }
            
            # Try to parse dates if provided
            start_date = external_data.get('startDate')
            if start_date:
                try:
                    result['start_date'] = datetime.fromisoformat(start_date)
                except:
                    try:
                        result['start_date'] = datetime.strptime(start_date, '%Y-%m-%d')
                    except:
                        pass
                        
            end_date = external_data.get('endDate')
            if end_date:
                try:
                    result['end_date'] = datetime.fromisoformat(end_date)
                except:
                    try:
                        result['end_date'] = datetime.strptime(end_date, '%Y-%m-%d')
                    except:
                        pass
        
        # Apply custom mappings if defined
        for mapping in mappings:
            if mapping.external_field in external_data:
                field_value = external_data[mapping.external_field]
                
                # Transform value if needed
                if mapping.transformation_rule:
                    try:
                        transform_rules = json.loads(mapping.transformation_rule)
                        field_value = cls._apply_transformation(field_value, transform_rules)
                    except:
                        logging.error(f"Failed to apply transformation for {mapping.external_field}")
                
                result[mapping.our_field] = field_value
                
        return result
    
    @staticmethod
    def _get_field_value(obj, field_name):
        """Get a field value from an object, handling nested attributes"""
        if hasattr(obj, field_name):
            return getattr(obj, field_name)
            
        # Handle dotted notation for nested fields
        if '.' in field_name:
            parts = field_name.split('.')
            current = obj
            
            for part in parts:
                if hasattr(current, part):
                    current = getattr(current, part)
                else:
                    return None
                    
            return current
            
        return None
    
    @staticmethod
    def _apply_transformation(value, rules):
        """Apply transformation rules to a value"""
        rule_type = rules.get('type')
        
        if rule_type == 'date_format':
            # Convert date format
            if isinstance(value, datetime):
                return value.strftime(rules.get('format', '%Y-%m-%d'))
            return value
            
        elif rule_type == 'mapping':
            # Map one value to another
            mapping_dict = rules.get('map', {})
            return mapping_dict.get(value, rules.get('default', value))
            
        elif rule_type == 'unit_conversion':
            # Convert units
            if rules.get('from') == 'mmol/L' and rules.get('to') == 'mg/dL':
                try:
                    return float(value) * 18
                except:
                    return value
            elif rules.get('from') == 'mg/dL' and rules.get('to') == 'mmol/L':
                try:
                    return float(value) / 18
                except:
                    return value
            
        return value


# Singleton instance
emr_service = EMRIntegrationService()