"""
File Upload Service
Handles file uploads for health records and manages file storage
"""

import os
import uuid
from werkzeug.utils import secure_filename
from datetime import datetime
from flask import current_app
from app import db
from models import HealthRecord

# Define allowed file extensions
ALLOWED_EXTENSIONS = {
    'pdf': 'application/pdf',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'gif': 'image/gif',
    'doc': 'application/msword',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'xls': 'application/vnd.ms-excel',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
}

# Base upload directory
UPLOAD_FOLDER = 'static/uploads'


def allowed_file(filename):
    """
    Check if the file extension is allowed
    
    Args:
        filename: The filename to check
        
    Returns:
        Boolean indicating if the file is allowed
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_file(file, patient_id, record_type, title, provider_id):
    """
    Save an uploaded file and create a HealthRecord
    
    Args:
        file: The file object from the request
        patient_id: ID of the patient this record belongs to
        record_type: Type of health record (lab_result, prescription, etc.)
        title: Title for the health record
        provider_id: ID of the provider uploading the file
        
    Returns:
        Tuple of (success, message, record_id)
    """
    try:
        if file and file.filename:
            if not allowed_file(file.filename):
                return False, "File type not allowed. Allowed types: PDF, images, and office documents.", None
            
            # Create a secure filename with a UUID to prevent collisions
            original_filename = secure_filename(file.filename)
            file_extension = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
            unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
            
            # Create patient directory if it doesn't exist
            patient_dir = os.path.join(UPLOAD_FOLDER, f"patient_{patient_id}")
            if not os.path.exists(patient_dir):
                os.makedirs(patient_dir)
            
            # Create record type subdirectory if it doesn't exist
            record_type_dir = os.path.join(patient_dir, record_type)
            if not os.path.exists(record_type_dir):
                os.makedirs(record_type_dir)
            
            # Full path to save the file
            file_path = os.path.join(record_type_dir, unique_filename)
            relative_path = os.path.join('uploads', f"patient_{patient_id}", record_type, unique_filename)
            
            # Save the file
            file.save(file_path)
            file.close()
            
            # Get file size
            file_size = os.path.getsize(file_path)
            
            # Create health record in database
            health_record = HealthRecord(
                patient_id=patient_id,
                record_type=record_type,
                title=title,
                content=f"Uploaded file: {original_filename}",
                recorded_by=provider_id,
                recorded_at=datetime.utcnow(),
                file_path=relative_path,
                file_type=file_extension,
                file_name=original_filename,
                file_size=file_size,
                is_file_record=True,
                upload_date=datetime.utcnow()
            )
            
            db.session.add(health_record)
            db.session.commit()
            
            return True, "File uploaded successfully", health_record.id
        else:
            return False, "No file provided", None
            
    except Exception as e:
        current_app.logger.error(f"Error uploading file: {str(e)}")
        return False, f"Error uploading file: {str(e)}", None


def delete_health_record_file(record_id):
    """
    Delete a health record and its associated file
    
    Args:
        record_id: ID of the health record to delete
        
    Returns:
        Tuple of (success, message)
    """
    try:
        health_record = HealthRecord.query.get(record_id)
        if not health_record:
            return False, "Record not found"
            
        if health_record.is_file_record and health_record.file_path:
            # Get absolute path 
            file_path = os.path.join('static', health_record.file_path)
            
            # Delete file if it exists
            if os.path.exists(file_path):
                os.remove(file_path)
                
        # Delete record from database
        db.session.delete(health_record)
        db.session.commit()
        
        return True, "Record deleted successfully"
        
    except Exception as e:
        current_app.logger.error(f"Error deleting health record: {str(e)}")
        return False, f"Error deleting health record: {str(e)}"


def get_file_path(record_id):
    """
    Get the file path for a health record
    
    Args:
        record_id: ID of the health record
        
    Returns:
        String with the file path or None if not found
    """
    try:
        health_record = HealthRecord.query.get(record_id)
        if health_record and health_record.is_file_record and health_record.file_path:
            return os.path.join('static', health_record.file_path)
        return None
    except Exception as e:
        current_app.logger.error(f"Error getting file path: {str(e)}")
        return None