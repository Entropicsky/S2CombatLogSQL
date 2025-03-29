"""Tests for the parser module."""
import pytest
import os
import tempfile
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from smite_parser.config.config import ParserConfig
from smite_parser.parser import CombatLogParser
from smite_parser.models import (
    Match, Player, Entity, CombatEvent, RewardEvent,
    ItemEvent, PlayerEvent, PlayerStat, TimelineEvent, Base
)


class TestParser:
    """Tests for the parser module."""
    
    @pytest.fixture
    def parser_config(self):
        """Create a parser configuration for testing."""
        # Create a temporary database file
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        # Create configuration
        config = ParserConfig(
            db_path=db_path,
            batch_size=10,
            show_progress=False,
            skip_malformed=True,
        )
        
        yield config
        
        # Clean up
        os.unlink(db_path)
    
    @pytest.fixture
    def parser(self, parser_config):
        """Create a parser for testing."""
        parser = CombatLogParser(parser_config)
        
        # Create engine and tables
        engine = create_engine(f"sqlite:///{parser_config.db_path}")
        Base.metadata.create_all(engine)
        
        return parser
    
    def test_parse_file(self, parser, sample_log_file):
        """Test parsing a log file."""
        # Parse the file
        success = parser.parse_file(sample_log_file)
        
        # Check that parsing was successful
        assert success
        
        # Check that the database was created
        assert os.path.exists(parser.config.db_path)
        
        # Connect to the database and check the data
        engine = create_engine(f"sqlite:///{parser.config.db_path}")
        Session = sessionmaker(bind=engine)
        session = Session()
        
        try:
            # Check matches table
            matches = session.query(Match).all()
            assert len(matches) == 1
            match = matches[0]
            assert match.match_id == "test-match-id"
            assert match.source_file == "test_log"
            
            # Check players table
            players = session.query(Player).all()
            assert len(players) == 1
            player = players[0]
            assert player.player_name == "Player1"
            assert player.team_id == 1
            assert player.role == "Jungle"
            
            # Check entities table
            entities = session.query(Entity).all()
            assert len(entities) >= 2  # At least Player1 and Player2
            
            # Check combat events
            combat_events = session.query(CombatEvent).all()
            assert len(combat_events) == 1
            combat_event = combat_events[0]
            assert combat_event.source_entity == "Player1"
            assert combat_event.target_entity == "Player2"
            assert combat_event.event_type == "Damage"
            assert combat_event.value_amount == 100
            
            # Check reward events
            reward_events = session.query(RewardEvent).all()
            assert len(reward_events) == 1
            reward_event = reward_events[0]
            assert reward_event.entity_name == "Player1"
            assert reward_event.event_type == "Currency"
            assert reward_event.value_amount == 100
            
            # Check item events
            item_events = session.query(ItemEvent).all()
            assert len(item_events) == 1
            item_event = item_events[0]
            assert item_event.player_name == "Player1"
            assert item_event.item_name == "Sword"
            assert item_event.value == 500
            
            # Check player events
            player_events = session.query(PlayerEvent).all()
            assert len(player_events) == 1
            player_event = player_events[0]
            assert player_event.player_name == "Player1"
            assert player_event.event_type == "RoleAssigned"
            
            # Check player stats
            player_stats = session.query(PlayerStat).all()
            assert len(player_stats) >= 1
            
            # Check timeline events
            timeline_events = session.query(TimelineEvent).all()
            assert len(timeline_events) >= 1
            
        finally:
            session.close()
    
    def test_read_log_file(self, parser, sample_log_file):
        """Test reading a log file."""
        # Read the file
        events = parser._read_log_file(sample_log_file)
        
        # Check that events were parsed
        assert len(events) == 5
        
        # Check specific event types
        event_types = [event.get('eventType') for event in events]
        assert event_types == ['start', 'playermsg', 'CombatMsg', 'RewardMsg', 'itemmsg']
    
    def test_collect_metadata(self, parser, sample_log_file):
        """Test collecting metadata from events."""
        # Read the file
        events = parser._read_log_file(sample_log_file)
        
        # Collect metadata
        parser._collect_metadata(events)
        
        # Check player names
        assert 'Player1' in parser.player_names
        
        # Check timestamps
        assert parser.start_time is not None
        assert parser.end_time is not None 