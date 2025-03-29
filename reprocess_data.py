#!/usr/bin/env python3
"""
Reprocess log file to fill in missing data.
This script directly uses internal components to fix data issues.
"""
import os
import sys
import logging
import json
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from smite_parser.config.config import ParserConfig, configure_logging  
from smite_parser.parser import CombatLogParser
from smite_parser.models import (
    Match, Player, PlayerStat, CombatEvent, RewardEvent, 
    ItemEvent, PlayerEvent, TimelineEvent
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def reprocess_log(log_file, db_file, batch_size=1000):
    """Reprocess a log file and update database correctly."""
    # Configure parser
    config = ParserConfig(
        db_path=db_file,
        batch_size=batch_size,
        show_progress=True,
        skip_malformed=True,
        log_level=logging.INFO,
    )
    
    logger.info(f"Reprocessing log file: {log_file}")
    logger.info(f"Target database: {db_file}")
    
    # Initialize database connection
    engine = create_engine(f"sqlite:///{db_file}")
    Session = sessionmaker(bind=engine)
    
    # Create parser
    parser = CombatLogParser(config)
    
    try:
        # First get the match IDs from the database
        with Session() as session:
            # Check existing matches in DB
            matches = session.query(Match).all()
            if not matches:
                logger.error("No matches found in database")
                return False
                
            logger.info(f"Found {len(matches)} matches in database")
            for match in matches:
                logger.info(f"Match ID: {match.match_id}, Source: {match.source_file}")
                
                # If this match is related to our log file
                if match.source_file and Path(match.source_file).stem == Path(log_file).stem:
                    match_id = match.match_id
                    logger.info(f"Found matching match ID: {match_id}")
                    
                    # Clear existing match data
                    logger.info(f"Clearing existing data for match ID: {match_id}")
                    
                    # Delete data from all tables in the correct order
                    session.query(TimelineEvent).filter_by(match_id=match_id).delete()
                    session.query(CombatEvent).filter_by(match_id=match_id).delete()
                    session.query(RewardEvent).filter_by(match_id=match_id).delete() 
                    session.query(ItemEvent).filter_by(match_id=match_id).delete()
                    session.query(PlayerEvent).filter_by(match_id=match_id).delete()
                    session.query(PlayerStat).filter_by(match_id=match_id).delete()
                    session.query(Player).filter_by(match_id=match_id).delete()
                    session.query(Match).filter_by(match_id=match_id).delete()
                    
                    session.commit()
                    logger.info(f"Successfully cleared data for match ID: {match_id}")
                    break
        
        # Now parse the whole file again
        success = parser.parse_file(log_file)
        
        if success:
            logger.info(f"Successfully reprocessed log file in {db_file}")
            return True
        else:
            logger.error("Failed to reprocess log file")
            return False
            
    except Exception as e:
        logger.error(f"Error during reprocessing: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_data(db_file):
    """Verify that data was properly populated."""
    engine = create_engine(f"sqlite:///{db_file}")
    Session = sessionmaker(bind=engine)
    
    with Session() as session:
        # Get match info
        match = session.query(Match).first()
        if not match:
            logger.error("No match data found in database")
            return False
        
        logger.info(f"Match ID: {match.match_id}")
        logger.info(f"Match duration: {match.duration_seconds} seconds")
        
        # Check combat events
        combat_events = session.query(CombatEvent).limit(5).all()
        if combat_events:
            logger.info("Sample combat events:")
            for event in combat_events:
                logger.info(f"  ID: {event.event_id}, Match ID: {event.match_id}, " 
                           f"Timestamp: {event.timestamp}, Event Time: {event.event_time}, "
                           f"Location: ({event.location_x}, {event.location_y})")
                
                # Verify required fields
                if not event.match_id:
                    logger.error("Combat event missing match_id")
                    return False
                if not event.timestamp:
                    logger.error("Combat event missing timestamp")
                    return False
                if event.location_x is None:
                    logger.error("Combat event missing location_x")
                    return False
                if event.location_y is None:
                    logger.error("Combat event missing location_y")
                    return False
        else:
            logger.error("No combat events found")
            return False
            
        # Check reward events
        reward_events = session.query(RewardEvent).limit(5).all()
        if reward_events:
            logger.info("Sample reward events:")
            for event in reward_events:
                logger.info(f"  ID: {event.event_id}, Match ID: {event.match_id}, " 
                           f"Timestamp: {event.timestamp}, Event Time: {event.event_time}, "
                           f"Location: ({event.location_x}, {event.location_y})")
                
                # Verify required fields
                if not event.match_id:
                    logger.error("Reward event missing match_id")
                    return False
                if not event.timestamp:
                    logger.error("Reward event missing timestamp")
                    return False
                if event.location_x is None:
                    logger.error("Reward event missing location_x")
                    return False
                if event.location_y is None:
                    logger.error("Reward event missing location_y")
                    return False
        else:
            logger.error("No reward events found")
            return False
            
        # Check item events
        item_events = session.query(ItemEvent).limit(5).all()
        if item_events:
            logger.info("Sample item events:")
            for event in item_events:
                logger.info(f"  ID: {event.event_id}, Match ID: {event.match_id}, " 
                           f"Timestamp: {event.timestamp}, Event Time: {event.event_time}, "
                           f"Location: ({event.location_x}, {event.location_y})")
                
                # Verify required fields
                if not event.match_id:
                    logger.error("Item event missing match_id")
                    return False
                if not event.timestamp:
                    logger.error("Item event missing timestamp")
                    return False
                if event.location_x is None:
                    logger.error("Item event missing location_x")
                    return False
                if event.location_y is None:
                    logger.error("Item event missing location_y")
                    return False
        else:
            logger.error("No item events found")
            return False
            
        # Check player events
        player_events = session.query(PlayerEvent).limit(5).all()
        if player_events:
            logger.info("Sample player events:")
            for event in player_events:
                logger.info(f"  ID: {event.event_id}, Match ID: {event.match_id}, " 
                           f"Timestamp: {event.timestamp}, Event Time: {event.event_time}, "
                           f"Location: ({event.location_x}, {event.location_y})")
                
                # Verify required fields
                if not event.match_id:
                    logger.error("Player event missing match_id")
                    return False
                if not event.timestamp:
                    logger.error("Player event missing timestamp")
                    return False
                if event.location_x is None:
                    logger.info("Player event location info missing - may be null for some events")
                if event.location_y is None:
                    logger.info("Player event location info missing - may be null for some events")
        else:
            logger.error("No player events found")
            return False
            
        # Check timeline events
        timeline_events = session.query(TimelineEvent).limit(5).all()
        if timeline_events:
            logger.info("Sample timeline events:")
            for event in timeline_events:
                logger.info(f"  ID: {event.event_id}, Match ID: {event.match_id}, " 
                           f"Timestamp: {event.timestamp}, Event Time: {event.event_time}")
                
                # Verify required fields
                if not event.match_id:
                    logger.error("Timeline event missing match_id")
                    return False
                if not event.timestamp:
                    logger.error("Timeline event missing timestamp")
                    return False
                if not event.event_time:
                    logger.error("Timeline event missing event_time")
                    return False
        else:
            logger.error("No timeline events found")
            return False
    
    logger.info("Data verification successful! All fields appear to be properly populated.")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <log_file> <db_file>")
        sys.exit(1)
    
    log_file = sys.argv[1]
    db_file = sys.argv[2]
    
    # Reprocess the log file
    success = reprocess_log(log_file, db_file)
    
    if success:
        # Verify the data
        if verify_data(db_file):
            print("Database update completed successfully!")
            sys.exit(0)
        else:
            print("Data verification failed.")
            sys.exit(1)
    else:
        print("Reprocessing failed.")
        sys.exit(1) 