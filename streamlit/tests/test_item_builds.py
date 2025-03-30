import os
import sys
import unittest
import pandas as pd
import sqlite3
import tempfile
import networkx as nx
import importlib

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the functions to test - use importlib to avoid linter errors with numeric module name
items_builds_module = importlib.import_module('pages.2_Items_Builds')
load_item_data = items_builds_module.load_item_data
format_time = items_builds_module.format_time
get_team_color = items_builds_module.get_team_color
create_item_timeline = items_builds_module.create_item_timeline
create_build_path_diagram = items_builds_module.create_build_path_diagram
create_item_popularity_chart = items_builds_module.create_item_popularity_chart
create_gold_distribution_chart = items_builds_module.create_gold_distribution_chart
create_item_impact_chart = items_builds_module.create_item_impact_chart

class TestItemBuildsPage(unittest.TestCase):
    """Test suite for the Items & Builds page functions."""
    
    def setUp(self):
        """Set up a test database with sample data."""
        # Create a temporary SQLite database
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
        # Create test tables and insert sample data
        self._create_test_database()
        
    def tearDown(self):
        """Clean up the test database."""
        self.conn.close()
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def _create_test_database(self):
        """Create test tables and insert sample data."""
        # Create matches table
        self.cursor.execute('''
        CREATE TABLE matches (
            match_id TEXT PRIMARY KEY,
            source_file TEXT,
            map_name TEXT,
            duration_seconds INTEGER
        )
        ''')
        
        # Create players table
        self.cursor.execute('''
        CREATE TABLE players (
            player_id INTEGER PRIMARY KEY,
            match_id TEXT,
            player_name TEXT,
            team_id INTEGER,
            role TEXT,
            god_name TEXT
        )
        ''')
        
        # Create item_events table
        self.cursor.execute('''
        CREATE TABLE item_events (
            item_id INTEGER PRIMARY KEY,
            match_id TEXT,
            player_name TEXT,
            item_name TEXT,
            item_cost INTEGER,
            purchase_time TEXT,
            game_time_seconds INTEGER,
            item_slot INTEGER,
            item_tier INTEGER
        )
        ''')
        
        # Create player_stats table
        self.cursor.execute('''
        CREATE TABLE player_stats (
            stat_id INTEGER PRIMARY KEY,
            match_id TEXT,
            player_name TEXT,
            kills INTEGER,
            deaths INTEGER,
            assists INTEGER,
            damage_dealt INTEGER,
            gold_earned INTEGER
        )
        ''')
        
        # Insert test data into matches
        self.cursor.execute('''
        INSERT INTO matches (match_id, source_file, map_name, duration_seconds)
        VALUES ('TEST001', 'test.log', 'Conquest', 1800)
        ''')
        
        # Insert test players (2 teams, 2 players each)
        self.cursor.execute('''
        INSERT INTO players (player_id, match_id, player_name, team_id, role, god_name)
        VALUES 
            (1, 'TEST001', 'Player1', 1, 'Solo', 'Zeus'),
            (2, 'TEST001', 'Player2', 1, 'Mid', 'Poseidon'),
            (3, 'TEST001', 'Player3', 2, 'Solo', 'Odin'),
            (4, 'TEST001', 'Player4', 2, 'Mid', 'Ra')
        ''')
        
        # Insert test item purchases
        self.cursor.execute('''
        INSERT INTO item_events (item_id, match_id, player_name, item_name, item_cost, purchase_time, game_time_seconds, item_slot, item_tier)
        VALUES 
            (1, 'TEST001', 'Player1', 'Sword', 1000, '00:01:30', 90, 1, 1),
            (2, 'TEST001', 'Player1', 'Shield', 1500, '00:05:00', 300, 2, 2),
            (3, 'TEST001', 'Player1', 'Boots', 800, '00:07:30', 450, 3, 1),
            (4, 'TEST001', 'Player2', 'Staff', 1200, '00:02:00', 120, 1, 2),
            (5, 'TEST001', 'Player2', 'Amulet', 900, '00:06:00', 360, 2, 1),
            (6, 'TEST001', 'Player3', 'Axe', 1100, '00:01:45', 105, 1, 1),
            (7, 'TEST001', 'Player3', 'Armor', 1700, '00:04:30', 270, 2, 2),
            (8, 'TEST001', 'Player4', 'Rod', 1300, '00:02:30', 150, 1, 2),
            (9, 'TEST001', 'Player4', 'Ring', 950, '00:05:30', 330, 2, 1)
        ''')
        
        # Insert test player stats
        self.cursor.execute('''
        INSERT INTO player_stats (stat_id, match_id, player_name, kills, deaths, assists, damage_dealt, gold_earned)
        VALUES 
            (1, 'TEST001', 'Player1', 5, 3, 2, 10000, 7500),
            (2, 'TEST001', 'Player2', 3, 4, 7, 8500, 6800),
            (3, 'TEST001', 'Player3', 4, 2, 4, 9000, 7200),
            (4, 'TEST001', 'Player4', 2, 5, 8, 7500, 6500)
        ''')
        
        self.conn.commit()

    def test_format_time(self):
        """Test the format_time function."""
        self.assertEqual(format_time(90), "01:30")
        self.assertEqual(format_time(3661), "61:01")
        self.assertEqual(format_time(None), "00:00")
        self.assertEqual(format_time("invalid"), "00:00")
        
    def test_get_team_color(self):
        """Test the get_team_color function."""
        self.assertEqual(get_team_color(1), "rgba(255, 0, 0, 0.7)")  # Chaos
        self.assertEqual(get_team_color(2), "rgba(0, 0, 255, 0.7)")  # Order
        self.assertEqual(get_team_color(None), "rgba(120, 120, 120, 0.7)")  # Unknown
    
    def test_load_item_data(self):
        """Test loading item data from the database."""
        # Mock Streamlit's st.error/warning functions for testing
        class MockSt:
            def __init__(self):
                self.errors = []
                self.warnings = []
            
            def error(self, msg):
                self.errors.append(msg)
            
            def warning(self, msg):
                self.warnings.append(msg)
        
        # Replace the actual st module with our mock
        module = importlib.import_module('pages.2_Items_Builds')
        original_st = module.st
        module.st = MockSt()
        
        try:
            # Test with valid path
            data = load_item_data(self.db_path)
            
            # Check if we got the expected data
            self.assertIsNotNone(data)
            self.assertIn("match_info", data)
            self.assertIn("players_data", data)
            self.assertIn("item_events", data)
            self.assertIn("player_stats", data)
            
            # Check if match_info has the right data
            self.assertEqual(data["match_info"]["match_id"].iloc[0], "TEST001")
            self.assertEqual(data["match_info"]["duration_seconds"].iloc[0], 1800)
            
            # Check if players_data has the right number of players
            self.assertEqual(len(data["players_data"]), 4)
            
            # Check if item_events has the right number of items
            self.assertEqual(len(data["item_events"]), 9)
            
            # Test with invalid path
            invalid_data = load_item_data("nonexistent.db")
            self.assertIsNone(invalid_data)
            self.assertEqual(len(module.st.errors), 1)  # Should have one error message
        
        finally:
            # Restore the original st module
            module.st = original_st
    
    def test_create_item_timeline(self):
        """Test creating the item purchase timeline chart."""
        # Create sample item events data
        item_events = pd.DataFrame({
            'player_name': ['Player1', 'Player1', 'Player2', 'Player2'],
            'item_name': ['Sword', 'Shield', 'Staff', 'Amulet'],
            'game_time_seconds': [90, 300, 120, 360],
            'team_id': [1, 1, 1, 1],
            'item_cost': [1000, 1500, 1200, 900]
        })
        
        # Mock Streamlit's st.warning function
        class MockSt:
            def __init__(self):
                self.warnings = []
            
            def warning(self, msg):
                self.warnings.append(msg)
        
        # Replace the actual st module
        module = importlib.import_module('pages.2_Items_Builds')
        original_st = module.st
        module.st = MockSt()
        
        try:
            # Test with valid data
            fig = create_item_timeline(item_events, 1800)
            self.assertIsNotNone(fig)
            
            # Test with empty data
            empty_fig = create_item_timeline(pd.DataFrame(), 1800)
            self.assertIsNone(empty_fig)
            
            # Test with missing columns
            incomplete_data = pd.DataFrame({
                'player_name': ['Player1'],
                'item_name': ['Sword']
            })
            incomplete_fig = create_item_timeline(incomplete_data, 1800)
            self.assertIsNone(incomplete_fig)
            self.assertEqual(len(module.st.warnings), 1)  # Should have one warning
        
        finally:
            # Restore the original st module
            module.st = original_st
    
    def test_create_build_path_diagram(self):
        """Test creating the build path diagram."""
        # Create sample item events data
        item_events = pd.DataFrame({
            'player_name': ['Player1', 'Player1', 'Player2', 'Player2'],
            'item_name': ['Sword', 'Shield', 'Staff', 'Amulet'],
            'game_time_seconds': [90, 300, 120, 360],
            'team_id': [1, 1, 1, 1],
            'item_cost': [1000, 1500, 1200, 900]
        })
        
        # Test with valid player name
        fig = create_build_path_diagram(item_events, 'Player1')
        self.assertIsNotNone(fig)
        
        # Test with non-existent player
        fig2 = create_build_path_diagram(item_events, 'NonExistent')
        self.assertIsNone(fig2)
        
        # Test with no player specified
        fig3 = create_build_path_diagram(item_events)
        self.assertIsNone(fig3)
        
        # Test with empty dataframe
        fig4 = create_build_path_diagram(pd.DataFrame(), 'Player1')
        self.assertIsNone(fig4)
    
    def test_create_item_popularity_chart(self):
        """Test creating the item popularity chart."""
        # Create sample item events data
        item_events = pd.DataFrame({
            'item_name': ['Sword', 'Shield', 'Sword', 'Staff', 'Amulet', 'Staff'],
            'player_name': ['Player1', 'Player1', 'Player2', 'Player2', 'Player3', 'Player3']
        })
        
        # Test with valid data
        fig = create_item_popularity_chart(item_events)
        self.assertIsNotNone(fig)
        
        # Test with empty dataframe
        fig2 = create_item_popularity_chart(pd.DataFrame())
        self.assertIsNone(fig2)
    
    def test_create_gold_distribution_chart(self):
        """Test creating the gold distribution chart."""
        # Create sample item events data
        item_events = pd.DataFrame({
            'player_name': ['Player1', 'Player1', 'Player2', 'Player2'],
            'item_name': ['Sword', 'Shield', 'Staff', 'Amulet'],
            'item_cost': [1000, 1500, 1200, 900]
        })
        
        # Mock the categorize_item function to always return a fixed category for testing
        def mock_categorize_item(item_name):
            if 'Sword' in item_name or 'Axe' in item_name:
                return 'Weapon'
            elif 'Shield' in item_name or 'Armor' in item_name:
                return 'Armor'
            else:
                return 'Other'
        
        # Replace the categorize_item function
        module = importlib.import_module('pages.2_Items_Builds')
        if hasattr(module, 'categorize_item'):
            original_categorize = module.categorize_item
            module.categorize_item = mock_categorize_item
        else:
            # Try to get and replace the function from the create_gold_distribution_chart's globals
            original_categorize = module.create_gold_distribution_chart.__globals__.get('categorize_item')
            if original_categorize:
                module.create_gold_distribution_chart.__globals__['categorize_item'] = mock_categorize_item
        
        try:
            # Test with valid data (all players)
            fig = create_gold_distribution_chart(item_events)
            self.assertIsNotNone(fig)
            
            # Test with valid data (single player)
            fig2 = create_gold_distribution_chart(item_events, 'Player1')
            self.assertIsNotNone(fig2)
            
            # Test with non-existent player
            fig3 = create_gold_distribution_chart(item_events, 'NonExistent')
            self.assertIsNone(fig3)
            
            # Test with no cost data
            no_cost_data = pd.DataFrame({
                'player_name': ['Player1', 'Player2'],
                'item_name': ['Sword', 'Staff']
            })
            fig4 = create_gold_distribution_chart(no_cost_data)
            self.assertIsNone(fig4)
            
            # Test with empty dataframe
            fig5 = create_gold_distribution_chart(pd.DataFrame())
            self.assertIsNone(fig5)
        
        finally:
            # Restore the original function
            if hasattr(module, 'categorize_item') and original_categorize:
                module.categorize_item = original_categorize
            elif original_categorize:
                module.create_gold_distribution_chart.__globals__['categorize_item'] = original_categorize
    
    def test_create_item_impact_chart(self):
        """Test creating the item impact chart."""
        # Create sample item events and player stats data
        item_events = pd.DataFrame({
            'item_name': ['Sword', 'Shield', 'Staff', 'Amulet'],
            'item_cost': [1000, 1500, 1200, 900]
        })
        
        player_stats = pd.DataFrame({
            'player_name': ['Player1', 'Player2'],
            'kills': [5, 3],
            'damage_dealt': [10000, 8500]
        })
        
        # Mock Streamlit's st.info function
        class MockSt:
            def __init__(self):
                self.info_msgs = []
            
            def info(self, msg):
                self.info_msgs.append(msg)
        
        # Replace the actual st module
        module = importlib.import_module('pages.2_Items_Builds')
        original_st = module.st
        module.st = MockSt()
        
        try:
            # Test with valid data
            fig = create_item_impact_chart(item_events, player_stats)
            self.assertIsNotNone(fig)
            self.assertEqual(len(module.st.info_msgs), 1)  # Should have one info message
            
            # Test with empty data
            fig2 = create_item_impact_chart(pd.DataFrame(), player_stats)
            self.assertIsNone(fig2)
            
            fig3 = create_item_impact_chart(item_events, pd.DataFrame())
            self.assertIsNone(fig3)
        
        finally:
            # Restore the original st module
            module.st = original_st

if __name__ == '__main__':
    unittest.main() 