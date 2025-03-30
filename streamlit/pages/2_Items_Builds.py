import os
import sys
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
import networkx as nx
from pathlib import Path

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Try to import the ensure_database_schema function from Home
try:
    from streamlit.Home import ensure_database_schema
except ImportError:
    # Define it here as fallback
    def ensure_database_schema(db_path):
        """Ensure the database has all required columns."""
        pass  # Simplified version for fallback

# Set the page configuration
st.set_page_config(
    page_title="Items & Builds | SMITE 2 Combat Log Analyzer",
    page_icon="🛒",
    layout="wide",
)

# Custom CSS for styling
st.markdown("""
<style>
    .main-header {
        font-size: 36px;
        font-weight: bold;
        color: #FF9933;
        margin-bottom: 20px;
    }
    .sub-header {
        font-size: 24px;
        font-weight: bold;
        color: #5F9EA0;
        margin-top: 30px;
        margin-bottom: 15px;
    }
    .order-team {
        color: rgba(0, 0, 255, 0.8);
    }
    .chaos-team {
        color: rgba(255, 0, 0, 0.8);
    }
    .info-box {
        padding: 15px;
        border-radius: 5px;
        background-color: #BDE5F8;
        color: #00529B;
        margin-bottom: 20px;
    }
    .chart-container {
        margin-top: 20px;
        margin-bottom: 30px;
    }
</style>
""", unsafe_allow_html=True)

