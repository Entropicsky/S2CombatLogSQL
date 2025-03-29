"""Tests for the database models."""
import pytest
import os
import tempfile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from smite_parser.models import (
    Base, Match, Player, Entity, Item, Ability, CombatEvent,
    RewardEvent, ItemEvent, PlayerEvent, PlayerStat, TimelineEvent,
    init_db, get_db_engine
)


class TestModels:
    """Tests for the database models."""
    
    @pytest.fixture
    def db_engine(self):
        """Create a temporary SQLite database for testing."""
        # Create a temporary database file
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        # Create engine with test database
        engine_url = f"sqlite:///{db_path}"
        engine = create_engine(engine_url)
        
        # Create all tables
        Base.metadata.create_all(engine)
        
        yield engine
        
        # Clean up
        os.unlink(db_path)
    
    @pytest.fixture
    def db_session(self, db_engine):
        """Create a database session for testing."""
        Session = sessionmaker(bind=db_engine)
        session = Session()
        
        yield session
        
        # Clean up
        session.close()
    
    def test_init_db(self):
        """Test database initialization."""
        # Create a temporary database file
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        try:
            # Initialize the database
            engine_url = f"sqlite:///{db_path}"
            init_db(engine_url)
            
            # Check that the tables were created
            engine = create_engine(engine_url)
            assert engine.dialect.has_table(engine, "matches")
            assert engine.dialect.has_table(engine, "players")
            assert engine.dialect.has_table(engine, "entities")
            assert engine.dialect.has_table(engine, "items")
            assert engine.dialect.has_table(engine, "abilities")
            assert engine.dialect.has_table(engine, "combat_events")
            assert engine.dialect.has_table(engine, "reward_events")
            assert engine.dialect.has_table(engine, "item_events")
            assert engine.dialect.has_table(engine, "player_events")
            assert engine.dialect.has_table(engine, "player_stats")
            assert engine.dialect.has_table(engine, "timeline_events")
        finally:
            # Clean up
            os.unlink(db_path)
    
    def test_get_db_engine(self):
        """Test database engine creation with configuration."""
        # Create a temporary database file
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        try:
            # Create engine with configuration
            config = {
                'db_path': db_path,
                'journal_mode': 'WAL',
                'synchronous': 'NORMAL',
                'foreign_keys': True,
                'temp_store': 'MEMORY'
            }
            engine = get_db_engine(config)
            
            # Check that the engine was created
            assert engine is not None
            
            # Check that the database file was created
            assert os.path.exists(db_path)
        finally:
            # Clean up
            os.unlink(db_path)
    
    def test_match_model(self, db_session):
        """Test the Match model."""
        # Create a match
        match = Match(
            match_id="test-match-1",
            source_file="test_log",
            start_time=datetime(2025, 3, 19, 3, 38, 15),
            end_time=datetime(2025, 3, 19, 4, 9, 57),
            duration_seconds=1902,
            match_data='{"player_count": 10}'
        )
        db_session.add(match)
        db_session.commit()
        
        # Query the match
        queried_match = db_session.query(Match).filter_by(match_id="test-match-1").first()
        
        # Check that the match was inserted correctly
        assert queried_match is not None
        assert queried_match.match_id == "test-match-1"
        assert queried_match.source_file == "test_log"
        assert queried_match.start_time == datetime(2025, 3, 19, 3, 38, 15)
        assert queried_match.end_time == datetime(2025, 3, 19, 4, 9, 57)
        assert queried_match.duration_seconds == 1902
        assert queried_match.match_data == '{"player_count": 10}'
    
    def test_player_model(self, db_session):
        """Test the Player model."""
        # Create a match
        match = Match(
            match_id="test-match-2",
            source_file="test_log",
            start_time=datetime(2025, 3, 19, 3, 38, 15),
            end_time=datetime(2025, 3, 19, 4, 9, 57),
            duration_seconds=1902,
            match_data='{"player_count": 10}'
        )
        db_session.add(match)
        
        # Create a player
        player = Player(
            match_id="test-match-2",
            player_name="TestPlayer",
            team_id=1,
            role="Jungle",
            god_id=42,
            god_name="Thor"
        )
        db_session.add(player)
        db_session.commit()
        
        # Query the player
        queried_player = db_session.query(Player).filter_by(
            match_id="test-match-2",
            player_name="TestPlayer"
        ).first()
        
        # Check that the player was inserted correctly
        assert queried_player is not None
        assert queried_player.match_id == "test-match-2"
        assert queried_player.player_name == "TestPlayer"
        assert queried_player.team_id == 1
        assert queried_player.role == "Jungle"
        assert queried_player.god_id == 42
        assert queried_player.god_name == "Thor"
        
        # Check relationship with match
        assert queried_player.match is not None
        assert queried_player.match.match_id == "test-match-2"
    
    def test_combat_event_model(self, db_session):
        """Test the CombatEvent model."""
        # Create a match
        match = Match(
            match_id="test-match-3",
            source_file="test_log",
            start_time=datetime(2025, 3, 19, 3, 38, 15),
            end_time=datetime(2025, 3, 19, 4, 9, 57),
            duration_seconds=1902,
            match_data='{"player_count": 10}'
        )
        db_session.add(match)
        
        # Create a combat event
        event = CombatEvent(
            match_id="test-match-3",
            event_time=datetime(2025, 3, 19, 3, 45, 30),
            event_type="Damage",
            source_entity="Player1",
            target_entity="Player2",
            ability_name="Sword",
            location_x=123.45,
            location_y=67.89,
            damage_amount=100,
            damage_mitigated=50,
            event_text="Player1 hit Player2 for 100 damage (50 mitigated)."
        )
        db_session.add(event)
        db_session.commit()
        
        # Query the event
        queried_event = db_session.query(CombatEvent).filter_by(
            match_id="test-match-3",
            source_entity="Player1",
            target_entity="Player2"
        ).first()
        
        # Check that the event was inserted correctly
        assert queried_event is not None
        assert queried_event.match_id == "test-match-3"
        assert queried_event.event_time == datetime(2025, 3, 19, 3, 45, 30)
        assert queried_event.event_type == "Damage"
        assert queried_event.source_entity == "Player1"
        assert queried_event.target_entity == "Player2"
        assert queried_event.ability_name == "Sword"
        assert queried_event.location_x == 123.45
        assert queried_event.location_y == 67.89
        assert queried_event.damage_amount == 100
        assert queried_event.damage_mitigated == 50
        assert queried_event.event_text == "Player1 hit Player2 for 100 damage (50 mitigated)."
        
        # Check relationship with match
        assert queried_event.match is not None
        assert queried_event.match.match_id == "test-match-3" 