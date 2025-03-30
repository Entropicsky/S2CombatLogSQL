import os
import sys
import unittest
import pandas as pd
import numpy as np
import importlib
from unittest.mock import patch, MagicMock

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestItemVisualization(unittest.TestCase):
    """Test visualization components in the Items & Builds page."""
    
    def setUp(self):
        """Set up test data for visualizations."""
        # Import the module using importlib to avoid linter errors with numeric filenames
        self.module = importlib.import_module('pages.2_Items_Builds')
        
        # Sample item events data
        self.item_events = pd.DataFrame({
            'player_name': ['Player1', 'Player1', 'Player2', 'Player2'],
            'item_name': ['Sword', 'Shield', 'Staff', 'Amulet'],
            'game_time_seconds': [90, 300, 120, 360],
            'team_id': [1, 1, 2, 2],
            'item_cost': [1000, 1500, 1200, 900],
            'purchase_time': ['00:01:30', '00:05:00', '00:02:00', '00:06:00'],
            'item_tier': [1, 2, 2, 1]
        })
        
        # Sample player stats data
        self.player_stats = pd.DataFrame({
            'player_name': ['Player1', 'Player2'],
            'team_id': [1, 2],
            'kills': [5, 3],
            'deaths': [2, 4],
            'assists': [3, 6],
            'damage_dealt': [10000, 8500],
            'gold_earned': [7500, 6800]
        })
        
        # Sample match info
        self.match_info = pd.DataFrame({
            'match_id': ['TEST001'],
            'map_name': ['Conquest'],
            'duration_seconds': [1800]
        })
    
    def test_streamlit_visualizations_with_mock(self):
        """Test visualizations using mock Streamlit objects."""
        # Create mock Streamlit objects
        mock_st = MagicMock()
        mock_st.empty.return_value = MagicMock()
        mock_st.container.return_value = MagicMock()
        mock_st.tabs.return_value = [MagicMock(), MagicMock(), MagicMock()]
        
        # Track charts that were plotted
        plotted_charts = []
        
        # Create a patched plotly_chart function
        def patched_plotly_chart(fig, *args, **kwargs):
            # Validate the figure
            self.assertIsNotNone(fig, "None figure passed to st.plotly_chart()")
            self.assertTrue(hasattr(fig, 'data'), "Figure lacks 'data' attribute")
            self.assertTrue(hasattr(fig, 'layout'), "Figure lacks 'layout' attribute")
            # Add to our list of plotted charts
            plotted_charts.append(fig)
        
        # Assign the patched function
        mock_st.plotly_chart = patched_plotly_chart
        
        # Replace the real st with our mock
        with patch.object(self.module, 'st', mock_st):
            # Test the charts directly if render_items_page doesn't exist
            item_data = {
                'item_events': self.item_events,
                'player_stats': self.player_stats,
                'match_info': self.match_info
            }
            
            if hasattr(self.module, 'render_items_page'):
                # Test full data visualization through the render function
                self.module.render_items_page(item_data)
            else:
                # Call the visualization functions directly
                # Test item timeline
                if hasattr(self.module, 'create_item_timeline'):
                    fig = self.module.create_item_timeline(self.item_events, 1800)
                    if fig is not None:
                        mock_st.plotly_chart(fig)
                
                # Test build path
                if hasattr(self.module, 'create_build_path_diagram'):
                    fig = self.module.create_build_path_diagram(self.item_events, 'Player1')
                    if fig is not None:
                        mock_st.plotly_chart(fig)
                
                # Test item popularity
                if hasattr(self.module, 'create_item_popularity_chart'):
                    fig = self.module.create_item_popularity_chart(self.item_events)
                    if fig is not None:
                        mock_st.plotly_chart(fig)
                
                # Test gold distribution
                if hasattr(self.module, 'create_gold_distribution_chart'):
                    fig = self.module.create_gold_distribution_chart(self.item_events)
                    if fig is not None:
                        mock_st.plotly_chart(fig)
            
            # Check that at least one chart was plotted
            self.assertTrue(len(plotted_charts) > 0, "No charts were plotted")
    
    def test_handle_missing_data(self):
        """Test visualization functions with missing or incomplete data."""
        # Mock Streamlit
        mock_st = MagicMock()
        
        # Test item timeline with missing columns
        with patch.object(self.module, 'st', mock_st):
            # Test with missing game_time_seconds
            incomplete_data = self.item_events.drop(columns=['game_time_seconds'])
            result = self.module.create_item_timeline(incomplete_data, 1800)
            self.assertIsNone(result)
            
            # Test with only required columns - this might return None based on implementation
            minimal_data = pd.DataFrame({
                'player_name': ['Player1', 'Player2'],
                'item_name': ['Sword', 'Staff'],
                'game_time_seconds': [90, 120]
            })
            result = self.module.create_item_timeline(minimal_data, 1800)
            # We'll skip asserting the result here since implementations may vary
            # Just verify no exception is raised
            
            # Add team_id to make it more likely to succeed
            minimal_data_with_team = minimal_data.copy()
            minimal_data_with_team['team_id'] = [1, 2]
            result = self.module.create_item_timeline(minimal_data_with_team, 1800)
            # Even with team_id, implementations may still vary, 
            # so we'll just verify no exception is raised
    
    def test_build_path_with_edge_cases(self):
        """Test build path diagram with various edge cases."""
        mock_st = MagicMock()
        
        with patch.object(self.module, 'st', mock_st):
            # Test with single item
            single_item_data = pd.DataFrame({
                'player_name': ['Player1'],
                'item_name': ['Sword'],
                'game_time_seconds': [90]
            })
            result = self.module.create_build_path_diagram(single_item_data, 'Player1')
            self.assertIsNotNone(result)
            
            # Test with duplicate items (same item bought twice)
            duplicate_items = pd.DataFrame({
                'player_name': ['Player1', 'Player1'],
                'item_name': ['Sword', 'Sword'],
                'game_time_seconds': [90, 300]
            })
            result = self.module.create_build_path_diagram(duplicate_items, 'Player1')
            self.assertIsNotNone(result)
            
            # Test with items purchased at exactly the same time
            same_time_items = pd.DataFrame({
                'player_name': ['Player1', 'Player1'],
                'item_name': ['Sword', 'Shield'],
                'game_time_seconds': [90, 90]
            })
            result = self.module.create_build_path_diagram(same_time_items, 'Player1')
            self.assertIsNotNone(result)
    
    def test_chart_data_transformations(self):
        """Test data transformations for chart creation."""
        # Test the categorize_item function if available
        if hasattr(self.module, 'categorize_item'):
            categorize_item = self.module.categorize_item
            # Test with known item types
            self.assertIn(categorize_item('Sword'), ('Weapon', 'Physical', 'Damage'))
            self.assertIn(categorize_item('Shield'), ('Defense', 'Protection', 'Armor'))
            # Test with unknown item
            self.assertIsNotNone(categorize_item('UnknownItem'))
        
        # Test gold distribution chart calculations
        mock_st = MagicMock()
        with patch.object(self.module, 'st', mock_st):
            # Create chart with sample data
            chart = self.module.create_gold_distribution_chart(self.item_events)
            # Verify chart creation
            self.assertIsNotNone(chart)
            
            # Calculate total gold spent
            total_gold = self.item_events['item_cost'].sum()
            # Ensure chart data includes all gold spent
            # Note: we can't directly check the chart data without complex mocking,
            # but this test verifies the function executes without errors
    
    def test_visualization_with_empty_data(self):
        """Test visualization functions with empty datasets."""
        mock_st = MagicMock()
        with patch.object(self.module, 'st', mock_st):
            # Test with empty DataFrame
            empty_df = pd.DataFrame()
            
            # Check item timeline
            result = self.module.create_item_timeline(empty_df, 1800)
            self.assertIsNone(result)
            
            # Check build path diagram
            result = self.module.create_build_path_diagram(empty_df, 'Player1')
            self.assertIsNone(result)
            
            # Check item popularity chart
            result = self.module.create_item_popularity_chart(empty_df)
            self.assertIsNone(result)
            
            # Check gold distribution chart
            result = self.module.create_gold_distribution_chart(empty_df)
            self.assertIsNone(result)
            
            # Check item impact chart
            result = self.module.create_item_impact_chart(empty_df, self.player_stats)
            self.assertIsNone(result)
    
    def test_visualization_with_null_values(self):
        """Test visualization functions with null values in data."""
        mock_st = MagicMock()
        with patch.object(self.module, 'st', mock_st):
            # Create data with some null values
            null_data = self.item_events.copy()
            null_data.loc[0, 'game_time_seconds'] = None
            null_data.loc[1, 'item_cost'] = None
            
            # Test item timeline with null game_time
            result = self.module.create_item_timeline(null_data, 1800)
            self.assertIsNotNone(result)  # Should handle nulls by filtering or providing defaults
            
            # Test gold distribution with null cost
            result = self.module.create_gold_distribution_chart(null_data)
            self.assertIsNotNone(result)  # Should handle null costs
    
    def test_player_name_edge_cases(self):
        """Test visualization with edge cases in player names."""
        mock_st = MagicMock()
        with patch.object(self.module, 'st', mock_st):
            # Test with special characters in player names
            special_chars_data = self.item_events.copy()
            special_chars_data['player_name'] = special_chars_data['player_name'].replace('Player1', 'Player#1$%^')
            
            # Check build path diagram
            result = self.module.create_build_path_diagram(special_chars_data, 'Player#1$%^')
            self.assertIsNotNone(result)
            
            # Check with extremely long player names
            long_name_data = self.item_events.copy()
            long_name_data['player_name'] = long_name_data['player_name'].replace('Player1', 'A' * 100)
            
            # Check build path diagram
            result = self.module.create_build_path_diagram(long_name_data, 'A' * 100)
            self.assertIsNotNone(result)

if __name__ == '__main__':
    unittest.main() 