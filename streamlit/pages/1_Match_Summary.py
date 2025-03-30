import os
import sys
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Try to import the ensure_database_schema function from Home
try:
    from streamlit.Home import ensure_database_schema
except ImportError:
    # Define it here as fallback
    def ensure_database_schema(db_path):
        """
        Ensure the database has all required columns in its tables.
        This function will add any missing columns to the existing tables.
        """
        conn = None
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check if player_stats table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='player_stats'")
            if cursor.fetchone():
                # Check for required columns in player_stats
                cursor.execute("PRAGMA table_info(player_stats)")
                existing_columns = [row[1] for row in cursor.fetchall()]
                
                # Define required columns and their types
                required_columns = {
                    'damage_mitigated': 'INTEGER DEFAULT 0',
                    'healing_done': 'INTEGER DEFAULT 0',
                    'structure_damage': 'INTEGER DEFAULT 0',
                    'gold_earned': 'INTEGER DEFAULT 0',
                    'experience_earned': 'INTEGER DEFAULT 0'
                }
                
                # Add any missing columns
                for column, dtype in required_columns.items():
                    if column not in existing_columns:
                        st.info(f"Adding missing column '{column}' to player_stats table")
                        try:
                            cursor.execute(f"ALTER TABLE player_stats ADD COLUMN {column} {dtype}")
                        except sqlite3.OperationalError as e:
                            st.warning(f"Could not add column '{column}': {e}")
                
                conn.commit()
                st.success("Database schema has been checked and updated if needed")
            else:
                st.warning("player_stats table not found in database")
                
        except Exception as e:
            st.error(f"Error ensuring database schema: {e}")
        finally:
            if conn:
                conn.close()

