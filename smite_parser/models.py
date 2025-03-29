"""Database models for SMITE 2 Combat Log Parser."""
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, 
    ForeignKey, Text, Boolean, create_engine, MetaData
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Match(Base):
    """Match table storing information about each parsed match."""
    __tablename__ = 'matches'
    
    match_id = Column(String, primary_key=True)
    source_file = Column(String, nullable=False)
    map_name = Column(String, nullable=True)
    game_type = Column(String, nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    match_data = Column(Text, nullable=True)  # JSON data
    
    # Relationships
    players = relationship("Player", back_populates="match", cascade="all, delete-orphan")
    entities = relationship("Entity", back_populates="match", cascade="all, delete-orphan")
    combat_events = relationship("CombatEvent", back_populates="match", cascade="all, delete-orphan")
    reward_events = relationship("RewardEvent", back_populates="match", cascade="all, delete-orphan")
    item_events = relationship("ItemEvent", back_populates="match", cascade="all, delete-orphan")
    player_events = relationship("PlayerEvent", back_populates="match", cascade="all, delete-orphan")
    abilities = relationship("Ability", back_populates="match", cascade="all, delete-orphan")
    player_stats = relationship("PlayerStat", back_populates="match", cascade="all, delete-orphan")
    timeline_events = relationship("TimelineEvent", back_populates="match", cascade="all, delete-orphan")


class Player(Base):
    """Player table storing normalized player information."""
    __tablename__ = 'players'
    
    player_id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, ForeignKey('matches.match_id'), nullable=True)  # Allow null for initial creation
    player_name = Column(String, nullable=False)
    team_id = Column(Integer, nullable=True)
    role = Column(String, nullable=True)
    god_id = Column(Integer, nullable=True)
    god_name = Column(String, nullable=True)
    
    # Relationships
    match = relationship("Match", back_populates="players")


class Entity(Base):
    """Entity table storing information about all game entities."""
    __tablename__ = 'entities'
    
    entity_id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, ForeignKey('matches.match_id'), nullable=True)  # Allow null for initial creation
    entity_name = Column(String, nullable=False)
    entity_type = Column(String, nullable=True)
    team_id = Column(Integer, nullable=True)
    
    # Relationships
    match = relationship("Match", back_populates="entities")


class Item(Base):
    """Item table storing information about items in the game."""
    __tablename__ = 'items'
    
    item_id = Column(Integer, primary_key=True)
    item_name = Column(String, nullable=False)
    item_type = Column(String, nullable=True)


class Ability(Base):
    """Ability table storing information about abilities used in the game."""
    __tablename__ = 'abilities'
    
    ability_id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, ForeignKey('matches.match_id'), nullable=False)
    ability_name = Column(String, nullable=False)
    ability_source = Column(String, nullable=True)
    
    # Relationships
    match = relationship("Match", back_populates="abilities")


class CombatEvent(Base):
    """Combat event table storing all combat-related events."""
    __tablename__ = 'combat_events'
    
    event_id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, ForeignKey('matches.match_id'), nullable=True)  # Allow null for initial creation
    event_time = Column(DateTime, nullable=False)
    timestamp = Column(DateTime, nullable=True)  # For compatibility
    event_type = Column(String, nullable=False)
    source_entity = Column(String, nullable=True)
    target_entity = Column(String, nullable=True)
    ability_name = Column(String, nullable=True)
    location_x = Column(Float, nullable=True)
    location_y = Column(Float, nullable=True)
    damage_amount = Column(Integer, nullable=True)
    damage_mitigated = Column(Integer, nullable=True)
    event_text = Column(Text, nullable=True)
    
    # Relationships
    match = relationship("Match", back_populates="combat_events")


class RewardEvent(Base):
    """Reward event table storing experience and currency rewards."""
    __tablename__ = 'reward_events'
    
    event_id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, ForeignKey('matches.match_id'), nullable=True)  # Allow null for initial creation
    event_time = Column(DateTime, nullable=False)
    timestamp = Column(DateTime, nullable=True)  # For compatibility
    event_type = Column(String, nullable=False)
    entity_name = Column(String, nullable=True)
    location_x = Column(Float, nullable=True)
    location_y = Column(Float, nullable=True)
    reward_amount = Column(Integer, nullable=True)
    source_type = Column(String, nullable=True)
    event_text = Column(Text, nullable=True)
    
    # Relationships
    match = relationship("Match", back_populates="reward_events")