def load_item_data(db_path):
    """Load item purchase data from the SQLite database."""
    db_path = os.path.abspath(db_path)
    if not db_path or not os.path.exists(db_path):
        st.error(f"Database file not found: {db_path}. Please go back to the Home page and select a valid database.")
        return None
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Check what tables exist
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        data = {}
        
        # Load match information
        match_info = pd.DataFrame()
        if 'matches' in tables:
            try:
                match_info = pd.read_sql_query("""
                    SELECT match_id, source_file, map_name, duration_seconds
                    FROM matches
                    LIMIT 1
                """, conn)
                data["match_info"] = match_info
            except sqlite3.OperationalError as e:
                st.warning(f"Could not load match information: {str(e)}")
        
        # Load player information
        players_data = pd.DataFrame()
        if 'players' in tables:
            try:
                players_data = pd.read_sql_query("""
                    SELECT player_id, player_name, team_id, role, god_name
                    FROM players
                    ORDER BY team_id
                """, conn)
                data["players_data"] = players_data
            except sqlite3.OperationalError as e:
                st.warning(f"Could not load player data: {str(e)}")
        
        # Load item purchase events
        item_events = pd.DataFrame()
        if 'item_events' in tables:
            try:
                item_events = pd.read_sql_query("""
                    SELECT 
                        item_id, player_name, item_name, cost, 
                        event_time as purchase_time, 
                        CAST(strftime('%s', event_time) - strftime('%s', (SELECT MIN(event_time) FROM item_events)) AS INTEGER) as game_time_seconds,
                        NULL as item_slot, NULL as item_tier
                    FROM item_events
                    ORDER BY event_time
                """, conn)
                
                # Join with player data to get team_id and role
                if not players_data.empty:
                    item_events = pd.merge(
                        item_events,
                        players_data[['player_name', 'team_id', 'role', 'god_name']],
                        on='player_name',
                        how='left'
                    )
                
                # Convert time columns to the right types
                if 'game_time_seconds' in item_events.columns:
                    item_events['game_time_seconds'] = pd.to_numeric(item_events['game_time_seconds'], errors='coerce').fillna(0)
                
                data["item_events"] = item_events
            except sqlite3.OperationalError as e:
                # Try with a subset of columns if not all are available
                try:
                    cursor.execute("PRAGMA table_info(item_events)")
                    item_columns = [row[1] for row in cursor.fetchall()]
                    
                    if item_columns:
                        # Build a select statement with derived columns as needed
                        select_parts = []
                        for col in ['item_id', 'player_name', 'item_name']:
                            if col in item_columns:
                                select_parts.append(col)
                        
                        # Handle cost column (might be named differently)
                        if 'cost' in item_columns:
                            select_parts.append('cost')
                        elif 'item_cost' in item_columns:
                            select_parts.append('item_cost')
                        else:
                            select_parts.append('NULL as cost')
                        
                        # Handle time columns
                        if 'event_time' in item_columns:
                            select_parts.append('event_time as purchase_time')
                            select_parts.append("CAST(strftime('%s', event_time) - strftime('%s', (SELECT MIN(event_time) FROM item_events)) AS INTEGER) as game_time_seconds")
                        elif 'purchase_time' in item_columns:
                            select_parts.append('purchase_time')
                            if 'game_time_seconds' in item_columns:
                                select_parts.append('game_time_seconds')
                            else:
                                select_parts.append('NULL as game_time_seconds')
                        else:
                            select_parts.append('NULL as purchase_time')
                            select_parts.append('NULL as game_time_seconds')
                        
                        # Handle other columns
                        if 'item_slot' not in item_columns:
                            select_parts.append('NULL as item_slot')
                        else:
                            select_parts.append('item_slot')
                            
                        if 'item_tier' not in item_columns:
                            select_parts.append('NULL as item_tier')
                        else:
                            select_parts.append('item_tier')
                        
                        cols = ", ".join(select_parts)
                        
                        # Determine the order by clause
                        if 'event_time' in item_columns:
                            order_by = 'event_time'
                        elif 'game_time_seconds' in item_columns:
                            order_by = 'game_time_seconds'
                        elif 'purchase_time' in item_columns:
                            order_by = 'purchase_time'
                        else:
                            order_by = '1'
                            
                        item_events = pd.read_sql_query(f"""
                            SELECT {cols}
                            FROM item_events
                            ORDER BY {order_by}
                        """, conn)
                        
                        # Join with player data to get team_id and role
                        if not players_data.empty:
                            item_events = pd.merge(
                                item_events,
                                players_data[['player_name', 'team_id', 'role', 'god_name']],
                                on='player_name',
                                how='left'
                            )
                        
                        # Convert time columns to the right types
                        if 'game_time_seconds' in item_events.columns:
                            item_events['game_time_seconds'] = pd.to_numeric(item_events['game_time_seconds'], errors='coerce').fillna(0)
                        
                        data["item_events"] = item_events
                    else:
                        st.warning("No item event data found.")
                except sqlite3.OperationalError as e:
                    st.warning(f"Could not load item event data: {str(e)}")
        
        # Load player statistics for item impact analysis
        player_stats = pd.DataFrame()
        if 'player_stats' in tables:
            try:
                player_stats = pd.read_sql_query("""
                    SELECT * FROM player_stats
                """, conn)
                data["player_stats"] = player_stats
            except sqlite3.OperationalError as e:
                st.warning(f"Could not load player statistics: {str(e)}")
        
        conn.close()
        
        # Check if we have any usable data
        if not data or (
            "item_events" not in data or data["item_events"].empty
        ):
            st.warning("No item data found in the database.")
            return None
        
        return data
    
    except Exception as e:
        st.error(f"Error loading item data: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return None

def format_time(seconds):
    """Format seconds into MM:SS format, handling None values."""
    if seconds is None or not isinstance(seconds, (int, float)):
        return "00:00"
    
    try:
        seconds = int(seconds)
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{minutes:02}:{remaining_seconds:02}"
    except:
        return "00:00"

def get_team_color(team_id):
    """Get color for team based on team_id."""
    if team_id == 1:
        return "rgba(255, 0, 0, 0.7)"  # Red for Chaos
    elif team_id == 2:
        return "rgba(0, 0, 255, 0.7)"  # Blue for Order
    else:
        return "rgba(120, 120, 120, 0.7)"  # Gray for unknown

def create_item_timeline(item_events, match_duration=None):
    """Create a Gantt chart showing item purchases over time by player."""
    if item_events.empty:
        st.warning("Item events dataframe is empty")
        return None
    
    # Create a simple timeline chart that's guaranteed to work
    try:
        # Make a clean copy of the data
        df = item_events.copy()
        
        # Make sure we have all required columns, add defaults if not
        if 'team_id' not in df.columns:
            df['team_id'] = 0  # Default team
        
        # Force game_time_seconds to be numeric and ensure reasonable values
        df['game_time_seconds'] = pd.to_numeric(df['game_time_seconds'], errors='coerce').fillna(0)
        
        # IMPORTANT: Replace extreme time values (59:59 appears to be a default)
        # Any time above 59 minutes is likely a parsing error and should be reset to 0
        df.loc[df['game_time_seconds'] > 59*60, 'game_time_seconds'] = 0
        
        # Create a simpler timeline dataframe
        timeline_df = pd.DataFrame({
            'Player': df['player_name'],
            'Item': df['item_name'],
            'Start': df['game_time_seconds'],
            'End': df['game_time_seconds'] + 10,  # Make bars wider (10 seconds) to be more visible
            'Team': df['team_id'].apply(lambda x: f"Team {x}"),
        })
        
        # Add formatted time for display
        timeline_df['TimeFormatted'] = timeline_df['Start'].apply(lambda x: format_time(x))
        
        # Show debug info about the resulting data
        st.write(f"Created timeline with {len(timeline_df)} rows for {timeline_df['Player'].nunique()} players")
        
        # Group by Player and get min/max time to debug time ranges
        time_ranges = timeline_df.groupby('Player').agg({'Start': ['min', 'max']})
        with st.expander("View time ranges by player"):
            st.dataframe(time_ranges)
            
        # Create a visible scatter+lines chart
        fig = px.scatter(
            timeline_df, 
            x="Start",
            y="Player",
            color="Team",
            hover_name="Item",
            title="Item Purchase Timeline",
            custom_data=["TimeFormatted", "Item"],
            size_max=10,
            opacity=0.7
        )
        
        # Add marker symbols to make them clearly visible
        fig.update_traces(
            marker=dict(size=12, symbol="circle", line=dict(width=2, color="DarkSlateGrey")),
            hovertemplate="<b>%{customdata[1]}</b><br>Time: %{customdata[0]}"
        )
        
        # Format time axis
        # Set range to ensure visibility (0 to max+10% buffer)
        max_time = timeline_df['Start'].max()
        if max_time < 60:  # If max time is less than 1 minute, use 5 minutes as default range
            max_time = 300
            
        fig.update_xaxes(
            title="Time (minutes:seconds)",
            range=[0, max_time * 1.1],  # Add 10% buffer
            tickmode='array',
            tickvals=[i * 60 for i in range(0, int(max_time/60) + 2)],
            ticktext=[format_time(i * 60) for i in range(0, int(max_time/60) + 2)]
        )
        
        # Adjust height based on number of players
        num_players = timeline_df['Player'].nunique()
        fig.update_layout(
            height=max(400, num_players * 70),
            yaxis=dict(title=""),
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="right",
                x=0.99
            )
        )
        
        return fig
    except Exception as e:
        st.error(f"Error creating timeline chart: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return None

def create_build_path_diagram(item_events, player_name=None):
    """Create a hierarchical diagram showing the build path progression for a player with potential upgrade paths."""
    if item_events.empty:
        return None
    
    # Filter for the specific player if provided
    if player_name:
        player_items = item_events[item_events['player_name'] == player_name].copy()
        if player_items.empty:
            return None
    else:
        # If no player specified, return None
        return None
    
    # Order by purchase time
    player_items = player_items.sort_values(by='game_time_seconds')
    
    # Try to identify item tiers and upgrades based on name patterns
    # This is a simplified approach - a real implementation would use SMITE item data
    def identify_item_type(item_name):
        item_name = item_name.lower()
        if any(term in item_name for term in ['blink', 'teleport', 'purification', 'sprint', 'shell', 'sunder']):
            return 'Relic'
        elif any(term in item_name for term in ['potion', 'elixir', 'ward', 'chalice']):
            return 'Consumable'
        elif any(term in item_name for term in ['boots', 'shoes', 'talaria', 'reinforced']):
            return 'Boots'
        elif any(term in item_name for term in ['cudgel', 'dagger', 'sigil', 'axe', 'bumba']):
            return 'Starter'
        elif any(term in item_name for term in ['sword', 'blade', 'mace', 'staff', 'rod', 'pendant']):
            return 'Core Item'
        elif any(term in item_name for term in ['defense', 'armor', 'cloak', 'shield', 'mail', 'mantle']):
            return 'Defense'
        else:
            return 'Other'
    
    # Add item type and simplified tier estimate 
    player_items['item_type'] = player_items['item_name'].apply(identify_item_type)
    
    # Create a more structured figure using plotly
    fig = go.Figure()
    
    # Create nodes for different item categories in logical grouped progression
    item_types = ['Starter', 'Relic', 'Boots', 'Core Item', 'Defense', 'Consumable', 'Other']
    available_types = [t for t in item_types if t in player_items['item_type'].values]
    
    # Get team color for styling
    team_id = player_items['team_id'].iloc[0] if 'team_id' in player_items.columns else 0
    node_color = get_team_color(team_id)
    
    # Create the layout - columns for item types, rows for items
    max_y = 2
    item_positions = {}  # Store positions for connecting lines
    
    # For each item type, create a column of items in purchase order
    for i, item_type in enumerate(available_types):
        items_of_type = player_items[player_items['item_type'] == item_type].sort_values(by='game_time_seconds')
        
        # Plot each item in this type
        for j, (_, item) in enumerate(items_of_type.iterrows()):
            item_name = item['item_name'] 
            purchase_time = format_time(item.get('game_time_seconds', 0))
            cost = int(item.get('cost', 0)) if pd.notnull(item.get('cost', 0)) else 0
            
            # Position items in their category columns
            x_pos = i
            y_pos = j
            max_y = max(max_y, j)
            
            # Store position for this item
            item_positions[item_name] = (x_pos, y_pos)
            
            # Add node for this item
            fig.add_trace(
                go.Scatter(
                    x=[x_pos],
                    y=[y_pos],
                    mode='markers+text',
                    marker=dict(
                        symbol='circle',
                        size=30,
                        color=node_color,
                        line=dict(color='white', width=2)
                    ),
                    text=item_name,
                    textposition="top center",
                    hoverinfo='text',
                    hovertext=f"{item_name}<br>Time: {purchase_time}<br>Cost: {cost:,g}",
                    name=item_type
                )
            )
    
    # Set up the layout
    fig.update_layout(
        title=f"Build Path for {player_name}",
        showlegend=True,
        legend_title="Item Type",
        hovermode='closest',
        height=max(300, max_y * 100 + 50),
        margin=dict(b=30, l=20, r=20, t=40),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            tickvals=list(range(len(available_types))),
            ticktext=available_types,
            tickfont=dict(size=12)
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            autorange="reversed",
            visible=False,
            scaleanchor="x",
            scaleratio=0.5
        ),
        plot_bgcolor='white'
    )
    
    return fig

