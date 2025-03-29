#!/usr/bin/env python3
"""
Script to enhance timeline events in SMITE 2 combat log databases.

This script performs two steps:
1. Migrates the database schema to add new fields to timeline_events
2. Reprocesses the timeline events using the enhanced generator

Usage:
    python enhance_timeline.py path/to/database.db
"""

import os
import sys
import logging
import argparse
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get the project root directory
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)

# Add the project root to sys.path
sys.path.insert(0, project_root)

# Import project modules
from scripts.migrate_timeline_schema import migrate_schema
from scripts.reprocess_timeline import reprocess_timeline


def enhance_timeline(db_path, match_id=None, force=False):
    """
    Enhance timeline events in the database.
    
    Args:
        db_path: Path to the SQLite database
        match_id: Optional match ID to reprocess. If None, reprocess all matches.
        force: Force reprocessing even if migration indicates no changes needed
        
    Returns:
        True if enhancement was successful, False otherwise
    """
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        return False
    
    # Step 1: Migrate the schema
    logger.info(f"Migrating schema for {db_path}")
    migration_success = migrate_schema(db_path)
    
    if not migration_success:
        logger.error("Schema migration failed")
        return False
    
    # Step 2: Reprocess timeline events
    if force or migration_success:
        logger.info(f"Reprocessing timeline events for {db_path}")
        reprocess_success = reprocess_timeline(db_path, match_id)
        
        if not reprocess_success:
            logger.error("Timeline reprocessing failed")
            return False
    else:
        logger.info("No schema changes needed, skipping reprocessing (use --force to override)")
    
    logger.info("Timeline enhancement completed successfully")
    return True


def main():
    """Main entry point for the enhancement script."""
    parser = argparse.ArgumentParser(description="Enhance timeline events in SMITE 2 combat log databases")
    parser.add_argument("db_path", help="Path to the SQLite database file")
    parser.add_argument("--match-id", help="Optional specific match ID to reprocess")
    parser.add_argument("--force", action="store_true", help="Force reprocessing even if no schema changes")
    args = parser.parse_args()
    
    success = enhance_timeline(args.db_path, args.match_id, args.force)
    
    if success:
        logger.info("Enhancement completed successfully")
        return 0
    else:
        logger.error("Enhancement failed")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 