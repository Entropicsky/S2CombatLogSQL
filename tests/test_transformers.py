"""Tests for the transformers module."""
import unittest
from datetime import datetime
from smite_parser.transformers import (
    parse_timestamp, convert_numeric, convert_float, normalize_role_name,
    extract_team_id, transform_event, categorize_entity,
    transform_combat_event, transform_reward_event,
    transform_item_event, transform_player_event
)


class TestTransformers(unittest.TestCase):
    """Test the transformer functions."""
    
    def test_parse_timestamp(self):
        """Test timestamp parsing."""
        # Valid timestamp
        assert parse_timestamp("2025.03.19-03.38.15") == datetime(2025, 3, 19, 3, 38, 15)
        
        # Invalid timestamp
        assert parse_timestamp("invalid") is None
    
    def test_convert_numeric(self):
        """Test numeric conversion."""
        # Valid numbers
        assert convert_numeric("123") == 123
        assert convert_numeric("0") == 0
        assert convert_numeric("-45") == -45
        
        # Invalid numbers
        assert convert_numeric("abc") is None
        assert convert_numeric("") is None
        assert convert_numeric(None) is None
    
    def test_convert_float(self):
        """Test float conversion."""
        # Valid floats
        assert convert_float("123.45") == 123.45
        assert convert_float("0.0") == 0.0
        assert convert_float("-45.67") == -45.67
        
        # Integer input should work too
        assert convert_float("123") == 123.0
        
        # Invalid floats
        assert convert_float("abc") is None
        assert convert_float("") is None
        assert convert_float(None) is None
    
    def test_normalize_role_name(self):
        """Test role name normalization."""
        # Valid role names
        assert normalize_role_name("EJungle") == "Jungle"
        assert normalize_role_name("ESolo") == "Solo"
        assert normalize_role_name("EMiddle") == "Middle"
        
        # Non-matching role names should be returned as-is
        assert normalize_role_name("Jungle") == "Jungle"
        assert normalize_role_name("") == ""
    
    def test_extract_team_id(self):
        """Test team ID extraction."""
        # Valid team IDs
        assert extract_team_id("1") == 1
        assert extract_team_id("2") == 2
        
        # Invalid team IDs
        assert extract_team_id("0") is None
        assert extract_team_id("3") is None
        assert extract_team_id("abc") is None
        assert extract_team_id("") is None
        assert extract_team_id(None) is None
    
    def test_transform_event(self):
        """Test event transformation."""
        # Basic event
        event = {
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
        
        match_id = "test-match-id"
        transformed = transform_event(event, match_id)
        
        # Check that the transformed event has the correct fields
        assert transformed["match_id"] == match_id
        assert transformed["event_type"] == "CombatMsg"
        assert transformed["type"] == "Damage"
        assert transformed["event_time"] == datetime(2025, 3, 19, 3, 38, 15)
        assert transformed["sourceowner"] == "Player1"
        assert transformed["targetowner"] == "Player2"
        assert transformed["value1"] == 100
        assert transformed["value2"] == 50
        assert transformed["location_x"] == 123.45
        assert transformed["location_y"] == 67.89
        assert transformed["itemid"] == "42"
        assert transformed["itemname"] == "Sword"
        assert transformed["text"] == "Player1 hit Player2 for 100 damage (50 mitigated)."
        
        # Test with missing fields
        minimal_event = {"eventType": "start", "matchID": "12345"}
        transformed = transform_event(minimal_event, match_id)
        assert transformed["match_id"] == match_id
        assert transformed["event_type"] == "start"
        assert "event_time" not in transformed
        
    def test_categorize_entity(self):
        """Test entity categorization."""
        player_names = {"Player1", "Player2", "Player3"}
        
        # Players
        assert categorize_entity("Player1", player_names) == "player"
        assert categorize_entity("Player2", player_names) == "player"
        
        # Minions
        assert categorize_entity("Fire Archer", player_names) == "minion"
        assert categorize_entity("Fire Brute", player_names) == "minion"
        assert categorize_entity("Swordsman", player_names) == "minion"
        assert categorize_entity("Champion Archer", player_names) == "minion"
        
        # Jungle camps
        assert categorize_entity("Alpha Harpy", player_names) == "jungle"
        assert categorize_entity("Pyromancer", player_names) == "jungle"
        assert categorize_entity("Gold Fury", player_names) == "jungle"
        assert categorize_entity("Elder Satyr", player_names) == "jungle"
        
        # Objectives
        assert categorize_entity("Order Tower", player_names) == "objective"
        assert categorize_entity("Chaos Phoenix", player_names) == "objective"
        assert categorize_entity("Order Titan", player_names) == "objective"
        
        # Unknown
        assert categorize_entity("Unknown Entity", player_names) == "unknown"
        assert categorize_entity("", player_names) == "unknown"
    
    def test_transform_combat_event(self):
        """Test that combat event transformation populates all required fields."""
        # Create a sample combat event
        event = {
            "eventType": "CombatMsg",
            "time": "2025.03.19-04.09.28",
            "type": "Damage",
            "sourceowner": "Player1",
            "targetowner": "Monster1",
            "itemname": "Ability1",
            "value1": "100",
            "value2": "25",
            "locationx": "123",
            "locationy": "456",
            "text": "Player1 hit Monster1 for 100 damage"
        }
        
        # Transform the event
        db_event = transform_combat_event(event)
        
        # Check that all required fields are populated
        self.assertIsNotNone(db_event)
        self.assertIsInstance(db_event.timestamp, datetime)
        self.assertIsInstance(db_event.event_time, datetime)
        self.assertEqual(db_event.event_type, "Damage")
        self.assertEqual(db_event.source_entity, "Player1")
        self.assertEqual(db_event.target_entity, "Monster1")
        self.assertEqual(db_event.ability_name, "Ability1")
        self.assertEqual(db_event.damage_amount, 100)
        self.assertEqual(db_event.damage_mitigated, 25)
        self.assertEqual(db_event.location_x, 123)
        self.assertEqual(db_event.location_y, 456)
        self.assertEqual(db_event.event_text, "Player1 hit Monster1 for 100 damage")
    
    def test_transform_reward_event(self):
        """Test that reward event transformation populates all required fields."""
        # Create a sample reward event
        event = {
            "eventType": "RewardMsg",
            "time": "2025.03.19-04.09.28",
            "type": "Currency",
            "sourceowner": "Player1",
            "value1": "500",
            "itemname": "KillReward",
            "locationx": "123",
            "locationy": "456",
            "text": "Player1 earned 500 gold"
        }
        
        # Transform the event
        db_event = transform_reward_event(event)
        
        # Check that all required fields are populated
        self.assertIsNotNone(db_event)
        self.assertIsInstance(db_event.timestamp, datetime)
        self.assertIsInstance(db_event.event_time, datetime)
        self.assertEqual(db_event.event_type, "Currency")
        self.assertEqual(db_event.entity_name, "Player1")
        self.assertEqual(db_event.reward_amount, 500)
        self.assertEqual(db_event.source_type, "KillReward")
        self.assertEqual(db_event.location_x, 123)
        self.assertEqual(db_event.location_y, 456)
        self.assertEqual(db_event.event_text, "Player1 earned 500 gold")
    
    def test_transform_item_event(self):
        """Test that item event transformation populates all required fields."""
        # Create a sample item event
        event = {
            "eventType": "itemmsg",
            "time": "2025.03.19-04.09.28",
            "type": "ItemPurchase",
            "sourceowner": "Player1",
            "itemid": "1234",
            "itemname": "Sword",
            "value1": "300",
            "locationx": "123",
            "locationy": "456",
            "text": "Player1 purchased Sword"
        }
        
        # Transform the event
        db_event = transform_item_event(event)
        
        # Check that all required fields are populated
        self.assertIsNotNone(db_event)
        self.assertIsInstance(db_event.timestamp, datetime)
        self.assertIsInstance(db_event.event_time, datetime)
        self.assertEqual(db_event.event_type, "ItemPurchase")
        self.assertEqual(db_event.player_name, "Player1")
        self.assertEqual(db_event.item_id, "1234")
        self.assertEqual(db_event.item_name, "Sword")
        self.assertEqual(db_event.cost, 300)
        self.assertEqual(db_event.location_x, 123)
        self.assertEqual(db_event.location_y, 456)
        self.assertEqual(db_event.event_text, "Player1 purchased Sword")
    
    def test_transform_player_event(self):
        """Test that player event transformation populates all required fields."""
        # Create a sample player event
        event = {
            "eventType": "playermsg",
            "time": "2025.03.19-04.09.28",
            "type": "RoleAssigned",
            "sourceowner": "Player1",
            "targetowner": "Team1",
            "value1": "1",
            "itemname": "EJungle",
            "locationx": "123",
            "locationy": "456",
            "text": "Player1 assigned to Jungle role"
        }
        
        # Transform the event
        db_event = transform_player_event(event)
        
        # Check that all required fields are populated
        self.assertIsNotNone(db_event)
        self.assertIsInstance(db_event.timestamp, datetime)
        self.assertIsInstance(db_event.event_time, datetime)
        self.assertEqual(db_event.event_type, "RoleAssigned")
        self.assertEqual(db_event.player_name, "Player1")
        self.assertEqual(db_event.entity_name, "Team1")
        self.assertEqual(db_event.value, "1")
        self.assertEqual(db_event.item_name, "EJungle")
        self.assertEqual(db_event.location_x, 123)
        self.assertEqual(db_event.location_y, 456)
        self.assertEqual(db_event.event_text, "Player1 assigned to Jungle role")


if __name__ == "__main__":
    unittest.main() 