"""
Database Migration Script - Update email table schema for new AI fields.
Run this once to update existing database structure.
"""

import sqlite3
from datetime import datetime, timezone


def migrate_database(db_path):
    """Update the emails table to support new AI analysis fields."""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Step 1: Add priority_score column (integer 1-5) with default 3
    print("Adding priority_score column...")
    cursor.execute("""
        ALTER TABLE emails ADD COLUMN IF NOT EXISTS priority_score INTEGER DEFAULT 3
    """)
    
    # Step 2: Add key_points column (JSON array)
    print("Adding key_points column...")
    cursor.execute("""
        ALTER TABLE emails ADD COLUMN IF NOT EXISTS key_points TEXT
    """)
    
    # Step 3: Add action_items column (JSON array)
    print("Adding action_items column...")
    cursor.execute("""
        ALTER TABLE emails ADD COLUMN IF NOT EXISTS action_items TEXT
    """)
    
    conn.commit()
    
    # Step 4: Update existing records to have default values for new columns
    print("Updating existing records with defaults...")
    
    # Set priority_score default for existing rows
    cursor.execute("""
        UPDATE emails SET priority_score = 3 WHERE priority_score IS NULL
    """)
    
    # Set key_points and action_items to empty JSON arrays
    cursor.execute("""
        UPDATE emails SET key_points = '[]', action_items = '[]' WHERE key_points IS NULL OR action_items IS NULL
    """)
    
    conn.commit()
    
    print(f"Migration complete! Updated {cursor.rowcount} records.")
    conn.close()


if __name__ == "__main__":
    import config
    
    db_path = config.DB_PATH
    print(f"Migrating database: {db_path}")
    migrate_database(db_path)
    print("Done!")