class ItemEvent(Base):
    """Item event table storing item purchase events."""
    __tablename__ = 'item_events'
    
    event_id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, ForeignKey('matches.match_id'), nullable=True)  # Allow null for initial creation
    event_time = Column(DateTime, nullable=False)
    timestamp = Column(DateTime, nullable=True)  # For compatibility
    event_type = Column(String, nullable=True)  # Added event_type field
    player_name = Column(String, nullable=True)
    item_id = Column(Integer, nullable=True)
    item_name = Column(String, nullable=True)
    location_x = Column(Float, nullable=True)
    location_y = Column(Float, nullable=True)
    cost = Column(Integer, nullable=True)
    event_text = Column(Text, nullable=True)
    
    # Relationships
    match = relationship("Match", back_populates="item_events")


class PlayerEvent(Base):
    """Player event table storing player-specific events."""
    __tablename__ = 'player_events'
    
    event_id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, ForeignKey('matches.match_id'), nullable=True)  # Allow null for initial creation
    event_time = Column(DateTime, nullable=False)
    timestamp = Column(DateTime, nullable=True)  # For compatibility
    event_type = Column(String, nullable=False)
    player_name = Column(String, nullable=True)
    entity_name = Column(String, nullable=True)  # Target entity name
    team_id = Column(Integer, nullable=True)
    value = Column(String, nullable=True)
    item_id = Column(Integer, nullable=True)
    item_name = Column(String, nullable=True)
    location_x = Column(Float, nullable=True)  # Added location field
    location_y = Column(Float, nullable=True)  # Added location field
    event_text = Column(Text, nullable=True)
    
    # Relationships
    match = relationship("Match", back_populates="player_events")


class PlayerStat(Base):
    """Player stat table storing aggregated player statistics per match."""
    __tablename__ = 'player_stats'
    
    stat_id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, ForeignKey('matches.match_id'), nullable=True)  # Allow null for initial creation
    player_name = Column(String, nullable=False)
    team_id = Column(Integer, nullable=True)
    kills = Column(Integer, nullable=True, default=0)
    deaths = Column(Integer, nullable=True, default=0)
    assists = Column(Integer, nullable=True, default=0)
    damage_dealt = Column(Integer, nullable=True, default=0)
    damage_taken = Column(Integer, nullable=True, default=0)
    healing_done = Column(Integer, nullable=True, default=0)
    gold_earned = Column(Integer, nullable=True, default=0)
    experience_earned = Column(Integer, nullable=True, default=0)
    cc_time_inflicted = Column(Integer, nullable=True, default=0)
    
    # Relationships
    match = relationship("Match", back_populates="player_stats")


class TimelineEvent(Base):
    """Timeline event table for match timeline analysis."""
    __tablename__ = 'timeline_events'
    
    event_id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, ForeignKey('matches.match_id'), nullable=True)  # Allow null for initial creation
    event_time = Column(DateTime, nullable=False)
    timestamp = Column(DateTime, nullable=True)  # For compatibility
    event_type = Column(String, nullable=False)
    event_description = Column(Text, nullable=True)  # Added description field
    entity_name = Column(String, nullable=True)
    target_name = Column(String, nullable=True)
    location_x = Column(Float, nullable=True)
    location_y = Column(Float, nullable=True)
    event_details = Column(Text, nullable=True)  # JSON data
    
    # Relationships
    match = relationship("Match", back_populates="timeline_events")


def init_db(engine_url: str) -> None:
    """Initialize the database with the schema."""
    engine = create_engine(engine_url)
    Base.metadata.create_all(engine)


def get_db_engine(config: Dict[str, Any]) -> Any:
    """Create a SQLite database engine with the appropriate configuration."""
    db_path = config['db_path']
    engine = create_engine(f"sqlite:///{db_path}")
    
    # Set pragmas
    with engine.connect() as conn:
        conn.execute(f"PRAGMA journal_mode = {config['journal_mode']}")
        conn.execute(f"PRAGMA synchronous = {config['synchronous']}")
        conn.execute(f"PRAGMA foreign_keys = {'ON' if config['foreign_keys'] else 'OFF'}")
        conn.execute(f"PRAGMA temp_store = {config['temp_store']}")
    
    return engine 