# Set the page configuration
st.set_page_config(
    page_title="Match Summary | SMITE 2 Combat Log Analyzer",
    page_icon="⚔️",
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
    .team-header-1 {
        color: #4169E1;
        font-weight: bold;
        font-size: 20px;
    }
    .team-header-2 {
        color: #FF4500;
        font-weight: bold;
        font-size: 20px;
    }
    .metric-card {
        background-color: #F6F6F6;
        border-radius: 5px;
        padding: 10px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .metric-value {
        font-size: 24px;
        font-weight: bold;
    }
    .metric-label {
        font-size: 14px;
        color: #666;
    }
    .win-team {
        border-left: 5px solid #4F8A10;
    }
    .lose-team {
        border-left: 5px solid #D8000C;
    }
    .order-table {
        border-left: 5px solid rgba(0, 0, 255, 0.7) !important;
    }
    .chaos-table {
        border-left: 5px solid rgba(255, 0, 0, 0.7) !important;
    }
    .table-header {
        font-weight: bold;
        font-size: 20px;
        margin-bottom: 10px;
    }
    .order-header {
        color: rgba(0, 0, 255, 0.8);
    }
    .chaos-header {
        color: rgba(255, 0, 0, 0.8);
    }
</style>
""", unsafe_allow_html=True)

def load_match_data(db_path):
    """Load the match data from the SQLite database."""
    db_path = os.path.abspath(db_path)
    if not db_path or not os.path.exists(db_path):
        st.error(f"Database file not found: {db_path}. Please go back to the Home page and select a valid database.")
        return None
    
    try:
        # Try to ensure the database has all required columns
        ensure_database_schema(db_path)
        
        conn = sqlite3.connect(db_path)
        
        # Check what tables exist
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        # Load match information (with fallbacks)
        match_info = pd.DataFrame()
        if 'matches' in tables:
            try:
                match_info = pd.read_sql_query("""
                    SELECT match_id, source_file, map_name, duration_seconds
                    FROM matches
                    LIMIT 1
                """, conn)
            except sqlite3.OperationalError:
                # If not all columns exist, query what we can
                columns = []
                for col in ['match_id', 'source_file', 'map_name', 'duration_seconds']:
                    try:
                        cursor.execute(f"SELECT {col} FROM matches LIMIT 1")
                        cursor.fetchone()
                        columns.append(col)
                    except sqlite3.OperationalError:
                        pass
                
                if columns:
                    col_str = ", ".join(columns)
                    match_info = pd.read_sql_query(f"""
                        SELECT {col_str}
                        FROM matches
                        LIMIT 1
                    """, conn)
        
        if match_info.empty:
            st.warning("No match information available in the database.")
        
        # Load player information and statistics
        players_data = pd.DataFrame()
        if 'players' in tables:
            try:
                # Get base player data
                players_data = pd.read_sql_query("""
                    SELECT player_id, player_name, team_id, role, god_name
                    FROM players
                    ORDER BY team_id
                """, conn)
                
                # If player_stats table exists, join with it
                if 'player_stats' in tables:
                    # Get available columns from player_stats table
                    cursor.execute("PRAGMA table_info(player_stats)")
                    player_stats_columns = [row[1] for row in cursor.fetchall()]
                    
                    if player_stats_columns:
                        # Build a query with only available columns
                        stat_cols = []
                        for col in ['kills', 'deaths', 'assists', 'damage_dealt', 'damage_mitigated', 
                                   'healing_done', 'gold_earned', 'experience_earned', 'structure_damage']:
                            if col in player_stats_columns:
                                stat_cols.append(f"ps.{col}")
                        
                        if stat_cols:
                            # Get player stats for those players
                            stats_query = f"""
                                SELECT player_name, {', '.join(stat_cols)}
                                FROM player_stats ps
                            """
                            
                            try:
                                player_stats = pd.read_sql_query(stats_query, conn)
                                
                                # Merge with player data
                                if not player_stats.empty:
                                    players_data = pd.merge(
                                        players_data, 
                                        player_stats,
                                        on='player_name',
                                        how='left'
                                    )
                            except sqlite3.OperationalError as e:
                                st.warning(f"Could not load complete player statistics: {str(e)}")
            except sqlite3.OperationalError as e:
                st.warning(f"Could not load player data: {str(e)}")
        
        if players_data.empty:
            st.warning("No player data available in the database.")
        
        # Load timeline events for key moments
        timeline_events = pd.DataFrame()
        if 'timeline_events' in tables:
            try:
                cursor.execute("PRAGMA table_info(timeline_events)")
                timeline_columns = [row[1] for row in cursor.fetchall()]
                
                if timeline_columns:
                    # Build a query with only available columns
                    col_list = []
                    for col in ['event_time', 'event_type', 'event_category', 'importance', 
                                 'team_id', 'entity_name', 'target_name', 'value', 'event_description',
                                 'game_time_seconds']:
                        if col in timeline_columns:
                            col_list.append(col)
                    
                    if col_list:
                        timeline_query = f"""
                            SELECT {', '.join(col_list)}
                            FROM timeline_events
                            ORDER BY event_time
                        """
                        
                        # Add importance filter if available
                        if 'importance' in col_list:
                            timeline_query = timeline_query.replace(
                                "ORDER BY", "WHERE importance >= 7 ORDER BY"
                            )
                        
                        timeline_events = pd.read_sql_query(timeline_query, conn)
            except sqlite3.OperationalError as e:
                st.warning(f"Could not load timeline events: {str(e)}")
        
        # Load team statistics summary
        team_stats = pd.DataFrame()
        if all(table in tables for table in ['players', 'player_stats']):
            try:
                # Get available columns from player_stats table
                cursor.execute("PRAGMA table_info(player_stats)")
                player_stats_columns = [row[1] for row in cursor.fetchall()]
                
                # Build aggregate expressions for available columns
                agg_columns = []
                
                # Add aggregations for each available column
                agg_map = {
                    'kills': 'total_kills',
                    'deaths': 'total_deaths',
                    'assists': 'total_assists',
                    'damage_dealt': 'total_damage',
                    'damage_mitigated': 'total_mitigated',
                    'healing_done': 'total_healing',
                    'gold_earned': 'total_gold',
                    'experience_earned': 'total_xp',
                    'structure_damage': 'total_structure_damage'
                }
                
                for col, agg_name in agg_map.items():
                    if col in player_stats_columns:
                        agg_columns.append(f"SUM({col}) as {agg_name}")
                
                if agg_columns:
                    # Build and execute query
                    query = f"""
                        SELECT p.team_id, {', '.join(agg_columns)}
                        FROM player_stats ps
                        JOIN players p ON ps.player_name = p.player_name AND ps.match_id = p.match_id
                        GROUP BY p.team_id
                    """
                    
                    team_stats = pd.read_sql_query(query, conn)
            except sqlite3.OperationalError as e:
                st.warning(f"Could not load team statistics: {str(e)}")
        
        conn.close()
        
        # Check if we have any usable data
        if match_info.empty and players_data.empty and timeline_events.empty and team_stats.empty:
            st.error("No usable data found in the database.")
            return None
        
        return {
            "match_info": match_info,
            "players_data": players_data,
            "timeline_events": timeline_events,
            "team_stats": team_stats
        }
    
    except Exception as e:
        st.error(f"Error loading match data: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return None

def format_team_name(team_id):
    """Format team name based on team_id."""
    if team_id == 1:
        return "Order (Blue)"
    elif team_id == 2:
        return "Chaos (Red)"
    else:
        return f"Team {team_id}"

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

def create_team_comparison_chart(team_stats):
    """Create a bar chart comparing team statistics."""
    if team_stats is None or team_stats.empty:
        return None
    
    # Create normalized data for comparison
    compare_data = team_stats.copy()
    
    # Select the metrics to compare
    metrics = {
        'total_kills': 'Kills',
        'total_damage': 'Damage (÷1000)',
        'total_gold': 'Gold (÷1000)',
        'total_structure_damage': 'Structure Damage (÷1000)'
    }
    
    # Create a dataframe for plotting
    plot_data = []
    for idx, row in compare_data.iterrows():
        team_name = format_team_name(row['team_id'])
        for metric, label in metrics.items():
            # Normalize large values for better visualization
            value = row[metric]
            if metric in ['total_damage', 'total_gold', 'total_structure_damage']:
                value = value / 1000
            
            plot_data.append({
                'Team': team_name,
                'Metric': label,
                'Value': value
            })
    
    plot_df = pd.DataFrame(plot_data)
    
    # Create the bar chart
    fig = px.bar(
        plot_df,
        x='Metric',
        y='Value',
        color='Team',
        barmode='group',
        color_discrete_map={
            "Order (Blue)": "#4169E1",
            "Chaos (Red)": "#FF4500"
        },
        height=400
    )
    
    fig.update_layout(
        title="Team Comparison",
        xaxis_title=None,
        yaxis_title="Value",
        legend_title=None,
        font=dict(size=14),
        margin=dict(l=40, r=40, t=60, b=40),
        hovermode="x unified"
    )
    
    return fig

def create_player_performance_table(players_data, team_name=None):
    """Create a formatted table for player performances with totals row."""
    if players_data is None or len(players_data) == 0:
        return None
    
    # Create a copy to avoid SettingWithCopyWarning
    players_df = players_data.copy()
    
    # Check what columns we have
    display_cols = []
    rename_map = {}
    
    # Always include player name and god
    if 'player_name' in players_df.columns:
        display_cols.append('player_name')
        rename_map['player_name'] = 'Player'
    
    if 'god_name' in players_df.columns:
        display_cols.append('god_name')
        rename_map['god_name'] = 'God'
    
    if 'role' in players_df.columns:
        display_cols.append('role')
        rename_map['role'] = 'Role'
    
    # Track numeric columns for totals
    numeric_cols = []
    
    # Add KDA columns if available
    if 'kills' in players_df.columns:
        display_cols.append('kills')
        rename_map['kills'] = 'Kills'
        numeric_cols.append('kills')
        # Ensure numeric
        players_df['kills'] = pd.to_numeric(players_df['kills'], errors='coerce').fillna(0).astype(int)
    
    if 'deaths' in players_df.columns:
        display_cols.append('deaths')
        rename_map['deaths'] = 'Deaths'
        numeric_cols.append('deaths')
        # Ensure numeric
        players_df['deaths'] = pd.to_numeric(players_df['deaths'], errors='coerce').fillna(0).astype(int)
    
    if 'assists' in players_df.columns:
        display_cols.append('assists')
        rename_map['assists'] = 'Assists'
        numeric_cols.append('assists')
        # Ensure numeric
        players_df['assists'] = pd.to_numeric(players_df['assists'], errors='coerce').fillna(0).astype(int)
    
    # Add gold if available
    if 'gold_earned' in players_df.columns:
        players_df['gold_formatted'] = players_df['gold_earned'].apply(lambda x: f"{x:,}" if pd.notnull(x) else "N/A")
        display_cols.append('gold_formatted')
        rename_map['gold_formatted'] = 'Gold Earned'
        numeric_cols.append('gold_earned')
    
    # Add damage if available
    if 'damage_dealt' in players_df.columns:
        players_df['damage_formatted'] = players_df['damage_dealt'].apply(lambda x: f"{x:,}" if pd.notnull(x) else "N/A")
        display_cols.append('damage_formatted')
        rename_map['damage_formatted'] = 'Damage'
        numeric_cols.append('damage_dealt')
    
    if not display_cols:
        return None
    
    # Create display dataframe with selected columns and renamed headers
    display_df = players_df[display_cols].copy()
    display_df = display_df.rename(columns=rename_map)
    
    # Calculate totals for numeric columns
    if numeric_cols:
        totals = {}
        for col in display_cols:
            if col in ['player_name', 'god_name', 'role']:
                if col == 'player_name':
                    totals[rename_map[col]] = 'TOTAL'
                else:
                    totals[rename_map[col]] = ''
            elif col == 'gold_formatted' and 'gold_earned' in numeric_cols:
                total_gold = players_df['gold_earned'].sum()
                totals[rename_map[col]] = f"{total_gold:,}"
            elif col == 'damage_formatted' and 'damage_dealt' in numeric_cols:
                total_damage = players_df['damage_dealt'].sum()
                totals[rename_map[col]] = f"{total_damage:,}"
            elif col in numeric_cols:
                totals[rename_map[col]] = players_df[col].sum()
        
        # Append totals row
        display_df = pd.concat([display_df, pd.DataFrame([totals])], ignore_index=True)
    
    return display_df

def create_gold_diff_chart(match_data):
    """Create a chart showing gold difference between teams (no simulated data)."""
    if not match_data or 'team_stats' not in match_data or match_data['team_stats'].empty or len(match_data['team_stats']) < 2:
        return None
    
    team_stats = match_data['team_stats']
    
    # Get the gold for each team
    if 'total_gold' not in team_stats.columns:
        return None
    
    # Make sure team_id is there
    if 'team_id' not in team_stats.columns:
        return None
    
    # Create a bar chart with the gold values for each team
    chaos_gold = team_stats[team_stats['team_id'] == 1]['total_gold'].values[0] if 1 in team_stats['team_id'].values else 0
    order_gold = team_stats[team_stats['team_id'] == 2]['total_gold'].values[0] if 2 in team_stats['team_id'].values else 0
    
    diff = chaos_gold - order_gold
    leading_team = "Chaos" if diff > 0 else "Order" if diff < 0 else "Tied"
    abs_diff = abs(diff)
    
    fig = go.Figure()
    
    # Add bars for each team
    fig.add_trace(go.Bar(
        x=['Chaos'],
        y=[chaos_gold],
        name='Chaos',
        marker_color='rgba(255, 0, 0, 0.7)',
        text=[f"{chaos_gold:,}"],
        textposition='auto',
    ))
    
    fig.add_trace(go.Bar(
        x=['Order'],
        y=[order_gold],
        name='Order',
        marker_color='rgba(0, 0, 255, 0.7)',
        text=[f"{order_gold:,}"],
        textposition='auto',
    ))
    
    # Update the layout
    fig.update_layout(
        title=f"Team Gold Comparison: {leading_team} ahead by {abs_diff:,} gold",
        xaxis_title="Team",
        yaxis_title="Gold",
        yaxis=dict(
            title="Gold",
            tickformat=",",
        ),
        barmode='group'
    )
    
    return fig

def create_damage_chart(match_data):
    """Create a chart showing team damage comparison (no simulated data)."""
    if not match_data or 'team_stats' not in match_data or match_data['team_stats'].empty or len(match_data['team_stats']) < 2:
        return None
    
    team_stats = match_data['team_stats']
    
    # Get the damage for each team
    if 'total_damage' not in team_stats.columns:
        return None
    
    # Make sure team_id is there
    if 'team_id' not in team_stats.columns:
        return None
    
    # Create a bar chart with the damage values for each team
    chaos_damage = team_stats[team_stats['team_id'] == 1]['total_damage'].values[0] if 1 in team_stats['team_id'].values else 0
    order_damage = team_stats[team_stats['team_id'] == 2]['total_damage'].values[0] if 2 in team_stats['team_id'].values else 0
    
    diff = chaos_damage - order_damage
    leading_team = "Chaos" if diff > 0 else "Order" if diff < 0 else "Tied"
    abs_diff = abs(diff)
    
    fig = go.Figure()
    
    # Add bars for each team
    fig.add_trace(go.Bar(
        x=['Chaos'],
        y=[chaos_damage],
        name='Chaos',
        marker_color='rgba(255, 0, 0, 0.7)',
        text=[f"{chaos_damage:,}"],
        textposition='auto',
    ))
    
    fig.add_trace(go.Bar(
        x=['Order'],
        y=[order_damage],
        name='Order',
        marker_color='rgba(0, 0, 255, 0.7)',
        text=[f"{order_damage:,}"],
        textposition='auto',
    ))
    
    # Update the layout
    fig.update_layout(
        title=f"Team Damage Comparison: {leading_team} ahead by {abs_diff:,} damage",
        xaxis_title="Team",
        yaxis_title="Damage",
        yaxis=dict(
            title="Damage",
            tickformat=",",
        ),
        barmode='group'
    )
    
    return fig

def get_event_icon(event_type):
    """Get an appropriate icon for the event type."""
    event_type = str(event_type).lower() if event_type is not None else "unknown"
    
    if 'kill' in event_type:
        return "☠️"
    elif 'objective' in event_type or 'gold' in event_type:
        return "🏆"
    elif 'tower' in event_type or 'phoenix' in event_type or 'structure' in event_type:
        return "🏰"
    elif 'fire' in event_type:
        return "🔥"
    elif 'buff' in event_type:
        return "⚡"
    elif 'heal' in event_type or 'health' in event_type:
        return "💖"
    elif 'damage' in event_type:
        return "💥"
    elif 'item' in event_type or 'purchase' in event_type:
        return "🛒"
    elif 'level' in event_type or 'xp' in event_type:
        return "⬆️"
    else:
        return "🔹"

def test_queries():
    """Test and validate all SQL queries in this file against a test database.
    This function is for development and testing purposes only.
    """
    import sqlite3
    
    # Create a test in-memory database with the expected schema
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    
    # Create the tables we query in this file
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS matches (
        match_id TEXT PRIMARY KEY,
        source_file TEXT NOT NULL,
        map_name TEXT,
        duration_seconds INTEGER
    );
    
    CREATE TABLE IF NOT EXISTS players (
        player_id INTEGER PRIMARY KEY,
        match_id TEXT,
        player_name TEXT NOT NULL,
        team_id INTEGER,
        role TEXT,
        god_name TEXT
    );
    
    CREATE TABLE IF NOT EXISTS player_stats (
        stat_id INTEGER PRIMARY KEY,
        match_id TEXT,
        player_name TEXT NOT NULL,
        team_id INTEGER,
        kills INTEGER DEFAULT 0,
        deaths INTEGER DEFAULT 0,
        assists INTEGER DEFAULT 0,
        damage_dealt INTEGER DEFAULT 0,
        damage_taken INTEGER DEFAULT 0,
        healing_done INTEGER DEFAULT 0,
        damage_mitigated INTEGER DEFAULT 0,
        gold_earned INTEGER DEFAULT 0,
        experience_earned INTEGER DEFAULT 0,
        cc_time_inflicted INTEGER DEFAULT 0,
        structure_damage INTEGER DEFAULT 0
    );
    
    CREATE TABLE IF NOT EXISTS timeline_events (
        event_id INTEGER PRIMARY KEY,
        match_id TEXT,
        event_time TIMESTAMP NOT NULL,
        game_time_seconds INTEGER,
        event_type TEXT NOT NULL,
        event_category TEXT,
        importance INTEGER,
        event_description TEXT,
        entity_name TEXT,
        target_name TEXT,
        team_id INTEGER
    );
    """)
    
    # Insert sample data
    cursor.execute("INSERT INTO matches VALUES ('test_match', 'test.log', 'Test Map', 1200)")
    cursor.execute("INSERT INTO players VALUES (1, 'test_match', 'Player1', 1, 'Mid', 'Zeus')")
    cursor.execute("INSERT INTO players VALUES (2, 'test_match', 'Player2', 2, 'Solo', 'Hades')")
    cursor.execute("INSERT INTO player_stats VALUES (1, 'test_match', 'Player1', 1, 5, 2, 3, 10000, 5000, 1000, 2000, 8000, 9000, 20, 1500)")
    cursor.execute("INSERT INTO player_stats VALUES (2, 'test_match', 'Player2', 2, 2, 5, 4, 8000, 10000, 500, 3000, 7000, 8000, 15, 500)")
    
    conn.commit()
    
    print("Testing match info query...")
    try:
        cursor.execute("""
            SELECT match_id, source_file, map_name, duration_seconds
            FROM matches
            LIMIT 1
        """)
        print("✅ Match info query passed")
    except sqlite3.Error as e:
        print(f"❌ Match info query failed: {e}")
    
    print("\nTesting player stats query...")
    try:
        cursor.execute("""
            SELECT p.player_id, p.player_name, p.team_id, p.role, p.god_name,
                   ps.kills, ps.deaths, ps.assists, ps.damage_dealt,
                   ps.damage_mitigated, ps.healing_done, ps.gold_earned,
                   ps.experience_earned, ps.structure_damage
            FROM players p
            LEFT JOIN player_stats ps ON p.player_name = ps.player_name AND p.match_id = ps.match_id
            ORDER BY p.team_id
        """)
        print("✅ Player stats query passed")
    except sqlite3.Error as e:
        print(f"❌ Player stats query failed: {e}")
    
    print("\nTesting team stats query...")
    try:
        cursor.execute("""
            SELECT p.team_id, 
                   SUM(kills) as total_kills,
                   SUM(deaths) as total_deaths,
                   SUM(assists) as total_assists,
                   SUM(damage_dealt) as total_damage,
                   SUM(damage_mitigated) as total_mitigated,
                   SUM(healing_done) as total_healing,
                   SUM(gold_earned) as total_gold,
                   SUM(experience_earned) as total_xp,
                   SUM(structure_damage) as total_structure_damage
            FROM player_stats ps
            JOIN players p ON ps.player_name = p.player_name AND ps.match_id = p.match_id
            GROUP BY p.team_id
        """)
        print("✅ Team stats query passed")
    except sqlite3.Error as e:
        print(f"❌ Team stats query failed: {e}")
    
    print("\nTesting timeline events query...")
    try:
        cursor.execute("""
            SELECT 
                event_time, event_type, event_category, importance, 
                team_id, entity_name, target_name, event_description,
                game_time_seconds
            FROM timeline_events
            WHERE importance >= 7
            ORDER BY event_time
        """)
        print("✅ Timeline events query passed")
    except sqlite3.Error as e:
        print(f"❌ Timeline events query failed: {e}")
    
    conn.close()
    print("\nAll query tests completed.")

def main():
    st.title("Match Summary")
    
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
    
    match_data = load_match_data(db_path)
    
    if not match_data:
        return  # Error messages already displayed by load_match_data
    
    # Add CSS for team styling
    st.markdown("""
    <style>
    .order-table {
        border-left: 5px solid rgba(0, 0, 255, 0.7) !important;
    }
    .chaos-table {
        border-left: 5px solid rgba(255, 0, 0, 0.7) !important;
    }
    .table-header {
        font-weight: bold;
        font-size: 20px;
        margin-bottom: 10px;
    }
    .order-header {
        color: rgba(0, 0, 255, 0.8);
    }
    .chaos-header {
        color: rgba(255, 0, 0, 0.8);
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Extract match information
    match_info = match_data.get('match_info', pd.DataFrame())
    if not match_info.empty:
        match_id = match_info.get('match_id', ['No Data']).iloc[0] if 'match_id' in match_info else 'No Data'
        map_name = match_info.get('map_name', ['No Data']).iloc[0] if 'map_name' in match_info else 'No Data'
        
        duration_seconds = match_info.get('duration_seconds', [0]).iloc[0] if 'duration_seconds' in match_info else 0
        match_duration = format_time(duration_seconds) if duration_seconds and duration_seconds > 0 else "No Data"
        
        # Display match overview in header
        st.header(f"Match ID: {match_id}")
        if map_name != 'No Data':
            st.subheader(f"Map: {map_name} | Duration: {match_duration}")
        else:
            st.subheader(f"Duration: {match_duration}")
    else:
        st.header("Match Summary")
        st.subheader("Match data not available")
    
    # Extract and process player data
    players_data = match_data.get('players_data', pd.DataFrame())
    
    if not players_data.empty:
        if 'gold_earned' in players_data.columns:
            # Format gold for display handled in create_player_performance_table
            pass
        
        # Create team tables (Order and Chaos)
        if 'team_id' in players_data.columns:
            team1_data = players_data[players_data['team_id'] == 1]
            team2_data = players_data[players_data['team_id'] == 2]
            
            # Order Team (blue)
            st.markdown("<div class='table-header order-header'>Order Team</div>", unsafe_allow_html=True)
            if not team2_data.empty:
                order_table = create_player_performance_table(team2_data, "Order")
                if order_table is not None:
                    st.markdown("<div class='order-table'>", unsafe_allow_html=True)
                    st.dataframe(order_table, hide_index=True, use_container_width=True)
                    st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.warning("No player data available for Order team.")
            
            # Chaos Team (red)
            st.markdown("<div class='table-header chaos-header'>Chaos Team</div>", unsafe_allow_html=True)
            if not team1_data.empty:
                chaos_table = create_player_performance_table(team1_data, "Chaos")
                if chaos_table is not None:
                    st.markdown("<div class='chaos-table'>", unsafe_allow_html=True)
                    st.dataframe(chaos_table, hide_index=True, use_container_width=True)
                    st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.warning("No player data available for Chaos team.")
        else:
            st.subheader("Players")
            st.write(create_player_performance_table(players_data))
    else:
        st.warning("No player data available for this match.")
    
    # Display team stats comparison if available
    team_stats = match_data.get('team_stats', pd.DataFrame())
    
    if not team_stats.empty:
        st.subheader("Team Comparison")
        
        # Create gold comparison chart
        gold_chart = create_gold_diff_chart(match_data)
        if gold_chart:
            st.plotly_chart(gold_chart, use_container_width=True)
        else:
            st.warning("Gold data is not available for comparison.")
        
        # Create damage chart
        if 'total_damage' in team_stats.columns:
            damage_chart = create_damage_chart(match_data)
            if damage_chart:
                st.plotly_chart(damage_chart, use_container_width=True)
            else:
                st.warning("Damage data is not available for comparison.")
        else:
            st.warning("Team damage data is not available.")
    else:
        st.warning("Team statistics are not available for this match.")
    
    # Display timeline of important events
    timeline_events = match_data.get('timeline_events', pd.DataFrame())
    
    if not timeline_events.empty:
        st.subheader("Timeline of Key Events")
        
        # Filter for important events if we have importance data
        if 'importance' in timeline_events.columns:
            timeline_events = timeline_events[timeline_events['importance'] >= 7]
        
        if not timeline_events.empty:
            # Check if we have game_time_seconds
            has_time = 'game_time_seconds' in timeline_events.columns
            
            # Create timeline
            timeline_container = st.container()
            with timeline_container:
                for _, event in timeline_events.iterrows():
                    # Get event time
                    event_time = format_time(event.get('game_time_seconds', None)) if has_time else "??:??"
                    
                    # Get icon based on event type
                    event_type = event.get('event_type', 'unknown')
                    icon = get_event_icon(event_type)
                    
                    # Get team color
                    team_id = event.get('team_id', 0)
                    team_color = "red" if team_id == 1 else "blue" if team_id == 2 else "gray"
                    
                    # Create description
                    if 'event_description' in event and pd.notnull(event['event_description']):
                        description = event['event_description']
                    else:
                        # Try to build a description from parts
                        entity = event.get('entity_name', 'Unknown')
                        target = event.get('target_name', '')
                        value = event.get('value', None)
                        
                        if event_type == 'kill':
                            description = f"{entity} killed {target}"
                        elif event_type == 'objective':
                            description = f"{entity} secured {target}"
                        elif event_type == 'structure':
                            description = f"{entity} destroyed {target}"
                        else:
                            description = f"{entity}: {event_type}"
                        
                        if value and pd.notnull(value) and value != '':
                            description += f" ({value})"
                    
                    # Display the event
                    cols = st.columns([1, 1, 10])
                    with cols[0]:
                        st.markdown(f"<span style='color:{team_color};'>{icon}</span>", unsafe_allow_html=True)
                    with cols[1]:
                        st.markdown(f"<span style='color:{team_color};'>{event_time}</span>", unsafe_allow_html=True)
                    with cols[2]:
                        st.markdown(f"<span style='color:{team_color};'>{description}</span>", unsafe_allow_html=True)
        else:
            st.warning("No key events found in the timeline.")
    else:
        st.warning("Timeline data is not available for this match.")
    
    # Footer
    st.markdown("---")
    st.markdown(
        "Developed for SMITE 2 Combat Log Analysis | &copy; 2025",
        unsafe_allow_html=True,
    )

if __name__ == "__main__":
    main() 