"""Data transformation functions for parsing SMITE 2 Combat Log events."""
import re
import json
import logging
from typing import Dict, Any, Optional, Tuple, List, Set
from datetime import datetime

from smite_parser.models import (
    CombatEvent, RewardEvent, ItemEvent, PlayerEvent
)

logger = logging.getLogger("smite_parser")

# Regular expressions for parsing
TIME_FORMAT = "%Y-%m-%d-%H:%M:%S"
ROLE_PATTERN = re.compile(r"^E(.*?)$")  # Match role names like "EJungle" -> "Jungle"


def parse_timestamp(timestamp):
    """
    Parse a timestamp string into a datetime object.
    
    Args:
        timestamp: The timestamp string to parse
        
    Returns:
        datetime: The parsed datetime object, or None if parsing fails
    """
    # Try different timestamp formats
    timestamp_formats = [
        "%Y.%m.%d-%H.%M.%S",  # Format with dots: 2025.03.19-04.09.28
        "%Y-%m-%d-%H:%M:%S"   # Format with dashes and colons: 2025-03-19-04:09:28
    ]
    
    for fmt in timestamp_formats:
        try:
            return datetime.strptime(timestamp, fmt)
        except ValueError as e:
            # Try the next format
            continue
    
    # If we get here, none of the formats worked
    logger.debug(f"Could not parse timestamp: {timestamp}")
    return None


def convert_numeric(value_str: str) -> Optional[int]:
    """Convert a string value to an integer."""
    try:
        return int(value_str)
    except (ValueError, TypeError):
        logger.debug(f"Failed to convert to int: {value_str}")
        return None


def convert_float(value_str: str) -> Optional[float]:
    """Convert a string value to a float."""
    try:
        return float(value_str)
    except (ValueError, TypeError):
        logger.debug(f"Failed to convert to float: {value_str}")
        return None


def normalize_role_name(role_name: str) -> str:
    """Normalize role names (e.g., EJungle -> Jungle)."""
    match = ROLE_PATTERN.match(role_name)
    if match:
        return match.group(1)
    return role_name


def extract_team_id(value1: str) -> Optional[int]:
    """Extract team ID from value1 field."""
    try:
        team_id = int(value1)
        # Validate team ID (should be 1 or 2)
        if team_id in (1, 2):
            return team_id
        logger.warning(f"Invalid team ID: {team_id}")
        return None
    except (ValueError, TypeError):
        logger.debug(f"Failed to extract team ID from: {value1}")
        return None


def transform_combat_event(event: Dict[str, Any]) -> Optional[CombatEvent]:
    """Transform a combat event from the log format to database model.
    
    Args:
        event: Combat event dictionary
        
    Returns:
        CombatEvent model instance or None if transformation fails
    """
    if event.get("eventType") != "CombatMsg":
        return None
    
    # Parse timestamp 
    timestamp = None
    if "time" in event:
        timestamp = parse_timestamp(event["time"])
    
    # Extract location data - use convert_float as locations are floating point values
    location_x = convert_float(event.get("locationx"))
    location_y = convert_float(event.get("locationy"))
    
    # Extract relevant fields with proper field names
    return CombatEvent(
        timestamp=timestamp,  # Changed from event_time to timestamp to match model
        event_time=timestamp, # Keep event_time if it's also in the model
        event_type=event.get("type"),
        source_entity=event.get("sourceowner"),
        target_entity=event.get("targetowner"),
        ability_name=event.get("itemname"),  # Ability name is in itemname
        damage_amount=convert_numeric(event.get("value1")),
        damage_mitigated=convert_numeric(event.get("value2")),
        location_x=location_x,
        location_y=location_y,
        event_text=event.get("text")
    )


def transform_reward_event(event: Dict[str, Any]) -> Optional[RewardEvent]:
    """Transform a reward event from the log format to database model.
    
    Args:
        event: Reward event dictionary
        
    Returns:
        RewardEvent model instance or None if transformation fails
    """
    if event.get("eventType") != "RewardMsg":
        return None
    
    # Parse timestamp
    timestamp = None
    if "time" in event:
        timestamp = parse_timestamp(event["time"])
    
    # Extract entity name
    entity_name = event.get("sourceowner")
    
    # Extract location data - use convert_float as locations are floating point values
    location_x = convert_float(event.get("locationx"))
    location_y = convert_float(event.get("locationy"))
    
    # Extract relevant fields
    return RewardEvent(
        timestamp=timestamp,
        event_time=timestamp,
        event_type=event.get("type"),
        entity_name=entity_name,
        reward_amount=convert_numeric(event.get("value1")),
        source_type=event.get("itemname"),  # Source is often in itemname
        location_x=location_x,
        location_y=location_y,
        event_text=event.get("text")
    )


