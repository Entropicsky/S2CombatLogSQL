#!/usr/bin/env python3
"""
Script to reprocess timeline events using the enhanced timeline generator.

This script connects to an existing database, deletes all existing timeline events,
and generates new enhanced timeline events using the latest timeline generation logic.
"""

import os
import sys
import argparse
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from smite_parser.parser import CombatLogParser
from smite_parser.models import Match, TimelineEvent
from smite_parser.config.config import ParserConfig

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def reprocess_timeline(db_path, match_id=None):
    """Reprocess timeline events for the specified match.
    
    Args:
        db_path: Path to the SQLite database
        match_id: Optional match ID to reprocess. If None, reprocess all matches.
        
    Returns:
        True if reprocessing was successful, False otherwise
    """
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        return False
    
    try:
        # Create SQLAlchemy engine and session
        engine = create_engine(f"sqlite:///{db_path}")
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Find matches to reprocess
        if match_id:
            matches = session.query(Match).filter(Match.match_id == match_id).all()
            if not matches:
                logger.error(f"Match ID {match_id} not found in database")
                return False
        else:
            matches = session.query(Match).all()
            
        logger.info(f"Found {len(matches)} matches to reprocess")
        
        # Create parser with the session
        config = ParserConfig(db_path=db_path, show_progress=True)
        parser = CombatLogParser(config)
        
        for match in matches:
            logger.info(f"Reprocessing timeline for match {match.match_id}")
            
            # Delete existing timeline events
            deleted = session.query(TimelineEvent).filter(
                TimelineEvent.match_id == match.match_id
            ).delete()
            logger.info(f"Deleted {deleted} existing timeline events")
            
            # Set parser match ID
            parser.match_id = match.match_id
            
            # Collect player names for this match - use SQLAlchemy text()
            player_query = text("SELECT player_name FROM players WHERE match_id = :match_id")
            players = [row[0] for row in session.execute(player_query, {"match_id": match.match_id}).fetchall()]
            parser.player_names = set(players)
            
            # Generate new timeline events
            parser._generate_timeline_events(session)
            
            # Commit changes
            session.commit()
            
            # Count new timeline events
            new_count = session.query(TimelineEvent).filter(
                TimelineEvent.match_id == match.match_id
            ).count()
            logger.info(f"Generated {new_count} new timeline events")
        
        logger.info("Timeline reprocessing completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Reprocessing failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    finally:
        if 'session' in locals():
            session.close()


def main():
    """Main entry point for the reprocessing script."""
    parser = argparse.ArgumentParser(description="Reprocess timeline events")
    parser.add_argument("db_path", help="Path to the SQLite database file")
    parser.add_argument("--match-id", help="Optional specific match ID to reprocess")
    args = parser.parse_args()
    
    success = reprocess_timeline(args.db_path, args.match_id)
    
    if success:
        logger.info("Reprocessing completed successfully")
        return 0
    else:
        logger.error("Reprocessing failed")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 