def create_item_popularity_chart(item_events):
    """Create a bar chart showing most purchased items."""
    if item_events.empty:
        return None
    
    # Get item counts
    item_counts = item_events['item_name'].value_counts().reset_index()
    item_counts.columns = ['Item', 'Count']
    
    # Sort by count and take top 15
    item_counts = item_counts.sort_values('Count', ascending=False).head(15)
    
    # Create bar chart
    fig = px.bar(
        item_counts,
        x='Count',
        y='Item',
        orientation='h',
        title='Most Popular Items',
        color='Count',
        color_continuous_scale=px.colors.sequential.Viridis
    )
    
    fig.update_layout(
        yaxis=dict(autorange="reversed"),
        height=500
    )
    
    return fig

def create_gold_distribution_chart(item_events, player_name=None):
    """Create a pie chart showing gold distribution by item category."""
    if item_events.empty:
        return None
    
    # Filter for the specific player if provided
    if player_name:
        data = item_events[item_events['player_name'] == player_name].copy()
        if data.empty:
            return None
    else:
        data = item_events.copy()
    
    # Ensure we have cost information
    if 'cost' not in data.columns or data['cost'].isna().all():
        return None
    
    # Create simple item categories based on name patterns
    # This is a simplified approach; ideally we'd have proper category data
    def categorize_item(item_name):
        item_name = item_name.lower()
        if any(term in item_name for term in ['sword', 'axe', 'dagger', 'blade', 'spear', 'bow']):
            return 'Weapon'
        elif any(term in item_name for term in ['armor', 'shield', 'plate', 'mail', 'guard']):
            return 'Armor'
        elif any(term in item_name for term in ['amulet', 'ring', 'necklace', 'pendant']):
            return 'Jewelry'
        elif any(term in item_name for term in ['staff', 'book', 'rod', 'wand', 'magic']):
            return 'Magical'
        elif any(term in item_name for term in ['potion', 'elixir', 'consumable']):
            return 'Consumable'
        elif any(term in item_name for term in ['boots', 'shoes', 'greaves']):
            return 'Footwear'
        else:
            return 'Other'
    
    # Add category column
    data.loc[:, 'Category'] = data['item_name'].apply(categorize_item)
    
    # Aggregate gold spent by category
    category_gold = data.groupby('Category')['cost'].sum().reset_index()
    category_gold.columns = ['Category', 'Gold Spent']
    
    # Create pie chart
    fig = px.pie(
        category_gold,
        values='Gold Spent',
        names='Category',
        title=f"Gold Distribution by Item Category{' for ' + player_name if player_name else ''}",
        color_discrete_sequence=px.colors.sequential.Plasma
    )
    
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(uniformtext_minsize=12, uniformtext_mode='hide')
    
    return fig