def transform_item_event(event: Dict[str, Any]) -> Optional[ItemEvent]:
    """Transform an item event from the log format to database model.
    
    Args:
        event: Item event dictionary
        
    Returns:
        ItemEvent model instance or None if transformation fails
    """
    if event.get("eventType") != "itemmsg":
        return None
    
    # Parse timestamp
    timestamp = None
    if "time" in event:
        timestamp = parse_timestamp(event["time"])
    
    # Extract player name
    player_name = event.get("sourceowner")
    
    # Extract location data - use convert_float as locations are floating point values
    location_x = convert_float(event.get("locationx"))
    location_y = convert_float(event.get("locationy"))
    
    # Determine event type
    event_type = event.get("type", "ItemPurchase")
    
    # Extract cost from text if value1 is not available or is zero
    cost = convert_numeric(event.get("value1"))
    if cost is None or cost == 0:
        # Try to extract cost from the text field
        text = event.get("text", "")
        if "(" in text and ")" in text:
            try:
                # Extract the value between parentheses as the cost
                cost_text = text.split("(")[-1].split(")")[0]
                cost = convert_numeric(cost_text)
            except (IndexError, ValueError):
                pass
    
    # Create item event
    return ItemEvent(
        timestamp=timestamp,
        event_time=timestamp,
        match_id=None,  # Will be set by the parser
        event_type=event_type,
        player_name=player_name,
        item_id=event.get("itemid"),
        item_name=event.get("itemname"),
        cost=cost,
        location_x=location_x,
        location_y=location_y,
        event_text=event.get("text")
    )


def transform_player_event(event: Dict[str, Any]) -> Optional[PlayerEvent]:
    """Transform a player event from the log format to database model.
    
    Args:
        event: Player event dictionary
        
    Returns:
        PlayerEvent model instance or None if transformation fails
    """
    if event.get("eventType") != "playermsg":
        return None
    
    # Parse timestamp
    timestamp = None
    if "time" in event:
        timestamp = parse_timestamp(event["time"])
    
    # Extract player name
    player_name = event.get("sourceowner")
    
    # Extract entity name - for player events, this is often the same as the player
    entity_name = player_name
    
    # Extract event type
    event_type = event.get("type")
    
    # Extract team ID
    team_id = convert_numeric(event.get("value1"))
    
    # Extract location data
    location_x = convert_float(event.get("locationx"))
    location_y = convert_float(event.get("locationy"))
    
    # For certain event types, provide default spawn locations if missing
    if (location_x is None or location_y is None) and event_type in ["RoleAssigned", "GodPicked", "GodHovered"]:
        if team_id == 1:  # Order team
            location_x = -10500.0
            location_y = 0.0
        elif team_id == 2:  # Chaos team
            location_x = 10500.0
            location_y = 0.0
    
    # Extract value
    value = event.get("value1")
    
    # Create player event
    return PlayerEvent(
        timestamp=timestamp,
        event_time=timestamp,
        match_id=None,  # Will be set by the parser
        event_type=event_type,
        player_name=player_name,
        entity_name=entity_name,  # Use player name as entity name
        team_id=team_id,
        value=value,
        item_id=convert_numeric(event.get("itemid")),
        item_name=event.get("itemname"),
        location_x=location_x,
        location_y=location_y,
        event_text=event.get("text")
    )


def categorize_entity(entity_name: str, player_names: Set[str]) -> str:
    """Categorize an entity as player, minion, monster, or objective."""
    if entity_name in player_names:
        return 'player'
    
    # Check common entity types
    lower_name = entity_name.lower()
    
    if 'tower' in lower_name or 'phoenix' in lower_name or 'titan' in lower_name:
        return 'objective'
    
    if ('archer' in lower_name or 'brute' in lower_name or 'swordsman' in lower_name or 
        'champion' in lower_name):
        return 'minion'
        
    if ('fury' in lower_name or 'pyromancer' in lower_name or 'harpy' in lower_name or 
        'satyr' in lower_name or 'cyclops' in lower_name or 'chimera' in lower_name or 
        'manticore' in lower_name or 'centaur' in lower_name or 'naga' in lower_name or
        'minotaur' in lower_name or 'scorpion' in lower_name):
        return 'jungle'
    
    return 'unknown'


