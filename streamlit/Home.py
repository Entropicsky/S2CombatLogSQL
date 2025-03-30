import os
import sys
import subprocess
import tempfile
import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path
import time

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set the page configuration
st.set_page_config(
    page_title="SMITE 2 Combat Log Analyzer",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
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
    .success-box {
        padding: 15px;
        border-radius: 5px;
        background-color: #DFF2BF;
        color: #4F8A10;
        margin-bottom: 20px;
    }
    .info-box {
        padding: 15px;
        border-radius: 5px;
        background-color: #BDE5F8;
        color: #00529B;
        margin-bottom: 20px;
    }
    .error-box {
        padding: 15px;
        border-radius: 5px;
        background-color: #FFD2D2;
        color: #D8000C;
        margin-bottom: 20px;
    }
    .st-emotion-cache-16txtl3 {
        padding: 3rem 1rem;
    }
</style>
""", unsafe_allow_html=True)

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

def process_combat_log(log_file, skip_excel=False):
    """Process the uploaded combat log file using the parser."""
    # Save the uploaded file to a temporary location
    with tempfile.NamedTemporaryFile(delete=False, suffix='.log') as temp_file:
        temp_file.write(log_file.getvalue())
        temp_file_path = temp_file.name
    
    try:
        # Determine the database filename from the uploaded file name and add timestamp to make it unique
        timestamp = int(time.time())
        file_base = log_file.name.split('.')[0]
        db_name = f"{file_base}_{timestamp}.db"
        db_path = os.path.join("data", db_name)
        absolute_db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', db_name))
        
        # Create data directory if it doesn't exist
        data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
        os.makedirs(data_dir, exist_ok=True)
        
        # Get the absolute path to the root directory and load.py
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        load_script_path = os.path.join(root_dir, "load.py")
        
        # Verify that the script exists
        if not os.path.exists(load_script_path):
            st.error(f"Error: The load script was not found at {load_script_path}")
            return False, None
        
        # Display debug information
        st.info(f"""
        Debug information:
        - Temp file: {temp_file_path}
        - DB path: {absolute_db_path}
        - Load script: {load_script_path}
        - Working directory: {root_dir}
        """)
        
        # Build the command for the subprocess
        cmd = [sys.executable, load_script_path, temp_file_path, "-o", absolute_db_path, "--force", "--verify"]
        
        if skip_excel:
            cmd.append("--no-excel")
        
        # Display the command
        st.code(" ".join(cmd), language="bash")
        
        # Create a placeholder for real-time output
        output_placeholder = st.empty()
        
        # Run the command with real-time output
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=root_dir,  # Set the working directory to the project root
        )
        
        # Display output in real-time
        output_text = ""
        for line in iter(process.stdout.readline, ''):
            output_text += line
            output_placeholder.text(output_text)
        
        # Wait for the process to complete
        return_code = process.wait()
        
        # Clean up the temporary file
        os.unlink(temp_file_path)
        
        # Verify database was created and has data
        if return_code == 0:
            # Check if database exists
            if os.path.exists(absolute_db_path):
                if os.path.getsize(absolute_db_path) > 0:
                    # Check if the database has the required tables
                    conn = sqlite3.connect(absolute_db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [row[0] for row in cursor.fetchall()]
                    conn.close()
                    
                    required_tables = ['matches', 'players', 'combat_events']
                    missing_tables = [table for table in required_tables if table not in tables]
                    
                    if missing_tables:
                        st.error(f"Database was created but is missing required tables: {', '.join(missing_tables)}")
                        return False, None
                    
                    # If there's an Excel export error in the output but the database was created successfully,
                    # we still consider this a success
                    if "Failed to export to Excel" in output_text:
                        st.warning("Database was created successfully but Excel export failed. This won't affect analysis.")
                    
                    # After database is created, ensure it has all required columns
                    ensure_database_schema(absolute_db_path)
                    
                    # Return the absolute path to ensure it's correctly located
                    return True, absolute_db_path
                else:
                    st.error(f"Database file was created but is empty: {absolute_db_path}")
                    return False, None
            else:
                st.error(f"Database file was not created at expected location: {absolute_db_path}")
                return False, None
        else:
            st.error(f"Process returned error code: {return_code}")
            return False, None
    
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        # Clean up the temporary file
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        return False, None

def get_existing_databases():
    """Get a list of existing database files."""
    data_dir = Path("data")
    if not data_dir.exists():
        return []
    
    return sorted([f for f in data_dir.glob("*.db")], key=os.path.getmtime, reverse=True)

def get_database_info(db_path):
    """Get basic information about the database."""
    try:
        # Make sure we're using an absolute path
        db_path = os.path.abspath(db_path)
        
        # Check if the file exists
        if not os.path.exists(db_path):
            st.error(f"Database file does not exist: {db_path}")
            return None
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if the database has the required tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        st.info(f"Database tables: {', '.join(tables)}")
        
        required_tables = ['matches', 'players', 'combat_events', 'reward_events', 'item_events']
        missing_tables = [table for table in required_tables if table not in tables]
        
        if missing_tables:
            st.warning(f"Database is missing some tables: {', '.join(missing_tables)}. This might affect some analyses.")
        
        # Get match information
        if 'matches' in tables:
            try:
                cursor.execute("SELECT match_id, source_file, map_name, duration_seconds FROM matches LIMIT 1")
                match_info = cursor.fetchone()
                
                # If no match info was found, the database might be empty
                if not match_info:
                    st.error("No match data found in the database.")
                    conn.close()
                    return None
            except sqlite3.OperationalError as e:
                # If we can't get all columns, try with a simpler query
                st.warning(f"Some match columns are missing: {str(e)}. Continuing with partial data.")
                cursor.execute("SELECT match_id FROM matches LIMIT 1")
                match_id = cursor.fetchone()
                if match_id:
                    match_info = (match_id[0], "Unknown", "Unknown", 0)
                else:
                    st.error("No match data found in the database.")
                    conn.close()
                    return None
        else:
            st.error("Matches table not found in database.")
            conn.close()
            return None
        
        # Get player count
        player_count = 0
        if 'players' in tables:
            cursor.execute("SELECT COUNT(*) FROM players")
            player_count = cursor.fetchone()[0]
        
        # Get event counts
        combat_events = 0
        if 'combat_events' in tables:
            cursor.execute("SELECT COUNT(*) FROM combat_events")
            combat_events = cursor.fetchone()[0]
        
        reward_events = 0
        if 'reward_events' in tables:
            cursor.execute("SELECT COUNT(*) FROM reward_events")
            reward_events = cursor.fetchone()[0]
        
        item_events = 0
        if 'item_events' in tables:
            cursor.execute("SELECT COUNT(*) FROM item_events")
            item_events = cursor.fetchone()[0]
        
        # Get team information
        team_info = []
        if 'players' in tables:
            try:
                cursor.execute("""
                    SELECT team_id, COUNT(*) 
                    FROM players 
                    GROUP BY team_id
                """)
                team_info = cursor.fetchall()
            except sqlite3.OperationalError:
                # If there's no team_id column
                st.warning("Could not retrieve team information. This might affect team analysis.")
        
        conn.close()
        
        return {
            "match_id": match_info[0] if match_info else None,
            "source_file": match_info[1] if match_info else None,
            "map_name": match_info[2] if match_info else None,
            "duration": match_info[3] if match_info else None,
            "player_count": player_count,
            "combat_events": combat_events,
            "reward_events": reward_events,
            "item_events": item_events,
            "team_info": team_info
        }
    except sqlite3.OperationalError as e:
        st.error(f"Database error: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Error getting database information: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return None

def display_database_info(db_info):
    """Display database information in a nice format."""
    if not db_info:
        return
    
    # Format duration as MM:SS
    duration_minutes = db_info["duration"] // 60 if db_info["duration"] else 0
    duration_seconds = db_info["duration"] % 60 if db_info["duration"] else 0
    duration_str = f"{duration_minutes:02d}:{duration_seconds:02d}"
    
    # Create two columns for the layout
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Match Information")
        st.markdown(f"**Match ID:** {db_info['match_id']}")
        st.markdown(f"**Map:** {db_info['map_name']}")
        st.markdown(f"**Duration:** {duration_str}")
        
        st.markdown("#### Teams")
        for team_id, count in db_info["team_info"]:
            st.markdown(f"**Team {team_id}:** {count} players")
    
    with col2:
        st.markdown("#### Event Counts")
        st.markdown(f"**Players:** {db_info['player_count']}")
        st.markdown(f"**Combat Events:** {db_info['combat_events']:,}")
        st.markdown(f"**Reward Events:** {db_info['reward_events']:,}")
        st.markdown(f"**Item Events:** {db_info['item_events']:,}")
        
        st.markdown("#### Source")
        st.markdown(f"**File:** {db_info['source_file']}")

def main():
    # Header
    st.markdown("<div class='main-header'>SMITE 2 Combat Log Analyzer</div>", unsafe_allow_html=True)
    st.markdown(
        "Upload SMITE 2 combat log files, analyze match data, and explore player performance."
    )
    st.markdown("---")
    
    # Create tabs
    tab1, tab2 = st.tabs(["Upload", "Existing Databases"])
    
    with tab1:
        st.markdown("<div class='sub-header'>Upload Combat Log</div>", unsafe_allow_html=True)
        
        # File uploader
        uploaded_file = st.file_uploader("Choose a SMITE 2 combat log file", type=["log"])
        
        # Processing options
        col1, col2 = st.columns(2)
        with col1:
            st.info("Each upload creates a new database with a unique name")
        with col2:
            skip_excel = st.checkbox("Skip Excel export", value=False)
        
        # Process the file when a button is clicked
        if uploaded_file is not None:
            if st.button("Process Combat Log"):
                with st.spinner('Processing combat log...'):
                    success, db_path = process_combat_log(
                        uploaded_file, 
                        skip_excel=skip_excel
                    )
                    
                    if success:
                        st.markdown(
                            f"<div class='success-box'>✅ Successfully processed {uploaded_file.name}</div>", 
                            unsafe_allow_html=True
                        )
                        
                        # Get database information
                        db_info = get_database_info(db_path)
                        if db_info:
                            display_database_info(db_info)
                            
                            # Add links to analysis pages
                            st.markdown("### Analyze Match")
                            
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.button("Match Summary", 
                                          on_click=lambda: st.session_state.update({
                                              'selected_db': db_path,
                                              'page': 'Match_Summary'
                                          }))
                            with col2:
                                st.button("Economy Analysis", 
                                          on_click=lambda: st.session_state.update({
                                              'selected_db': db_path,
                                              'page': 'Economy_Analysis'
                                          }))
                            with col3:
                                st.button("Combat Analysis", 
                                          on_click=lambda: st.session_state.update({
                                              'selected_db': db_path,
                                              'page': 'Combat_Analysis'
                                          }))
                            
                            # Store the current database in session state
                            st.session_state['selected_db'] = db_path
                    else:
                        st.markdown(
                            f"<div class='error-box'>❌ Failed to process {uploaded_file.name}</div>", 
                            unsafe_allow_html=True
                        )
    
    with tab2:
        st.markdown("<div class='sub-header'>Existing Databases</div>", unsafe_allow_html=True)
        
        # Get list of existing databases
        databases = get_existing_databases()
        
        if not databases:
            st.markdown("<div class='info-box'>No database files found. Upload a combat log file to create one.</div>", unsafe_allow_html=True)
        else:
            # Create a selectbox for choosing a database
            selected_db = st.selectbox(
                "Select a database to view:",
                options=databases,
                format_func=lambda x: x.name
            )
            
            if selected_db:
                # Get info for the selected database
                db_info = get_database_info(selected_db)
                if db_info:
                    display_database_info(db_info)
                    
                    # Add links to analysis pages
                    st.markdown("### Analyze Match")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.button("Match Summary", key="existing_match_summary", 
                                  on_click=lambda: st.session_state.update({
                                      'selected_db': str(selected_db),
                                      'page': 'Match_Summary'
                                  }))
                    with col2:
                        st.button("Economy Analysis", key="existing_economy_analysis", 
                                  on_click=lambda: st.session_state.update({
                                      'selected_db': str(selected_db),
                                      'page': 'Economy_Analysis'
                                  }))
                    with col3:
                        st.button("Combat Analysis", key="existing_combat_analysis", 
                                  on_click=lambda: st.session_state.update({
                                      'selected_db': str(selected_db),
                                      'page': 'Combat_Analysis'
                                  }))
                    
                    # Store the current database in session state
                    st.session_state['selected_db'] = str(selected_db)

    # Footer
    st.markdown("---")
    st.markdown(
        "Developed for SMITE 2 Combat Log Analysis | &copy; 2025",
        unsafe_allow_html=True,
    )

# Initialize session state if not already
if 'selected_db' not in st.session_state:
    st.session_state['selected_db'] = None

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
    """)
    
    # Add test data
    cursor.execute("INSERT INTO matches VALUES ('test_match', 'test.log', 'Test Map', 1200)")
    
    conn.commit()
    
    # Test the table info query
    print("Testing table info query...")
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        print("✅ Table info query passed")
    except sqlite3.Error as e:
        print(f"❌ Table info query failed: {e}")
    
    # Test the player_stats table column query
    print("\nTesting player_stats column info query...")
    try:
        cursor.execute("PRAGMA table_info(player_stats)")
        print("✅ Player stats column info query passed")
    except sqlite3.Error as e:
        print(f"❌ Player stats column info query failed: {e}")
    
    # Test adding a column
    print("\nTesting ALTER TABLE query...")
    try:
        cursor.execute("ALTER TABLE player_stats ADD COLUMN test_column INTEGER DEFAULT 0")
        print("✅ ALTER TABLE query passed")
    except sqlite3.Error as e:
        print(f"❌ ALTER TABLE query failed: {e}")
    
    conn.close()
    print("\nAll query tests completed.")

if __name__ == "__main__":
    main() 