def create_item_impact_chart(item_events, player_stats):
    """Create a bar chart showing the statistical impact of key items."""
    # This is a placeholder for a more complex analysis
    # Ideally, we'd analyze performance metrics before and after key item purchases
    # For now, we'll just show a simplified implementation
    
    if item_events.empty or player_stats.empty:
        return None
    
    st.info("Item impact analysis requires more detailed timeline data. This is a simplified placeholder visualization.")
    
    # Get key items (e.g., expensive items)
    if 'cost' in item_events.columns:
        key_items = item_events.sort_values('cost', ascending=False)
        key_items = key_items.drop_duplicates('item_name').head(10)
        
        # Create dummy impact data
        impact_data = []
        
        for _, item in key_items.iterrows():
            item_name = item['item_name']
            cost = item.get('cost', 0)
            
            # In a real implementation, we'd compute actual statistical impact
            # This is just placeholder data
            impact_data.append({
                'Item': item_name,
                'Cost': cost,
                'Impact Score': cost / 1000  # Dummy score based on cost
            })
        
        # Create chart
        if impact_data:
            df = pd.DataFrame(impact_data)
            
            fig = px.bar(
                df,
                x='Item',
                y='Impact Score',
                title='Estimated Item Impact (Based on Cost)',
                color='Cost',
                color_continuous_scale=px.colors.sequential.Viridis
            )
            
            fig.update_layout(
                xaxis_tickangle=-45,
                height=400
            )
            
            return fig
    
    return None

