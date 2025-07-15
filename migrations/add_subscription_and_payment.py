"""
Migration script to add subscription fields to User model and create Payment table
"""
import os
import sys
import asyncio
import sqlite3

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings

# SQL statements for migration
ADD_SUBSCRIPTION_FIELDS = """
ALTER TABLE users 
ADD COLUMN subscription_tier VARCHAR(20) DEFAULT 'FREE' NOT NULL,
ADD COLUMN subscription_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL;
"""

CREATE_PAYMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    yativo_deposit_id VARCHAR(255),
    yativo_customer_id VARCHAR(255),
    amount FLOAT NOT NULL,
    currency VARCHAR(3) NOT NULL,
    tier VARCHAR(20) NOT NULL,
    payment_method VARCHAR(100),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checkout_url TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);
"""

def run_migration():
    """Run the migration"""
    print("Starting migration...")
    
    # Get database path from settings
    db_path = settings.DATABASE_PATH
    print(f"Using database at: {db_path}")
    
    try:
        # Connect to SQLite database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Add subscription fields to users table
        print("Adding subscription fields to users table...")
        try:
            cursor.execute(ADD_SUBSCRIPTION_FIELDS)
            print("Successfully added subscription fields")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("Subscription fields already exist, skipping...")
            else:
                raise
        
        # Create payments table
        print("Creating payments table...")
        cursor.execute(CREATE_PAYMENTS_TABLE)
        print("Successfully created payments table")
        
        # Commit changes
        conn.commit()
        print("Migration completed successfully!")
    except Exception as e:
        print(f"Error during migration: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    run_migration() 