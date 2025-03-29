"""Configuration for pytest."""
import os
import tempfile
import pytest
import json
from datetime import datetime
from pathlib import Path


@pytest.fixture
def test_data_dir():
    """Create a temporary directory for test data."""
    temp_dir = tempfile.TemporaryDirectory()
    yield Path(temp_dir.name)
    temp_dir.cleanup()


@pytest.fixture
def sample_event_json():
    """Sample event JSON data."""
    return {
        "eventType": "CombatMsg",
        "type": "Damage",
        "time": "2025.03.19-03.38.15",
        "sourceowner": "Player1",
        "targetowner": "Player2",
        "value1": "100",
        "value2": "50",
        "locationx": "123.45",
        "locationy": "67.89",
        "itemid": "42",
        "itemname": "Sword",
        "text": "Player1 hit Player2 for 100 damage (50 mitigated)."
    }


@pytest.fixture
def sample_log_file():
    """Create a sample combat log file for testing."""
    # Create a temporary file
    fd, path = tempfile.mkstemp(suffix='.combatlog')
    
    # Sample log entries
    log_entries = [
        {
            "timestamp": datetime.now().isoformat(),
            "eventType": "start",
            "matchId": "test-match-id",
            "maps": "Conquest",
            "gametype": "Conquest"
        },
        {
            "timestamp": datetime.now().isoformat(),
            "eventType": "playermsg",
            "player": "Player1",
            "team": 1,
            "god": "Loki",
            "role": "Jungle",
            "level": 1
        },
        {
            "timestamp": datetime.now().isoformat(),
            "eventType": "CombatMsg",
            "source": "Player1",
            "target": "Player2",
            "type": "Damage",
            "value": 100,
            "ability": "Basic Attack"
        },
        {
            "timestamp": datetime.now().isoformat(),
            "eventType": "RewardMsg",
            "entity": "Player1",
            "type": "Currency",
            "value": 100,
            "source": "Minion"
        },
        {
            "timestamp": datetime.now().isoformat(),
            "eventType": "itemmsg",
            "player": "Player1",
            "item": "Sword",
            "slot": 1,
            "value": 500
        }
    ]
    
    # Write the log entries to the file
    with os.fdopen(fd, 'w') as f:
        for entry in log_entries:
            f.write(json.dumps(entry) + "\n")
    
    yield path
    
    # Clean up
    os.unlink(path)


@pytest.fixture
def sample_match_data():
    """Sample match data for testing."""
    return {
        "match_id": "test-match-id",
        "source_file": "test_log",
        "start_time": datetime(2025, 3, 19, 3, 38, 15),
        "end_time": datetime(2025, 3, 19, 4, 9, 57),
        "duration_seconds": 1902,
        "player_names": {"Player1", "Player2"},
    } 