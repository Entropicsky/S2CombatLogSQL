"""Parser module for the SMITE 2 Combat Log."""
import os
import json
import logging
import datetime
from datetime import timedelta
from typing import Dict, List, Optional, Set, Tuple, Any, Iterator
from collections import defaultdict
from tqdm import tqdm

from sqlalchemy import create_engine, func, select
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
        """Generate timeline events from raw events.
        
        Args:
            session: Database session
        """
        timeline_batch = []
        
        # Get major events for the timeline
        # 1. Kills (from both Kill and KillingBlow events)
        kill_events = session.query(CombatEvent).filter(
            CombatEvent.match_id == self.match_id,
            (CombatEvent.event_type == "Kill") | (CombatEvent.event_type == "KillingBlow"),
            CombatEvent.source_entity.in_(self.player_names),
            CombatEvent.target_entity.in_(self.player_names)
        ).all()
        
        for event in kill_events:
            timeline_event = TimelineEvent(
                match_id=self.match_id,
                timestamp=event.timestamp,
                event_time=event.event_time,
                event_description=f"{event.source_entity} killed {event.target_entity}",
                event_type="Kill",
                entity_name=event.source_entity,
                target_name=event.target_entity,
                location_x=event.location_x or 0.0,
                location_y=event.location_y or 0.0
            )
            timeline_batch.append(timeline_event)
        
        # 2. Major item purchases
        item_events = session.query(ItemEvent).filter(
            ItemEvent.event_type == "ItemPurchase",
            ItemEvent.match_id == self.match_id,
            ItemEvent.cost >= 1000  # High-value items only
        ).all()
        
        for event in item_events:
            timeline_event = TimelineEvent(
                match_id=self.match_id,
                timestamp=event.timestamp,
                event_time=event.event_time,
                event_description=f"{event.player_name} purchased {event.item_name}",
                event_type="ItemPurchase",
                entity_name=event.player_name,
                location_x=event.location_x or 0.0,
                location_y=event.location_y or 0.0
            )
            timeline_batch.append(timeline_event)
        
        # 3. Objective events (can be expanded based on more specific event types)
        objective_events = session.query(RewardEvent).filter(
            RewardEvent.match_id == self.match_id
        ).filter(
            (RewardEvent.event_type == "ObjectiveComplete") |
            (RewardEvent.event_type == "Structure") |
            (RewardEvent.event_type.like("%Objective%"))
        ).all()
        
        for event in objective_events:
            source_description = event.source_type or event.event_subtype or "Unknown"
            timeline_event = TimelineEvent(
                match_id=self.match_id,
                timestamp=event.timestamp,
                event_time=event.event_time,
                event_description=f"{event.entity_name} completed objective: {source_description}",
                event_type="Objective",
                entity_name=event.entity_name,
                location_x=event.location_x or 0.0,
                location_y=event.location_y or 0.0
            )
            timeline_batch.append(timeline_event)
        
        # 4. Add combat sequence starting events if no other events exist
        if not timeline_batch:
            self.logger.info("No kill or objective events found for timeline, adding combat sequences")
            # Get first combat event per player as a fallback
            first_events = session.query(CombatEvent).filter(
                CombatEvent.match_id == self.match_id,
                CombatEvent.source_entity.in_(self.player_names)
            ).order_by(CombatEvent.event_time).limit(10).all()
            
            for event in first_events:
                timeline_event = TimelineEvent(
                    match_id=self.match_id,
                    timestamp=event.timestamp,
                    event_time=event.event_time,
                    event_description=f"{event.source_entity} entered combat with {event.target_entity}",
                    event_type="CombatStart",
                    entity_name=event.source_entity,
                    target_name=event.target_entity,
                    location_x=event.location_x or 0.0,
                    location_y=event.location_y or 0.0
                )
                timeline_batch.append(timeline_event)
            
        # Add all timeline events to session
        if timeline_batch:
            self.logger.info(f"Adding {len(timeline_batch)} timeline events")
            timeline_batch = self._validate_event_batch(timeline_batch)
            session.add_all(timeline_batch)
            session.flush()
        else:
            self.logger.warning("No timeline events generated")
    
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