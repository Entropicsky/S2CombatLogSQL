"""Parser module for the SMITE 2 Combat Log."""
import os
import json
import logging
import datetime
from datetime import timedelta
from typing import Dict, List, Optional, Set, Tuple, Any, Iterator
from collections import defaultdict
from tqdm import tqdm
import time
from pathlib import Path

from sqlalchemy import create_engine, func, select, or_
from sqlalchemy.orm import sessionmaker, Session

from smite_parser.config.config import ParserConfig
from smite_parser.models import (
    Base, Match, Player, Entity, CombatEvent, RewardEvent, 
    ItemEvent, PlayerEvent, PlayerStat, TimelineEvent, Item, Ability
)
from smite_parser.transformers import (
    transform_combat_event, transform_reward_event,
    transform_item_event, transform_player_event, parse_timestamp, categorize_entity, extract_match_data
)


class CombatLogParser:
    """Parser for SMITE 2 Combat Log files."""

    def __init__(self, config: ParserConfig):
        """Initialize the parser with the given configuration.
        
        Args:
            config: Parser configuration object
        """
        self.config = config
        self.logger = logging.getLogger("smite_parser")
        
        # Set up database connection
        self.engine = create_engine(f"sqlite:///{self.config.db_path}")
        self.Session = sessionmaker(bind=self.engine)
        
        # Create tables if they don't exist
        Base.metadata.create_all(self.engine)
        
        # Metadata collected during parsing
        self.player_names: Set[str] = set()
        self.entity_names: Set[str] = set()
        self.match_id: Optional[str] = None
        self.map_name: Optional[str] = None
        self.game_type: Optional[str] = None
        self.start_time: Optional[datetime.datetime] = None
        self.end_time: Optional[datetime.datetime] = None
        self.match_info = {}
        
    def parse_file(self, file_path: str) -> bool:
        """Parse a single combat log file.
        
        Args:
            file_path: Path to the combat log file to parse
            
        Returns:
            True if parsing was successful, False otherwise
        """
        self.logger.info(f"Parsing file: {file_path}")
        
        try:
            # Reset metadata
            self._reset_metadata()
            
            # Extract the file name without extension for match source
            base_name = os.path.basename(file_path)
            source_name = os.path.splitext(base_name)[0]
            
            # Store source name in match_info
            self.match_info['source_file'] = source_name
            
            # Read and parse the log file
            events = self._read_log_file(file_path)
            
            # Collect metadata from events
            self._collect_metadata(events)
            
            # Process events in batches and store in database
            with self.Session() as session:
                self._process_events(session, events)
            
            self.logger.info(f"Successfully parsed file: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error parsing file {file_path}: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    def _reset_metadata(self) -> None:
        """Reset metadata collected during parsing."""
        self.player_names = set()
        self.entity_names = set()
        self.match_id = None
        self.map_name = None
        self.game_type = None
        self.start_time = None
        self.end_time = None
    
    def _read_log_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Read and parse the log file.
        
        Args:
            file_path: Path to the log file
            
        Returns:
            List of parsed events
        """
        events = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            line_num = 0
            for line in f:
                line_num += 1
                line = line.strip()
                if not line:
                    continue
                
                # Remove trailing comma if present
                if line.endswith(','):
                    line = line[:-1]
                
                try:
                    # Try to parse as JSON
                    event = json.loads(line)
                    events.append(event)
                except json.JSONDecodeError as e:
                    if self.config.skip_malformed:
                        self.logger.warning(f"Skipping malformed JSON at line {line_num}: {e}")
                    else:
                        raise
        
        return events
    
    def _collect_metadata(self, events: List[Dict[str, Any]]) -> None:
        """Collect metadata from events.
        
        Args:
            events: List of parsed events
        """
        timestamps = []
        player_info = {}  # Store player info including role, team, etc.
        
        for event in events:
            # Extract timestamp from time field using the centralized parser
            if "time" in event:
                ts = parse_timestamp(event["time"])
                if ts:
                    timestamps.append(ts)
            
            # Extract match metadata
            if event.get("eventType") == "start":
                self.match_id = event.get("matchID")
                self.logger.info(f"Found match ID: {self.match_id}")
            
            # Track player names and roles
            if event.get("eventType") == "playermsg" and event.get("type") == "RoleAssigned":
                player_name = event.get("sourceowner")
                role_name = event.get("itemname")
                team_id = event.get("value1")
                
                if player_name and role_name and team_id:
                    if player_name not in player_info:
                        player_info[player_name] = {"role": role_name, "team_id": team_id}
                        self.player_names.add(player_name)
                        self.logger.debug(f"Found player: {player_name}, Role: {role_name}, Team: {team_id}")
            
            # Track all player names (not just roles)
            if "sourceowner" in event:
                source_owner = event.get("sourceowner")
                # Check if it's a player (not an NPC/monster)
                if source_owner and (event.get("eventType") == "playermsg" or 
                                     event.get("type") in ["Kill", "ItemPurchase"] or
                                     "Player" in source_owner):
                    self.player_names.add(source_owner)
            
            # Track entity names
            if "sourceowner" in event:
                self.entity_names.add(event["sourceowner"])
            if "targetowner" in event:
                self.entity_names.add(event["targetowner"])
        
        # Set start and end times
        if timestamps:
            self.start_time = min(timestamps)
            self.end_time = max(timestamps)
        
        self.logger.info(f"Collected {len(self.player_names)} player names: {self.player_names}")
    
    def _process_events(self, session: Session, events: List[Dict[str, Any]]) -> None:
        """Process events and store in database.
        
        Args:
            session: Database session
            events: List of parsed events
        """
        # Extract match metadata
        match_metadata = extract_match_data(events)
        
        # Handle datetime fields for JSON serialization
        serializable_metadata = {}
        for key, value in match_metadata.items():
            if isinstance(value, datetime.datetime):
                serializable_metadata[key] = value.isoformat()
            else:
                serializable_metadata[key] = value
        
        # Create match record
        self.match_id = self.match_id or match_metadata.get('match_id') or f"match-{self.match_info.get('source_file', 'unknown')}"
        match = Match(
            match_id=self.match_id,
            map_name=match_metadata.get('map_name', 'Unknown Map'),
            game_type=match_metadata.get('game_type', 'Unknown Mode'),
            start_time=self.start_time,
            end_time=self.end_time,
            source_file=self.match_info.get('source_file', 'unknown'),
            duration_seconds=(self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else None,
            match_data=json.dumps(serializable_metadata) if serializable_metadata else None
        )
        session.add(match)
        session.flush()  # Flush to ensure match_id is available
        
        # Create player records
        self._process_players(session, events)
        
        # Create entity records
        self._process_entities(session)
        
        # Process the main event types
        self._process_event_batches(session, events)
        
        # Commit the changes
        session.commit()
        
        # Generate derived data with the committed events
        self._generate_derived_data()
    
    def _process_players(self, session: Session, events: List[Dict[str, Any]]) -> None:
        """Process player data and create player records.
        
        Args:
            session: Database session
            events: List of parsed events
        """
        player_data = {}
        
        # Find player information from events
        for event in events:
            if event.get("eventType") == "playermsg" and event.get("type") == "RoleAssigned":
                player_name = event.get("sourceowner")
                role_name = event.get("itemname")
                team_id = event.get("value1")
                
                if player_name and role_name:
                    # Normalize role name
                    if role_name.startswith("E"):
                        role_name = role_name[1:]  # Remove 'E' prefix if present
                    
                    player_data[player_name] = {
                        "team_id": team_id,
                        "role": role_name
                    }
        
        # Find god information from GodPicked events
        for event in events:
            if event.get("eventType") == "playermsg" and event.get("type") == "GodPicked":
                player_name = event.get("sourceowner")
                god_name = event.get("itemname")
                god_id = event.get("itemid")
                
                if player_name and (god_name or god_id) and player_name in player_data:
                    player_data[player_name]["god_name"] = god_name
                    player_data[player_name]["god_id"] = god_id
        
        # Create player records
        for player_name, data in player_data.items():
            self.logger.info(f"Creating player record: {player_name}, Team: {data.get('team_id')}, Role: {data.get('role')}, God: {data.get('god_name')}")
            player = Player(
                match_id=self.match_id,
                player_name=player_name,
                team_id=data.get("team_id"),
                god_name=data.get("god_name"),
                god_id=data.get("god_id"),
                role=data.get("role")
            )
            session.add(player)
    
    def _process_entities(self, session: Session) -> None:
        """Process entity data and create entity records.
        
        Args:
            session: Database session
        """
        # Get all player names from the session for entity type classification
        player_names = set()
        for player in session.query(Player).filter_by(match_id=self.match_id).all():
            player_names.add(player.player_name)
        
        # Process each entity
        for entity_name in self.entity_names:
            if entity_name:
                # Determine entity type using categorize_entity
                entity_type = categorize_entity(entity_name, player_names)
                
                # Determine team_id based on entity type and name
                team_id = None
                if entity_type == 'player':
                    # For players, get team_id from players table
                    player = session.query(Player).filter_by(
                        match_id=self.match_id, 
                        player_name=entity_name
                    ).first()
                    if player:
                        team_id = player.team_id
                elif entity_type in ['objective', 'minion']:
                    # For objectives and minions, determine team from name if possible
                    lower_name = entity_name.lower()
                    if 'order' in lower_name:
                        team_id = 1
                    elif 'chaos' in lower_name:
                        team_id = 2
                
                entity = Entity(
                    entity_name=entity_name,
                    match_id=self.match_id,
                    entity_type=entity_type,
                    team_id=team_id
                )
                session.add(entity)
    
    def _process_event_batches(self, session: Session, events: List[Dict[str, Any]]) -> None:
        """Process events in batches.
        
        Args:
            session: Database session
            events: List of parsed events
        """
        # Group events by type
        combat_events = []
        reward_events = []
        item_events = []
        player_events = []
        
        for event in events:
            event_type = event.get("eventType")
            
            if event_type == "CombatMsg":
                combat_events.append(event)
            elif event_type == "RewardMsg":
                reward_events.append(event)
            elif event_type == "itemmsg":
                item_events.append(event)
            elif event_type == "playermsg":
                player_events.append(event)
        
        # Process items and abilities first to establish references
        if item_events:
            self._process_items(session, events)
        
        if combat_events:
            self._process_abilities(session, events)
        
        # Process each event type in batches
        if combat_events:
            self._process_combat_events(session, combat_events)
        
        if reward_events:
            self._process_reward_events(session, reward_events)
            
        if item_events:
            self._process_item_events(session, item_events)
            
        if player_events:
            self._process_player_events(session, player_events)
    
    def _validate_event_batch(self, batch):
        """Ensure all required fields are set in a batch of events.
        
        Args:
            batch: List of event objects
            
        Returns:
            The validated batch
        """
        self.logger.debug(f"Validating batch of {len(batch)} events, match_id={self.match_id}")
        for event in batch:
            # Ensure match_id is set
            if not event.match_id:
                self.logger.debug(f"Setting match_id={self.match_id} on {event.__class__.__name__}")
                event.match_id = self.match_id
                
            # Ensure timestamp is set if event_time is available
            if not event.timestamp and event.event_time:
                self.logger.debug(f"Setting timestamp from event_time for {event.__class__.__name__}")
                event.timestamp = event.event_time
                
        return batch
        
    def _process_combat_events(self, session: Session, events: List[Dict[str, Any]]) -> None:
        """Process combat events.
        
        Args:
            session: Database session
            events: List of combat events
        """
        batch = []
        
        for event in events:
            try:
                db_event = transform_combat_event(event)
                if db_event:
                    # Set the match ID
                    db_event.match_id = self.match_id
                    batch.append(db_event)
                
                if len(batch) >= self.config.batch_size:
                    # Validate batch before adding to session
                    batch = self._validate_event_batch(batch)
                    session.add_all(batch)
                    session.flush()
                    batch = []
            except Exception as e:
                self.logger.error(f"Error processing combat event: {str(e)}")
                if not self.config.skip_malformed:
                    raise
        
        # Add any remaining events
        if batch:
            # Validate batch before adding to session
            batch = self._validate_event_batch(batch)
            session.add_all(batch)
            session.flush()
    
    def _process_reward_events(self, session: Session, events: List[Dict[str, Any]]) -> None:
        """Process reward events.
        
        Args:
            session: Database session
            events: List of reward events
        """
        batch = []
        
        for event in events:
            try:
                db_event = transform_reward_event(event)
                if db_event:
                    # Set the match ID
                    db_event.match_id = self.match_id
                    batch.append(db_event)
                
                if len(batch) >= self.config.batch_size:
                    # Validate batch before adding to session
                    batch = self._validate_event_batch(batch)
                    session.add_all(batch)
                    session.flush()
                    batch = []
            except Exception as e:
                self.logger.error(f"Error processing reward event: {str(e)}")
                if not self.config.skip_malformed:
                    raise
        
        # Add any remaining events
        if batch:
            # Validate batch before adding to session
            batch = self._validate_event_batch(batch)
            session.add_all(batch)
            session.flush()
    
    def _process_item_events(self, session: Session, events: List[Dict[str, Any]]) -> None:
        """Process item events.
        
        Args:
            session: Database session
            events: List of item events
        """
        batch = []
        
        for event in events:
            try:
                db_event = transform_item_event(event)
                if db_event:
                    # Set the match ID
                    db_event.match_id = self.match_id
                    batch.append(db_event)
                
                if len(batch) >= self.config.batch_size:
                    # Validate batch before adding to session
                    batch = self._validate_event_batch(batch)
                    session.add_all(batch)
                    session.flush()
                    batch = []
            except Exception as e:
                self.logger.error(f"Error processing item event: {str(e)}")
                if not self.config.skip_malformed:
                    raise
        
        # Add any remaining events
        if batch:
            # Validate batch before adding to session
            batch = self._validate_event_batch(batch)
            session.add_all(batch)
            session.flush()
    
    def _process_player_events(self, session: Session, events: List[Dict[str, Any]]) -> None:
        """Process player events.
        
        Args:
            session: Database session
            events: List of player events
        """
        batch = []
        
        for event in events:
            try:
                db_event = transform_player_event(event)
                if db_event:
                    # Set the match ID
                    db_event.match_id = self.match_id
                    batch.append(db_event)
                
                if len(batch) >= self.config.batch_size:
                    # Validate batch before adding to session
                    batch = self._validate_event_batch(batch)
                    session.add_all(batch)
                    session.flush()
                    batch = []
            except Exception as e:
                self.logger.error(f"Error processing player event: {str(e)}")
                if not self.config.skip_malformed:
                    raise
        
        # Add any remaining events
        if batch:
            # Validate batch before adding to session
            batch = self._validate_event_batch(batch)
            session.add_all(batch)
            session.flush()
    
    def _generate_derived_data(self) -> None:
        """Generate derived data from the parsed events."""
        with self.Session() as session:
            self.logger.debug(f"Generating derived data for match_id={self.match_id}")
            
            # Calculate player statistics for each player
            for player_name in self.player_names:
                self._calculate_player_stats(session, player_name)
            
            # Generate timeline events
            self._generate_timeline_events(session)
            
            # Commit the changes
            session.commit()
    
    def _calculate_player_stats(self, session: Session, player_name: str) -> None:
        """Calculate and store player statistics.
        
        Args:
            session: Database session
            player_name: Player name
        """
        self.logger.info(f"Calculating stats for player: {player_name}")
        
        # Get player record
        player = session.query(Player).filter_by(
            match_id=self.match_id, 
            player_name=player_name
        ).first()
        
        if not player:
            self.logger.error(f"Player {player_name} not found in database")
            return
        
        # Get combat events involving this player
        combat_events = session.query(CombatEvent).filter_by(
            match_id=self.match_id
        ).filter(
            # Player is either source or target
            ((CombatEvent.source_entity == player_name) | 
             (CombatEvent.target_entity == player_name))
        ).all()
        
        # Initialize stats
        kills = 0
        deaths = 0
        assists = 0
        damage_dealt = 0
        damage_taken = 0
        healing_done = 0
        cc_time_inflicted = 0
        
        # Track already processed kills to avoid double counting
        processed_kills = set()
        
        # Track damage dealt to other players with timestamps
        # Format: {target_player: [(timestamp, damage)]}
        damage_to_players = {}
        
        # First pass: collect damage dealt to other players and calculate basic stats
        for event in combat_events:
            # Player dealt damage
            if event.source_entity == player_name and event.event_type == "Damage":
                damage_amount = event.damage_amount or 0
                damage_dealt += damage_amount
                
                # Record damage dealt to other players (for assist calculation)
                if event.target_entity in self.player_names and event.target_entity != player_name:
                    if event.target_entity not in damage_to_players:
                        damage_to_players[event.target_entity] = []
                    
                    damage_to_players[event.target_entity].append((event.timestamp, damage_amount))
                
            # Player took damage
            if event.target_entity == player_name and event.event_type == "Damage":
                damage_taken += event.damage_amount or 0
                
            # Player healed
            if event.source_entity == player_name and event.event_type == "Healing":
                healing_done += event.damage_amount or 0
                
            # Player applied crowd control
            if event.source_entity == player_name and event.event_type == "CrowdControl":
                cc_time_inflicted += 1  # We don't have duration, so count instances
                
            # Player killed someone (check for both Kill and KillingBlow)
            if event.source_entity == player_name and (event.event_type == "Kill" or event.event_type == "KillingBlow"):
                # Only count if the target is another player
                if event.target_entity in self.player_names:
                    # Check if this kill was already processed
                    kill_key = f"{event.timestamp}_{event.target_entity}"
                    if kill_key not in processed_kills:
                        kills += 1
                        processed_kills.add(kill_key)
                
            # Player died (check for both Kill and KillingBlow)
            if event.target_entity == player_name and (event.event_type == "Kill" or event.event_type == "KillingBlow"):
                if event.source_entity in self.player_names:
                    deaths += 1
        
        # Get all killing blows in the match for assist calculation
        kill_events = session.query(CombatEvent).filter(
            CombatEvent.match_id == self.match_id,
            (CombatEvent.event_type == "Kill") | (CombatEvent.event_type == "KillingBlow"),
            CombatEvent.source_entity.in_(self.player_names),
            CombatEvent.target_entity.in_(self.player_names),
            CombatEvent.source_entity != player_name  # Not kills by this player
        ).all()
        
        # Calculate assists by checking if player dealt damage to victims shortly before their deaths
        for kill_event in kill_events:
            killer = kill_event.source_entity
            victim = kill_event.target_entity
            kill_time = kill_event.timestamp
            
            # Skip if this player was the killer or victim
            if player_name == killer or player_name == victim:
                continue
            
            # Check if player damaged the victim before they died
            if victim in damage_to_players:
                # Find damage events within 10 seconds before the kill
                assist_window = timedelta(seconds=10)
                recent_damage = [
                    dmg for ts, dmg in damage_to_players[victim]
                    if kill_time - assist_window <= ts <= kill_time
                ]
                
                # Award assist if sufficient damage was dealt
                if sum(recent_damage) >= 50:  # Threshold for meaningful contribution
                    assists += 1
        
        # Get reward events for this player
        reward_events = session.query(RewardEvent).filter_by(
            match_id=self.match_id
        ).all()
        
        # Calculate gold and experience
        gold_earned = 0
        experience_earned = 0
        
        for event in reward_events:
            # Skip if event text doesn't contain player name
            if not event.event_text or player_name not in event.event_text:
                continue
                
            if event.source_type == "gold":
                gold_earned += event.reward_amount or 0
            elif event.source_type == "experience":
                experience_earned += event.reward_amount or 0
        
        # Create or update player stats
        stat = session.query(PlayerStat).filter_by(
            match_id=self.match_id, 
            player_name=player_name
        ).first()
        
        if not stat:
            stat = PlayerStat(
                match_id=self.match_id,
                player_name=player_name,
                team_id=player.team_id
            )
            session.add(stat)
        
        # Update stats
        stat.kills = kills
        stat.deaths = deaths
        stat.assists = assists
        stat.damage_dealt = damage_dealt
        stat.damage_taken = damage_taken
        stat.healing_done = healing_done
        stat.gold_earned = gold_earned
        stat.experience_earned = experience_earned
        stat.cc_time_inflicted = cc_time_inflicted
        
        session.commit()
    
    def _generate_timeline_events(self, session: Session) -> None:
        """Generate comprehensive timeline events from raw events.
        
        Creates a rich timeline with all significant match events categorized
        and prioritized for MOBA analysis.
        
        Args:
            session: Database session
        """
        self.logger.info("Generating enhanced timeline events")
        timeline_batch = []
        
        # Get match start time for game_time_seconds calculation
        match = session.query(Match).filter_by(match_id=self.match_id).first()
        if not match or not match.start_time:
            self.logger.warning("Match start time not available, game_time_seconds will not be calculated")
            match_start_time = None
        else:
            match_start_time = match.start_time
            
        # Generate timeline events by category
        # 1. Player kill events
        kill_events = self._generate_kill_timeline_events(session, match_start_time)
        timeline_batch.extend(kill_events)
        
        # 2. Objective events (towers, phoenix, titans, jungle bosses)
        objective_events = self._generate_objective_timeline_events(session, match_start_time)
        timeline_batch.extend(objective_events)
        
        # 3. Economy events (significant item purchases, gold spikes)
        economy_events = self._generate_economy_timeline_events(session, match_start_time)
        timeline_batch.extend(economy_events)
        
        # 4. Significant combat events (high damage, multi-target abilities)
        combat_events = self._generate_combat_timeline_events(session, match_start_time)
        timeline_batch.extend(combat_events)
        
        # 5. Crowd control and team fight events
        teamfight_events = self._generate_team_fight_timeline_events(session, match_start_time)
        timeline_batch.extend(teamfight_events)
        
        # 6. Player milestone events (role assignments, god picks, etc.)
        milestone_events = self._generate_milestone_timeline_events(session, match_start_time)
        timeline_batch.extend(milestone_events)
        
        # Add all timeline events to session
        if timeline_batch:
            self.logger.info(f"Adding {len(timeline_batch)} timeline events")
            timeline_batch = self._validate_event_batch(timeline_batch)
            session.add_all(timeline_batch)
            session.flush()
        else:
            self.logger.warning("No timeline events generated")
    
    def _calculate_game_time_seconds(self, event_time, match_start_time):
        """Calculate seconds elapsed since match start.
        
        Args:
            event_time: Event timestamp
            match_start_time: Match start timestamp
            
        Returns:
            Seconds elapsed or None if calculation not possible
        """
        if not match_start_time or not event_time:
            return None
            
        time_diff = event_time - match_start_time
        return int(time_diff.total_seconds())

    def clear_existing_match(self, session: Session, match_id: str) -> None:
        """Clear existing data for a match.
        
        Args:
            session: Database session
            match_id: Match ID to clear
        """
        self.logger.info(f"Clearing existing data for match ID: {match_id}")
        
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
        self.logger.info(f"Successfully cleared data for match ID: {match_id}")

    def _process_items(self, session: Session, events: List[Dict[str, Any]]) -> None:
        """Process unique items and create item records.
        
        Args:
            session: Database session
            events: List of events
        """
        # Set to track unique items
        unique_items = {}
        
        # Extract items from item events
        for event in events:
            if event.get("eventType") == "itemmsg" and event.get("type") == "ItemPurchase":
                item_id = event.get("itemid")
                item_name = event.get("itemname")
                
                if item_id and item_name and item_id not in unique_items:
                    unique_items[item_id] = item_name
        
        # Create item records for unique items
        for item_id, item_name in unique_items.items():
            try:
                # Convert item_id to int if it's a string
                item_id_int = int(item_id)
                
                # Determine item type based on name
                item_type = None
                lower_name = item_name.lower()
                
                if 'relic' in lower_name or 'beads' in lower_name or 'blink' in lower_name or 'shell' in lower_name:
                    item_type = 'Relic'
                elif 'potion' in lower_name or 'chalice' in lower_name:
                    item_type = 'Consumable'
                else:
                    item_type = 'Item'  # Default type
                
                # Create item record
                item = Item(
                    item_id=item_id_int,
                    item_name=item_name,
                    item_type=item_type
                )
                session.add(item)
            except (ValueError, TypeError) as e:
                self.logger.warning(f"Error creating item record for {item_id} - {item_name}: {e}")
                continue

    def _process_abilities(self, session: Session, events: List[Dict[str, Any]]) -> None:
        """Process unique abilities and create ability records.
        
        Args:
            session: Database session
            events: List of events
        """
        # Dictionary to track unique abilities by name
        unique_abilities = {}
        
        # Extract abilities from combat events
        for event in events:
            if event.get("eventType") == "CombatMsg":
                ability_name = event.get("itemname")
                source_entity = event.get("sourceowner")
                
                if ability_name and source_entity and ability_name not in unique_abilities:
                    unique_abilities[ability_name] = source_entity
        
        # Create ability records for unique abilities
        for ability_name, source_entity in unique_abilities.items():
            # Create ability record
            ability = Ability(
                match_id=self.match_id,
                ability_name=ability_name,
                ability_source=source_entity
            )
            session.add(ability) 

    def _generate_kill_timeline_events(self, session: Session, match_start_time):
        """Generate timeline events for player kills.
        
        Args:
            session: Database session
            match_start_time: Match start timestamp
            
        Returns:
            List of timeline events
        """
        timeline_events = []
        
        # Get player kill events (both Kill and KillingBlow types)
        kill_events = session.query(CombatEvent).filter(
            CombatEvent.match_id == self.match_id,
            (CombatEvent.event_type == "Kill") | (CombatEvent.event_type == "KillingBlow"),
            CombatEvent.source_entity.in_(self.player_names),
            CombatEvent.target_entity.in_(self.player_names)
        ).all()
        
        for event in kill_events:
            # Look for assists - players who damaged the target within 10 seconds before the kill
            assist_events = session.query(CombatEvent).filter(
                CombatEvent.match_id == self.match_id,
                CombatEvent.event_type == "Damage",
                CombatEvent.target_entity == event.target_entity,
                CombatEvent.source_entity.in_(self.player_names),
                CombatEvent.source_entity != event.source_entity,
                CombatEvent.event_time <= event.event_time,
                CombatEvent.event_time >= (event.event_time - datetime.timedelta(seconds=10))
            ).all()
            
            # Collect unique assist players
            assist_players = []
            for assist in assist_events:
                if assist.source_entity not in assist_players:
                    assist_players.append(assist.source_entity)
            
            # Get team_id for the killer
            killer_team_id = None
            player = session.query(Player).filter_by(
                match_id=self.match_id,
                player_name=event.source_entity
            ).first()
            if player:
                killer_team_id = player.team_id
            
            # Calculate importance based on context
            # Kills are base importance 7, multi-kills increase importance
            importance = 7
            
            # Set event description with assists if any
            if assist_players:
                assists_text = ", ".join(assist_players)
                event_description = f"{event.source_entity} killed {event.target_entity} (Assists: {assists_text})"
            else:
                event_description = f"{event.source_entity} killed {event.target_entity}"
            
            # Calculate game time in seconds
            game_time_seconds = self._calculate_game_time_seconds(event.event_time, match_start_time)
            
            # Create timeline event
            timeline_event = TimelineEvent(
                match_id=self.match_id,
                timestamp=event.timestamp,
                event_time=event.event_time,
                game_time_seconds=game_time_seconds,
                event_type="PlayerKill",
                event_category="Combat",
                importance=importance,
                event_description=event_description,
                entity_name=event.source_entity,
                target_name=event.target_entity,
                team_id=killer_team_id,
                location_x=event.location_x or 0.0,
                location_y=event.location_y or 0.0,
                value=1,  # 1 kill
                other_entities=",".join(assist_players) if assist_players else None
            )
            timeline_events.append(timeline_event)
            
        return timeline_events 

    def _generate_objective_timeline_events(self, session: Session, match_start_time):
        """Generate timeline events for objectives (towers, phoenixes, titans, jungle bosses).
        
        Args:
            session: Database session
            match_start_time: Match start timestamp
            
        Returns:
            List of timeline events
        """
        timeline_events = []
        
        # Define important objectives
        structure_keywords = ['Tower', 'Phoenix', 'Titan']
        jungle_boss_keywords = ['Gold Fury', 'Fire Giant', 'Pyromancer', 'Bull Demon']
        
        # 1. Look for structure destruction events in combat events
        structure_events = session.query(CombatEvent).filter(
            CombatEvent.match_id == self.match_id,
            (CombatEvent.event_type == "Kill") | (CombatEvent.event_type == "KillingBlow"),
            CombatEvent.source_entity.in_(self.player_names)
        ).filter(
            # Use SQL LIKE for each structure keyword
            or_(
                *[CombatEvent.target_entity.like(f'%{keyword}%') for keyword in structure_keywords]
            )
        ).all()
        
        for event in structure_events:
            # Determine objective type and set importance
            importance = 5  # Default importance
            event_type = "Unknown"
            
            if "Tower" in event.target_entity:
                event_type = "TowerDestroyed"
                importance = 6
            elif "Phoenix" in event.target_entity:
                event_type = "PhoenixDestroyed"
                importance = 8
            elif "Titan" in event.target_entity:
                event_type = "TitanKilled"
                importance = 10  # Highest importance - match ending event
            
            # Determine team of structure
            objective_team = None
            if "Order" in event.target_entity:
                objective_team = 1
            elif "Chaos" in event.target_entity:
                objective_team = 2
            
            # Get attacker team
            attacker_team = None
            player = session.query(Player).filter_by(
                match_id=self.match_id,
                player_name=event.source_entity
            ).first()
            if player:
                attacker_team = player.team_id
                
            # Calculate game time in seconds
            game_time_seconds = self._calculate_game_time_seconds(event.event_time, match_start_time)
            
            # Create event description
            if objective_team and attacker_team:
                if objective_team != attacker_team:
                    team_desc = "enemy" if objective_team != attacker_team else "friendly"
                    event_description = f"{event.source_entity} destroyed {team_desc} {event.target_entity}"
                else:
                    event_description = f"{event.source_entity} destroyed {event.target_entity}"
            else:
                event_description = f"{event.source_entity} destroyed {event.target_entity}"
            
            # Create timeline event
            timeline_event = TimelineEvent(
                match_id=self.match_id,
                timestamp=event.timestamp,
                event_time=event.event_time,
                game_time_seconds=game_time_seconds,
                event_type=event_type,
                event_category="Objective",
                importance=importance,
                event_description=event_description,
                entity_name=event.source_entity,
                target_name=event.target_entity,
                team_id=attacker_team,
                location_x=event.location_x or 0.0,
                location_y=event.location_y or 0.0,
                value=importance  # Use importance as value
            )
            timeline_events.append(timeline_event)
        
        # 2. Look for jungle boss kills
        jungle_boss_events = session.query(CombatEvent).filter(
            CombatEvent.match_id == self.match_id,
            (CombatEvent.event_type == "Kill") | (CombatEvent.event_type == "KillingBlow"),
            CombatEvent.source_entity.in_(self.player_names)
        ).filter(
            # Use SQL LIKE for each jungle boss keyword
            or_(
                *[CombatEvent.target_entity.like(f'%{keyword}%') for keyword in jungle_boss_keywords]
            )
        ).all()
        
        for event in jungle_boss_events:
            # Determine boss type and set importance
            importance = 7  # Default importance for jungle objectives
            event_type = "JungleBossKilled"
            
            if "Gold Fury" in event.target_entity:
                event_type = "GoldFuryKilled"
                importance = 7
            elif "Fire Giant" in event.target_entity:
                event_type = "FireGiantKilled"
                importance = 9
            elif "Pyromancer" in event.target_entity:
                event_type = "PyromancerKilled"
                importance = 6
            elif "Bull Demon" in event.target_entity:
                event_type = "BullDemonKilled"
                importance = 7
            
            # Get attacker team
            attacker_team = None
            player = session.query(Player).filter_by(
                match_id=self.match_id,
                player_name=event.source_entity
            ).first()
            if player:
                attacker_team = player.team_id
                
            # Calculate game time in seconds
            game_time_seconds = self._calculate_game_time_seconds(event.event_time, match_start_time)
            
            # Create timeline event
            timeline_event = TimelineEvent(
                match_id=self.match_id,
                timestamp=event.timestamp,
                event_time=event.event_time,
                game_time_seconds=game_time_seconds,
                event_type=event_type,
                event_category="Objective",
                importance=importance,
                event_description=f"{event.source_entity} defeated {event.target_entity}",
                entity_name=event.source_entity,
                target_name=event.target_entity,
                team_id=attacker_team,
                location_x=event.location_x or 0.0,
                location_y=event.location_y or 0.0,
                value=importance  # Use importance as value
            )
            timeline_events.append(timeline_event)
        
        # 3. Look for explicit objective events in reward events
        objective_rewards = session.query(RewardEvent).filter(
            RewardEvent.match_id == self.match_id
        ).filter(
            (RewardEvent.event_type == "ObjectiveComplete") |
            (RewardEvent.event_type == "Structure") |
            (RewardEvent.event_type.like("%Objective%"))
        ).all()
        
        for event in objective_rewards:
            # Calculate game time in seconds
            game_time_seconds = self._calculate_game_time_seconds(event.event_time, match_start_time)
            
            source_description = event.source_type or "Unknown"
            
            # Create timeline event
            timeline_event = TimelineEvent(
                match_id=self.match_id,
                timestamp=event.timestamp,
                event_time=event.event_time,
                game_time_seconds=game_time_seconds,
                event_type="ObjectiveReward",
                event_category="Objective",
                importance=6,
                event_description=f"{event.entity_name} completed objective: {source_description}",
                entity_name=event.entity_name,
                location_x=event.location_x or 0.0,
                location_y=event.location_y or 0.0,
                value=event.reward_amount or 0
            )
            timeline_events.append(timeline_event)
        
        return timeline_events 

    def _generate_economy_timeline_events(self, session: Session, match_start_time):
        """Generate timeline events for economy (item purchases, gold spikes).
        
        Args:
            session: Database session
            match_start_time: Match start timestamp
            
        Returns:
            List of timeline events
        """
        timeline_events = []
        
        # Define important item thresholds for different stages of the game
        early_game_threshold = 700   # Early game important items
        mid_game_threshold = 900     # Mid game important items
        late_game_threshold = 1200   # Late game important items
        
        # 1. Track significant item purchases
        item_events = session.query(ItemEvent).filter(
            ItemEvent.match_id == self.match_id,
            ItemEvent.event_type == "ItemPurchase"
        ).order_by(ItemEvent.event_time).all()
        
        # Track player's item build progression
        player_item_counts = {player: 0 for player in self.player_names}
        player_item_totals = {player: 0 for player in self.player_names}
        player_build_stage = {player: "early" for player in self.player_names}
        
        for event in item_events:
            if event.player_name not in self.player_names:
                continue
                
            player = event.player_name
            item_cost = event.cost or 0
            player_item_counts[player] = player_item_counts.get(player, 0) + 1
            player_item_totals[player] = player_item_totals.get(player, 0) + item_cost
            
            # Determine importance based on item cost and game stage
            importance = 3  # Default low importance
            
            # Update player's game stage based on total items purchased
            if player_item_counts[player] >= 12:
                player_build_stage[player] = "late"
            elif player_item_counts[player] >= 6:
                player_build_stage[player] = "mid"
                
            # Adjust thresholds based on game stage
            threshold = early_game_threshold
            if player_build_stage[player] == "mid":
                threshold = mid_game_threshold
            elif player_build_stage[player] == "late":
                threshold = late_game_threshold
                
            # Only include significant items based on cost and game stage
            if item_cost >= threshold:
                # Important items have higher importance
                if item_cost >= late_game_threshold:
                    importance = 6
                elif item_cost >= mid_game_threshold:
                    importance = 5
                else:
                    importance = 4
                    
                # Get player team
                player_team = None
                player_record = session.query(Player).filter_by(
                    match_id=self.match_id,
                    player_name=player
                ).first()
                if player_record:
                    player_team = player_record.team_id
                    
                # Calculate game time in seconds
                game_time_seconds = self._calculate_game_time_seconds(event.event_time, match_start_time)
                
                # Create timeline event
                timeline_event = TimelineEvent(
                    match_id=self.match_id,
                    timestamp=event.timestamp,
                    event_time=event.event_time,
                    game_time_seconds=game_time_seconds,
                    event_type="ItemPurchase",
                    event_category="Economy",
                    importance=importance,
                    event_description=f"{player} purchased {event.item_name} ({item_cost} gold)",
                    entity_name=player,
                    team_id=player_team,
                    location_x=event.location_x or 0.0,
                    location_y=event.location_y or 0.0,
                    value=item_cost
                )
                timeline_events.append(timeline_event)
        
        # 2. Track gold spike events from reward events
        reward_events = session.query(RewardEvent).filter(
            RewardEvent.match_id == self.match_id,
            RewardEvent.source_type == "gold",
            RewardEvent.reward_amount >= 200  # Only significant gold rewards
        ).all()
        
        for event in reward_events:
            if not event.event_text or not any(player in event.event_text for player in self.player_names):
                continue
                
            # Extract player name from event text (might need to be improved)
            player_name = None
            for player in self.player_names:
                if player in event.event_text:
                    player_name = player
                    break
                    
            if not player_name:
                continue
                
            # Get player team
            player_team = None
            player_record = session.query(Player).filter_by(
                match_id=self.match_id,
                player_name=player_name
            ).first()
            if player_record:
                player_team = player_record.team_id
                
            # Calculate game time in seconds
            game_time_seconds = self._calculate_game_time_seconds(event.event_time, match_start_time)
            
            # Create timeline event for significant gold rewards
            if event.reward_amount >= 500:
                importance = 5  # High gold spike
            else:
                importance = 4  # Medium gold spike
                
            # Create timeline event
            timeline_event = TimelineEvent(
                match_id=self.match_id,
                timestamp=event.timestamp,
                event_time=event.event_time,
                game_time_seconds=game_time_seconds,
                event_type="GoldReward",
                event_category="Economy",
                importance=importance,
                event_description=f"{player_name} received {event.reward_amount} gold",
                entity_name=player_name,
                team_id=player_team,
                location_x=event.location_x or 0.0,
                location_y=event.location_y or 0.0,
                value=event.reward_amount
            )
            timeline_events.append(timeline_event)
        
        return timeline_events 

    def _generate_combat_timeline_events(self, session: Session, match_start_time):
        """Generate timeline events for significant combat events.
        
        Args:
            session: Database session
            match_start_time: Match start timestamp
            
        Returns:
            List of timeline events
        """
        timeline_events = []
        
        # Define thresholds for significant damage
        high_damage_threshold = 300
        
        # 1. High damage events between players
        high_damage_events = session.query(CombatEvent).filter(
            CombatEvent.match_id == self.match_id,
            CombatEvent.event_type.in_(["Damage", "CritDamage"]),
            CombatEvent.source_entity.in_(self.player_names),
            CombatEvent.target_entity.in_(self.player_names),
            CombatEvent.damage_amount >= high_damage_threshold
        ).order_by(CombatEvent.event_time).all()
        
        for event in high_damage_events:
            # Get player team
            source_team = None
            player = session.query(Player).filter_by(
                match_id=self.match_id,
                player_name=event.source_entity
            ).first()
            if player:
                source_team = player.team_id
            
            # Calculate importance based on damage amount
            if event.damage_amount >= 500:
                importance = 6  # Very high damage
            elif event.damage_amount >= 400:
                importance = 5  # High damage
            else:
                importance = 4  # Significant damage
            
            # Calculate game time in seconds
            game_time_seconds = self._calculate_game_time_seconds(event.event_time, match_start_time)
            
            # Create event description with damage mitigation detail
            mitigation_text = ""
            if event.damage_mitigated and event.damage_mitigated > 0:
                mitigation_text = f" ({event.damage_mitigated} mitigated)"
                
            event_description = f"{event.source_entity} hit {event.target_entity} for {event.damage_amount} damage{mitigation_text} using {event.ability_name}"
            
            # Create timeline event
            timeline_event = TimelineEvent(
                match_id=self.match_id,
                timestamp=event.timestamp,
                event_time=event.event_time,
                game_time_seconds=game_time_seconds,
                event_type="HighDamage",
                event_category="Combat",
                importance=importance,
                event_description=event_description,
                entity_name=event.source_entity,
                target_name=event.target_entity,
                team_id=source_team,
                location_x=event.location_x or 0.0,
                location_y=event.location_y or 0.0,
                value=event.damage_amount
            )
            timeline_events.append(timeline_event)
            
        # 2. Significant healing events
        high_healing_threshold = 200
        healing_events = session.query(CombatEvent).filter(
            CombatEvent.match_id == self.match_id,
            CombatEvent.event_type == "Healing",
            CombatEvent.source_entity.in_(self.player_names),
            CombatEvent.damage_amount >= high_healing_threshold
        ).order_by(CombatEvent.event_time).all()
        
        for event in healing_events:
            # Get player team
            source_team = None
            player = session.query(Player).filter_by(
                match_id=self.match_id,
                player_name=event.source_entity
            ).first()
            if player:
                source_team = player.team_id
            
            # Calculate importance based on healing amount
            if event.damage_amount >= 400:
                importance = 5  # Very high healing
            elif event.damage_amount >= 300:
                importance = 4  # High healing
            else:
                importance = 3  # Significant healing
            
            # Calculate game time in seconds
            game_time_seconds = self._calculate_game_time_seconds(event.event_time, match_start_time)
            
            # Create event description
            target_text = event.target_entity if event.target_entity else "themselves"
            ability_text = f" using {event.ability_name}" if event.ability_name else ""
            event_description = f"{event.source_entity} healed {target_text} for {event.damage_amount}{ability_text}"
            
            # Create timeline event
            timeline_event = TimelineEvent(
                match_id=self.match_id,
                timestamp=event.timestamp,
                event_time=event.event_time,
                game_time_seconds=game_time_seconds,
                event_type="SignificantHealing",
                event_category="Combat",
                importance=importance,
                event_description=event_description,
                entity_name=event.source_entity,
                target_name=event.target_entity,
                team_id=source_team,
                location_x=event.location_x or 0.0,
                location_y=event.location_y or 0.0,
                value=event.damage_amount
            )
            timeline_events.append(timeline_event)
            
        return timeline_events 

    def _generate_team_fight_timeline_events(self, session: Session, match_start_time):
        """Generate timeline events for team fights.
        
        Args:
            session: Database session
            match_start_time: Match start timestamp
            
        Returns:
            List of timeline events
        """
        timeline_events = []
        
        # Get all combat events involving players
        combat_events = session.query(CombatEvent).filter(
            CombatEvent.match_id == self.match_id,
            CombatEvent.event_type.in_(["Damage", "CritDamage", "KillingBlow", "Kill"]),
            CombatEvent.source_entity.in_(self.player_names),
            CombatEvent.target_entity.in_(self.player_names)
        ).order_by(CombatEvent.event_time).all()
        
        if not combat_events:
            return timeline_events
        
        # Parameters for team fight detection
        team_fight_cooldown = 15  # seconds between combat events to consider part of same team fight
        min_participants = 4      # minimum number of unique players to consider a team fight
        min_team_representation = 2  # minimum players from each team
        
        # Track team fights
        current_fight = {
            'start_time': None,
            'end_time': None,
            'participants': set(),
            'team1_participants': set(),
            'team2_participants': set(),
            'kills': 0,
            'total_damage': 0,
            'events': []
        }
        
        team_fights = []
        player_teams = {}
        
        # Get player team mappings
        for player_name in self.player_names:
            player = session.query(Player).filter_by(
                match_id=self.match_id,
                player_name=player_name
            ).first()
            if player:
                player_teams[player_name] = player.team_id
        
        # Process combat events to identify team fights
        for i, event in enumerate(combat_events):
            source_team = player_teams.get(event.source_entity)
            target_team = player_teams.get(event.target_entity)
            
            # Skip events where we can't determine teams
            if not source_team or not target_team:
                continue
                
            # Skip friendly fire (same team)
            if source_team == target_team:
                continue
            
            # Extract damage amount
            damage_amount = event.damage_amount or 0
            
            # If no active fight or this event is too far after the last one, start a new fight
            if (current_fight['end_time'] is None or 
                (event.event_time - current_fight['end_time']).total_seconds() > team_fight_cooldown):
                
                # If we had a previous fight with enough participants, save it
                if (current_fight['end_time'] is not None and 
                    len(current_fight['participants']) >= min_participants and
                    len(current_fight['team1_participants']) >= min_team_representation and
                    len(current_fight['team2_participants']) >= min_team_representation):
                    
                    team_fights.append(current_fight)
                
                # Start a new fight
                current_fight = {
                    'start_time': event.event_time,
                    'end_time': event.event_time,
                    'participants': {event.source_entity, event.target_entity},
                    'team1_participants': {event.source_entity} if source_team == 1 else {event.target_entity} if target_team == 1 else set(),
                    'team2_participants': {event.source_entity} if source_team == 2 else {event.target_entity} if target_team == 2 else set(),
                    'kills': 1 if event.event_type in ["KillingBlow", "Kill"] else 0,
                    'total_damage': damage_amount,
                    'events': [event]
                }
            else:
                # Continue the current fight
                current_fight['end_time'] = event.event_time
                current_fight['participants'].add(event.source_entity)
                current_fight['participants'].add(event.target_entity)
                
                # Add to team participants
                if source_team == 1:
                    current_fight['team1_participants'].add(event.source_entity)
                elif source_team == 2:
                    current_fight['team2_participants'].add(event.source_entity)
                    
                if target_team == 1:
                    current_fight['team1_participants'].add(event.target_entity)
                elif target_team == 2:
                    current_fight['team2_participants'].add(event.target_entity)
                
                # Update fight stats
                if event.event_type in ["KillingBlow", "Kill"]:
                    current_fight['kills'] += 1
                current_fight['total_damage'] += damage_amount
                current_fight['events'].append(event)
        
        # Add the last fight if it qualifies
        if (current_fight['end_time'] is not None and 
            len(current_fight['participants']) >= min_participants and
            len(current_fight['team1_participants']) >= min_team_representation and
            len(current_fight['team2_participants']) >= min_team_representation):
            
            team_fights.append(current_fight)
        
        # Create timeline events for team fights
        for i, fight in enumerate(team_fights):
            # Calculate game time in seconds
            start_game_time = self._calculate_game_time_seconds(fight['start_time'], match_start_time)
            end_game_time = self._calculate_game_time_seconds(fight['end_time'], match_start_time)
            
            # Calculate duration
            duration_seconds = (fight['end_time'] - fight['start_time']).total_seconds()
            
            # Determine the outcome and importance
            fight_size = len(fight['participants'])
            importance = min(9, 5 + (fight_size // 2))  # Base importance on number of participants
            
            # Adjust importance based on kills
            if fight['kills'] >= 3:
                importance = min(10, importance + 1)
            
            # Create fight description
            team1_count = len(fight['team1_participants'])
            team2_count = len(fight['team2_participants'])
            
            event_description = f"Team fight: {team1_count} vs {team2_count} players for {int(duration_seconds)} seconds"
            if fight['kills'] > 0:
                event_description += f" with {fight['kills']} kill{'s' if fight['kills'] > 1 else ''}"
            
            # Create timeline event
            timeline_event = TimelineEvent(
                match_id=self.match_id,
                timestamp=fight['start_time'],
                event_time=fight['start_time'],
                game_time_seconds=start_game_time,
                event_type="TeamFight",
                event_category="Combat",
                importance=importance,
                event_description=event_description,
                entity_name=", ".join(list(fight['participants'])[:3]) + ("..." if len(fight['participants']) > 3 else ""),
                value=int(duration_seconds),
                other_entities=", ".join(fight['participants'])
            )
            timeline_events.append(timeline_event)
            
        return timeline_events 

    def _generate_milestone_timeline_events(self, session: Session, match_start_time):
        """Generate timeline events for player milestones.
        
        Args:
            session: Database session
            match_start_time: Match start timestamp
            
        Returns:
            List of timeline events
        """
        timeline_events = []
        
        # Track important milestones:
        # 1. First blood
        # 2. First item completion for each player
        # 3. Level milestones (level 5, 10, 15, 20)
        # 4. Kill streaks (3, 5, 7, 10)
        
        # 1. First blood
        first_kill = session.query(CombatEvent).filter(
            CombatEvent.match_id == self.match_id,
            CombatEvent.event_type.in_(["Kill", "KillingBlow"]),
            CombatEvent.source_entity.in_(self.player_names),
            CombatEvent.target_entity.in_(self.player_names)
        ).order_by(CombatEvent.event_time).first()
        
        if first_kill:
            # Get player team
            source_team = None
            player = session.query(Player).filter_by(
                match_id=self.match_id,
                player_name=first_kill.source_entity
            ).first()
            if player:
                source_team = player.team_id
            
            # Calculate game time in seconds
            game_time_seconds = self._calculate_game_time_seconds(first_kill.event_time, match_start_time)
            
            # Create event description
            event_description = f"First Blood! {first_kill.source_entity} killed {first_kill.target_entity}"
            
            # Create timeline event
            timeline_event = TimelineEvent(
                match_id=self.match_id,
                timestamp=first_kill.timestamp,
                event_time=first_kill.event_time,
                game_time_seconds=game_time_seconds,
                event_type="FirstBlood",
                event_category="Milestone",
                importance=8,  # First blood is important!
                event_description=event_description,
                entity_name=first_kill.source_entity,
                target_name=first_kill.target_entity,
                team_id=source_team
            )
            timeline_events.append(timeline_event)
        
        # 2. First item completion for each player
        for player_name in self.player_names:
            first_item = session.query(ItemEvent).filter(
                ItemEvent.match_id == self.match_id,
                ItemEvent.player_name == player_name,
                ItemEvent.event_type == "ItemPurchase",
                ItemEvent.cost > 500  # Only consider significant items (not consumables)
            ).order_by(ItemEvent.event_time).first()
            
            if first_item:
                # Get player team
                source_team = None
                player = session.query(Player).filter_by(
                    match_id=self.match_id,
                    player_name=player_name
                ).first()
                if player:
                    source_team = player.team_id
                
                # Calculate game time in seconds
                game_time_seconds = self._calculate_game_time_seconds(first_item.event_time, match_start_time)
                
                # Create event description
                event_description = f"{player_name} completed first major item: {first_item.item_name} for {first_item.cost} gold"
                
                # Create timeline event
                timeline_event = TimelineEvent(
                    match_id=self.match_id,
                    timestamp=first_item.timestamp,
                    event_time=first_item.event_time,
                    game_time_seconds=game_time_seconds,
                    event_type="FirstItem",
                    event_category="Milestone",
                    importance=5,  # Moderate importance
                    event_description=event_description,
                    entity_name=player_name,
                    team_id=source_team,
                    value=first_item.cost
                )
                timeline_events.append(timeline_event)
        
        # 3. Level milestones (level 5, 10, 15, 20)
        important_levels = [5, 10, 15, 20]
        
        # Get all level up events
        level_events = session.query(CombatEvent).filter(
            CombatEvent.match_id == self.match_id,
            CombatEvent.event_type == "LevelUp",
            CombatEvent.source_entity.in_(self.player_names)
        ).order_by(CombatEvent.event_time).all()
        
        # Track player levels
        player_levels = {player: 1 for player in self.player_names}
        
        for event in level_events:
            player_name = event.source_entity
            
            # Skip if not a player
            if player_name not in self.player_names:
                continue
                
            # Extract level from event text if possible
            try:
                level = int(event.event_text.split("level")[1].strip())
                player_levels[player_name] = level
            except (IndexError, ValueError, AttributeError):
                # If we can't extract the level, increment by 1
                player_levels[player_name] += 1
                level = player_levels[player_name]
            
            # Only create events for important levels
            if level in important_levels:
                # Get player team
                source_team = None
                player = session.query(Player).filter_by(
                    match_id=self.match_id,
                    player_name=player_name
                ).first()
                if player:
                    source_team = player.team_id
                
                # Calculate game time in seconds
                game_time_seconds = self._calculate_game_time_seconds(event.event_time, match_start_time)
                
                # Calculate importance based on level
                importance = 3 + (level // 5)  # Level 5=4, 10=5, 15=6, 20=7
                
                # Create event description
                event_description = f"{player_name} reached level {level}"
                
                # Create timeline event
                timeline_event = TimelineEvent(
                    match_id=self.match_id,
                    timestamp=event.timestamp,
                    event_time=event.event_time,
                    game_time_seconds=game_time_seconds,
                    event_type="LevelMilestone",
                    event_category="Milestone",
                    importance=importance,
                    event_description=event_description,
                    entity_name=player_name,
                    team_id=source_team,
                    value=level
                )
                timeline_events.append(timeline_event)
        
        # 4. Kill streaks (3, 5, 7, 10)
        important_streaks = [3, 5, 7, 10]
        player_kill_streaks = {player: 0 for player in self.player_names}
        player_streak_events = {player: {} for player in self.player_names}
        
        # Get all kill events in order
        kill_events = session.query(CombatEvent).filter(
            CombatEvent.match_id == self.match_id,
            CombatEvent.event_type.in_(["Kill", "KillingBlow"]),
            CombatEvent.source_entity.in_(self.player_names)
        ).order_by(CombatEvent.event_time).all()
        
        # Process the events to track streaks
        for event in kill_events:
            killer = event.source_entity
            victim = event.target_entity
            
            # Only count player kills
            if victim not in self.player_names:
                continue
                
            # Increment the killer's streak
            player_kill_streaks[killer] += 1
            current_streak = player_kill_streaks[killer]
            
            # Check if the streak is important
            if current_streak in important_streaks:
                # Get player team
                source_team = None
                player = session.query(Player).filter_by(
                    match_id=self.match_id,
                    player_name=killer
                ).first()
                if player:
                    source_team = player.team_id
                
                # Calculate game time in seconds
                game_time_seconds = self._calculate_game_time_seconds(event.event_time, match_start_time)
                
                # Calculate importance based on streak
                importance = 4 + (current_streak // 3)  # 3=5, 5=6, 7=7, 10=8
                
                # Create event description
                event_description = f"{killer} is on a {current_streak}-player kill streak!"
                
                # Create timeline event
                timeline_event = TimelineEvent(
                    match_id=self.match_id,
                    timestamp=event.timestamp,
                    event_time=event.event_time,
                    game_time_seconds=game_time_seconds,
                    event_type="KillStreak",
                    event_category="Milestone",
                    importance=importance,
                    event_description=event_description,
                    entity_name=killer,
                    team_id=source_team,
                    value=current_streak
                )
                timeline_events.append(timeline_event)
                
                # Store this streak event
                player_streak_events[killer][current_streak] = timeline_event
            
            # Reset the victim's streak and check if they had a streak
            prev_streak = player_kill_streaks[victim]
            player_kill_streaks[victim] = 0
            
            # Check if the victim had an important streak that was ended
            if prev_streak >= 3:
                # Find the highest streak event that was recorded
                highest_streak = 0
                for streak in important_streaks:
                    if streak <= prev_streak and streak in player_streak_events[victim]:
                        highest_streak = streak
                
                if highest_streak > 0:
                    # Get the streak event
                    streak_event = player_streak_events[victim][highest_streak]
                    
                    # Get player team
                    source_team = None
                    player = session.query(Player).filter_by(
                        match_id=self.match_id,
                        player_name=killer
                    ).first()
                    if player:
                        source_team = player.team_id
                    
                    # Calculate game time in seconds
                    game_time_seconds = self._calculate_game_time_seconds(event.event_time, match_start_time)
                    
                    # Calculate importance based on ended streak
                    importance = 4 + (prev_streak // 3)  # Similar to starting a streak
                    
                    # Create event description
                    event_description = f"{killer} ended {victim}'s {prev_streak}-player kill streak!"
                    
                    # Create timeline event
                    timeline_event = TimelineEvent(
                        match_id=self.match_id,
                        timestamp=event.timestamp,
                        event_time=event.event_time,
                        game_time_seconds=game_time_seconds,
                        event_type="KillStreakEnded",
                        event_category="Milestone",
                        importance=importance,
                        event_description=event_description,
                        entity_name=killer,
                        target_name=victim,
                        team_id=source_team,
                        value=prev_streak,
                        related_event_id=streak_event.id if hasattr(streak_event, 'id') else None
                    )
                    timeline_events.append(timeline_event)
        
        return timeline_events 