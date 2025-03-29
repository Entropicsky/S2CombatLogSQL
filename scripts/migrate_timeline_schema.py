#!/usr/bin/env python3
"""
Migration script to update timeline_events schema with new fields.

This script adds new fields to the timeline_events table:
- event_category: Higher-level classification (Combat, Economy, Objective, etc.)
- importance: Rating from 1-10 of the event's significance 
- game_time_seconds: Time in seconds from match start
- team_id: Team associated with the event
- value: Numerical value (damage, gold, etc.)
- related_event_id: Link to another event
- other_entities: Comma-separated list of other entities involved
"""

import os
import sys
import argparse
import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def migrate_schema(db_path):
    """Migrate the timeline_events table schema in the given database.
    
    Args:
        db_path: Path to the SQLite database file
    
    Returns:
        True if migration was successful, False otherwise
    """
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        return False
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get current schema to check if columns already exist
        cursor.execute("PRAGMA table_info(timeline_events)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Add new columns if they don't exist
        new_columns = {
            "event_category": "VARCHAR",
            "importance": "INTEGER",
            "game_time_seconds": "INTEGER",
            "team_id": "INTEGER",
            "value": "FLOAT",
            "related_event_id": "INTEGER",
            "other_entities": "TEXT"
        }
        
        # Track added columns
        added_columns = []
        
        for col_name, col_type in new_columns.items():
            if col_name not in columns:
                logger.info(f"Adding column {col_name} ({col_type})")
                cursor.execute(f"ALTER TABLE timeline_events ADD COLUMN {col_name} {col_type}")
                added_columns.append(col_name)
        
        # Commit the changes
        conn.commit()
        
        if added_columns:
            logger.info(f"Added {len(added_columns)} new columns: {', '.join(added_columns)}")
        else:
            logger.info("No schema changes needed")
        
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()


def main():
    """Main entry point for the migration script."""
    parser = argparse.ArgumentParser(description="Migrate timeline_events schema")
    parser.add_argument("db_path", help="Path to the SQLite database file")
    args = parser.parse_args()
    
    success = migrate_schema(args.db_path)
    
    if success:
        logger.info("Migration completed successfully")
        return 0
    else:
        logger.error("Migration failed")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 