def extract_assists(event: Dict[str, Any], players: List[str]) -> List[str]:
    """Extract assisting players from a KillingBlow event."""
    # This is placeholder logic - in a real implementation, we would 
    # need to analyze the event_text or other fields to determine assists
    # As the current data doesn't seem to include assist information directly
    return []


def extract_match_data(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract match data from events.
    
    Args:
        events: List of events
        
    Returns:
        Dictionary with match data
    """
    match_data = {
        "match_id": None,
        "map_name": "Unknown Map",  # Default value
        "game_type": "Unknown Mode",  # Default value
        "start_time": None,
        "end_time": None,
    }
    
    # Look for match metadata
    for event in events:
        # Check for match ID
        if "matchid" in event:
            match_data["match_id"] = event["matchid"]
        
        # Check for map name
        if "mapname" in event:
            match_data["map_name"] = event["mapname"]
        elif "map" in event:
            match_data["map_name"] = event["map"]
        
        # Check for game type/mode
        if "gametype" in event:
            match_data["game_type"] = event["gametype"]
        elif "gamemode" in event:
            match_data["game_type"] = event["gamemode"]
        elif "gameType" in event:
            match_data["game_type"] = event["gameType"]
        
        # Try to find event timestamps for start/end time
        if "time" in event:
            timestamp = parse_timestamp(event["time"])
            if timestamp:
                # Update start time if not set or earlier
                if not match_data["start_time"] or timestamp < match_data["start_time"]:
                    match_data["start_time"] = timestamp
                
                # Update end time if not set or later
                if not match_data["end_time"] or timestamp > match_data["end_time"]:
                    match_data["end_time"] = timestamp
    
    # Look for map name and game type in event text if not found
    for event in events:
        if "text" in event:
            text = event.get("text", "").lower()
            
            # Extract map name from text
            if match_data["map_name"] == "Unknown Map":
                map_indicators = ["conquest", "joust", "arena", "assault", "clash", "siege"]
                for indicator in map_indicators:
                    if indicator in text:
                        match_data["map_name"] = indicator.capitalize()
                        break
            
            # Extract game type from text
            if match_data["game_type"] == "Unknown Mode":
                mode_indicators = ["casual", "ranked", "custom", "tutorial", "practice"]
                for indicator in mode_indicators:
                    if indicator in text:
                        match_data["game_type"] = indicator.capitalize()
                        break
    
    return match_data


def extract_player_stats(
    combat_events: List[Dict[str, Any]], 
    reward_events: List[Dict[str, Any]],
    players: Set[str]
) -> Dict[str, Dict[str, Any]]:
    """Extract player statistics from events."""
    stats = {player: {
        'kills': 0,
        'deaths': 0,
        'assists': 0,
        'damage_dealt': 0,
        'damage_taken': 0,
        'healing_done': 0,
        'gold_earned': 0,
        'experience_earned': 0,
        'cc_time_inflicted': 0
    } for player in players}
    
    # Process combat events
    for event in combat_events:
        event_type = event.get('type')
        source = event.get('sourceowner')
        target = event.get('targetowner')
        value1 = event.get('value1', 0)
        
        if source in players:
            # Player is source
            if event_type == 'Damage':
                stats[source]['damage_dealt'] += value1
            elif event_type == 'Healing' and target in players:
                stats[source]['healing_done'] += value1
            elif event_type == 'KillingBlow' and target in players:
                stats[source]['kills'] += 1
            elif event_type == 'CrowdControl' and target in players:
                stats[source]['cc_time_inflicted'] += 1  # Placeholder, would need actual CC time
        
        if target in players:
            # Player is target
            if event_type == 'Damage':
                stats[target]['damage_taken'] += value1
            elif event_type == 'KillingBlow' and source in players:
                stats[target]['deaths'] += 1
    
    # Process reward events
    for event in reward_events:
        event_type = event.get('type')
        entity = event.get('sourceowner')
        value1 = event.get('value1', 0)
        
        if entity in players:
            if event_type == 'Currency':
                stats[entity]['gold_earned'] += value1
            elif event_type == 'Experience':
                stats[entity]['experience_earned'] += value1
    
    return stats 