def create_item_purchase_summary(item_events, match_duration=None):
    """Create a visualization summarizing what items players purchased, grouped by player and type."""
    if item_events.empty:
        return None
    
    try:
        # Make a copy to avoid modifying original
        df = item_events.copy()
        
        # Ensure numeric game time
        df['game_time_seconds'] = pd.to_numeric(df['game_time_seconds'], errors='coerce').fillna(0)
        
        # Filter out extreme values
        df = df[df['game_time_seconds'] < 3600]  # Max 1 hour
        
        # Add item type classification
        def classify_item(item_name):
            item_name = str(item_name).lower()
            if any(term in item_name for term in ['blink', 'teleport', 'purification', 'sprint', 'shell', 'sunder', 'beads', 'aegis']):
                return 'Relic'
            elif any(term in item_name for term in ['potion', 'elixir', 'ward', 'chalice']):
                return 'Consumable'
            elif any(term in item_name for term in ['boots', 'shoes', 'talaria', 'reinforced']):
                return 'Boots'
            elif any(term in item_name for term in ['cudgel', 'dagger', 'sigil', 'axe', 'bumba']):
                return 'Starter'
            elif any(term in item_name for term in ['staff', 'rod', 'pendant', 'wand', 'book']):
                return 'Magical'
            elif any(term in item_name for term in ['sword', 'blade', 'mace', 'hammer', 'axe', 'bow']):
                return 'Physical'
            elif any(term in item_name for term in ['defense', 'armor', 'cloak', 'shield', 'mail', 'mantle', 'protections']):
                return 'Defense'
            else:
                return 'Other'
        
        df['item_type'] = df['item_name'].apply(classify_item)
        df['purchase_min'] = (df['game_time_seconds'] / 60).astype(int)
        
        # Create a summary grouped by player, item type, and purchase minute
        summary_data = []
        
        # Process each player's items
        for player_name, player_items in df.groupby('player_name'):
            team_id = player_items['team_id'].iloc[0] if 'team_id' in player_items.columns else 0
            
            # Group by item type and minute
            for (item_type, minute), items in player_items.groupby(['item_type', 'purchase_min']):
                # Count items and total cost
                count = len(items)
                total_cost = items['cost'].sum() if 'cost' in items.columns else 0
                
                item_names = items['item_name'].tolist()
                item_text = ", ".join(item_names)
                
                summary_data.append({
                    'Player': player_name,
                    'Team': f"Team {team_id}",
                    'TeamID': team_id,
                    'ItemType': item_type,
                    'Minute': minute,
                    'Count': count,
                    'TotalCost': total_cost,
                    'Items': item_text
                })
        
        if not summary_data:
            return None
            
        # Create dataframe
        summary_df = pd.DataFrame(summary_data)
        
        # Create heatmap of item purchases over time
        fig = px.scatter(
            summary_df,
            x='Minute',
            y='Player',
            color='ItemType',
            size='Count',
            hover_name='ItemType',
            hover_data=['Items', 'TotalCost', 'Count'],
            facet_col='TeamID',
            facet_col_wrap=2,
            size_max=20,
            title="Item Purchase Summary by Player and Time"
        )
        
        # Improve the appearance
        fig.update_layout(
            height=600,
            xaxis_title="Minutes into Game",
            yaxis_title="",
            legend_title="Item Type",
        )
        
        # Improve hover information
        fig.update_traces(
            hovertemplate="<b>%{hovertext}</b><br>" +
                         "Time: %{x} minutes<br>" +
                         "Items: %{customdata[0]}<br>" +
                         "Cost: %{customdata[1]}<br>" +
                         "Count: %{customdata[2]}"
        )
        
        return fig
        
    except Exception as e:
        st.error(f"Error creating item purchase summary: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return None

def create_simple_item_sequence(item_events, player_name=None):
    """Create a simple sequential visualization of items purchased by a player in chronological order."""
    if item_events.empty or not player_name:
        return None
    
    # Filter for the specific player
    player_items = item_events[item_events['player_name'] == player_name].copy()
    if player_items.empty:
        return None
    
    # Order by purchase time
    player_items = player_items.sort_values(by='game_time_seconds')
    
    # Create a structured table of purchases
    purchase_data = []
    for i, (_, item) in enumerate(player_items.iterrows(), 1):
        purchase_time = format_time(item.get('game_time_seconds', 0))
        cost = int(item.get('cost', 0)) if pd.notnull(item.get('cost', 0)) else 0
        
        purchase_data.append({
            'Order': i,
            'Item': item['item_name'],
            'Time': purchase_time,
            'Cost': f"{cost:,g}",
        })
    
    # Create a DataFrame for display
    purchase_df = pd.DataFrame(purchase_data)
    
    return purchase_df

def main():
    st.title("Items & Builds Analysis")
    
    # Get database path from session state (check both keys for compatibility)
    db_path = None
    if 'selected_db' in st.session_state and st.session_state.selected_db:
        db_path = st.session_state.selected_db
    elif 'current_db' in st.session_state and st.session_state.current_db:
        # For backward compatibility
        db_path = st.session_state.current_db
        # Store it in the selected_db key for future use
        st.session_state.selected_db = db_path
    
    if not db_path:
        st.error("No database selected. Please go to the Home page and select a database.")
        return
    
    # Load item data
    data = load_item_data(db_path)
    
    if not data:
        st.warning("No item data available to analyze.")
        return
    
    # Get match duration for time formatting
    match_info = data.get("match_info", pd.DataFrame())
    match_duration = None
    if not match_info.empty and 'duration_seconds' in match_info.columns:
        match_duration = match_info['duration_seconds'].iloc[0]
    
    # Create tabs for different analysis views
    tab1, tab2, tab3 = st.tabs(["Item Timelines", "Build Paths", "Item Analysis"])
    
    with tab1:
        st.header("Item Purchase Timeline")
        st.write("This visualization shows when items were purchased by each player throughout the match.")
        
        item_events = data.get("item_events", pd.DataFrame())
        
        if not item_events.empty:
            # Show basic data info
            st.write(f"Found {len(item_events)} item events from {item_events['player_name'].nunique()} players")
            
            # Create tabs for different timeline views
            timeline_tab1, timeline_tab2 = st.tabs(["Item Purchase Summary", "Detailed Timeline"])
            
            with timeline_tab1:
                st.subheader("Item Purchase Summary by Player and Time")
                st.write("This visualization groups items by type and purchase time, showing what players bought throughout the match.")
                
                # Create the item purchase summary visualization
                item_summary_fig = create_item_purchase_summary(item_events, match_duration)
                
                if item_summary_fig:
                    st.plotly_chart(item_summary_fig, use_container_width=True)
                else:
                    st.warning("Could not create item purchase summary visualization.")
            
            with timeline_tab2:
                # Print summary of columns
                missing_any = False
                for col in ['player_name', 'item_name', 'game_time_seconds', 'team_id']:
                    if col in item_events.columns:
                        null_count = item_events[col].isna().sum()
                        if null_count > 0:
                            st.write(f"⚠️ Column '{col}' has {null_count} null values")
                            missing_any = True
                        else:
                            st.write(f"✅ Column '{col}' is present and complete")
                    else:
                        st.write(f"❌ Column '{col}' is missing")
                        missing_any = True
                
                # Show the raw data only if there are issues
                if missing_any:
                    with st.expander("View raw item data"):
                        st.dataframe(item_events.head(10))
                
                # Create the detailed timeline chart
                st.subheader("Detailed Item Purchase Timeline")
                timeline_fig = create_item_timeline(item_events, match_duration)
                
                if timeline_fig:
                    st.plotly_chart(timeline_fig, use_container_width=True)
                else:
                    st.error("Could not create item timeline visualization. Check the errors above.")
        else:
            st.warning("No item purchase data available.")
    
    with tab2:
        st.header("Build Path Analysis")
        st.write("Select a player to view their item build path progression.")
        
        item_events = data.get("item_events", pd.DataFrame())
        players_data = data.get("players_data", pd.DataFrame())
        
        if not item_events.empty and 'player_name' in item_events.columns:
            # Get unique players with items
            players_with_items = item_events['player_name'].unique()
            
            if players_with_items.size > 0:
                # Create two columns for team selection
                col1, col2 = st.columns(2)
                
                with col1:
                    # Get Chaos team players
                    if not players_data.empty and 'team_id' in players_data.columns:
                        chaos_players = players_data[players_data['team_id'] == 1]['player_name'].tolist()
                        chaos_players = [p for p in chaos_players if p in players_with_items]
                        
                        if chaos_players:
                            st.markdown("<div class='chaos-team'>Chaos Team</div>", unsafe_allow_html=True)
                            selected_chaos_player = st.selectbox(
                                "Select Chaos player",
                                chaos_players,
                                key="chaos_player"
                            )
                            
                            if selected_chaos_player:
                                # Show simple item sequence first
                                st.subheader(f"Item Purchase Sequence for {selected_chaos_player}")
                                simple_sequence = create_simple_item_sequence(item_events, selected_chaos_player)
                                if simple_sequence is not None:
                                    st.dataframe(simple_sequence, use_container_width=True, hide_index=True)
                                else:
                                    st.warning("No purchase data available for this player.")
                                
                                # Show build path diagram
                                st.subheader("Build Path by Item Category")
                                build_fig = create_build_path_diagram(item_events, selected_chaos_player)
                                if build_fig:
                                    st.plotly_chart(build_fig, use_container_width=True)
                                
                                # Show gold distribution for this player
                                gold_dist_fig = create_gold_distribution_chart(item_events, selected_chaos_player)
                                if gold_dist_fig:
                                    st.plotly_chart(gold_dist_fig, use_container_width=True)
                
                with col2:
                    # Get Order team players
                    if not players_data.empty and 'team_id' in players_data.columns:
                        order_players = players_data[players_data['team_id'] == 2]['player_name'].tolist()
                        order_players = [p for p in order_players if p in players_with_items]
                        
                        if order_players:
                            st.markdown("<div class='order-team'>Order Team</div>", unsafe_allow_html=True)
                            selected_order_player = st.selectbox(
                                "Select Order player",
                                order_players,
                                key="order_player"
                            )
                            
                            if selected_order_player:
                                # Show simple item sequence first
                                st.subheader(f"Item Purchase Sequence for {selected_order_player}")
                                simple_sequence = create_simple_item_sequence(item_events, selected_order_player)
                                if simple_sequence is not None:
                                    st.dataframe(simple_sequence, use_container_width=True, hide_index=True)
                                else:
                                    st.warning("No purchase data available for this player.")
                                
                                # Show build path diagram
                                st.subheader("Build Path by Item Category")
                                build_fig = create_build_path_diagram(item_events, selected_order_player)
                                if build_fig:
                                    st.plotly_chart(build_fig, use_container_width=True)
                                
                                # Show gold distribution for this player
                                gold_dist_fig = create_gold_distribution_chart(item_events, selected_order_player)
                                if gold_dist_fig:
                                    st.plotly_chart(gold_dist_fig, use_container_width=True)
            else:
                st.warning("No players with item purchase data found.")
        else:
            st.warning("No item purchase data available.")
    
    with tab3:
        st.header("Item Analysis")
        st.write("Analysis of item popularity and impact across the match.")
        
        item_events = data.get("item_events", pd.DataFrame())
        player_stats = data.get("player_stats", pd.DataFrame())
        
        if not item_events.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                # Show item popularity chart
                pop_fig = create_item_popularity_chart(item_events)
                if pop_fig:
                    st.plotly_chart(pop_fig, use_container_width=True)
            
            with col2:
                # Show overall gold distribution
                gold_dist_fig = create_gold_distribution_chart(item_events)
                if gold_dist_fig:
                    st.plotly_chart(gold_dist_fig, use_container_width=True)
            
            # Show item impact analysis if we have player stats
            if not player_stats.empty:
                impact_fig = create_item_impact_chart(item_events, player_stats)
                if impact_fig:
                    st.plotly_chart(impact_fig, use_container_width=True)
        else:
            st.warning("No item data available for analysis.")
    
    # Footer
    st.markdown("---")
    st.markdown(
        "Developed for SMITE 2 Combat Log Analysis | &copy; 2025",
        unsafe_allow_html=True,
    )

if __name__ == "__main__":
    main() 