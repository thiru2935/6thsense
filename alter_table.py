from app import app, db
import os
from sqlalchemy import text

"""
Script to add the new columns to the health_record table
"""

with app.app_context():
    # Check if we need to add the new columns
    try:
        # Execute SQL directly to add the necessary columns if they don't exist yet
        sql = text("""
        ALTER TABLE health_record 
        ADD COLUMN IF NOT EXISTS file_path VARCHAR(255),
        ADD COLUMN IF NOT EXISTS file_type VARCHAR(50),
        ADD COLUMN IF NOT EXISTS file_name VARCHAR(255),
        ADD COLUMN IF NOT EXISTS file_size INTEGER,
        ADD COLUMN IF NOT EXISTS is_file_record BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS upload_date TIMESTAMP
        """)
        
        db.session.execute(sql)
        db.session.commit()
        print("Successfully updated the health_record table schema.")
    except Exception as e:
        db.session.rollback()
        print(f"Error updating schema: {str(e)}")