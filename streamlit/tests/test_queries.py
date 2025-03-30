import os
import sys
import re
import sqlite3
import importlib.util
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parents[2]))

def load_module(file_path):
    """Load a Python module from file path."""
    spec = importlib.util.spec_from_file_location("module.name", file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def extract_sql_queries(file_content):
    """Extract SQL queries from file content."""
    # Look for pd.read_sql_query or cursor.execute patterns
    query_patterns = [
        r'pd\.read_sql_query\(\s*"""(.*?)"""',
        r'pd\.read_sql_query\(\s*f"""(.*?)"""',
        r'cursor\.execute\(\s*"""(.*?)"""',
        r'cursor\.execute\(\s*f"""(.*?)"""',
        r'cursor\.execute\(\s*"(.*?)"',
        r'cursor\.execute\(\s*f"(.*?)"',
    ]
    
    queries = []
    for pattern in query_patterns:
        matches = re.findall(pattern, file_content, re.DOTALL)
        queries.extend(matches)
    
    return queries

def create_test_db():
    """Create a test database with the expected schema."""
    db_path = ":memory:"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create all the tables with their expected schemas
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS matches (
        match_id TEXT PRIMARY KEY,
        source_file TEXT NOT NULL,
        map_name TEXT,
        game_type TEXT,
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        duration_seconds INTEGER,
        match_data TEXT
    );
    
    CREATE TABLE IF NOT EXISTS players (
        player_id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id TEXT,
        player_name TEXT NOT NULL,
        team_id INTEGER,
        role TEXT,
        god_id INTEGER,
        god_name TEXT
    );
    
    CREATE TABLE IF NOT EXISTS player_stats (
        stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id TEXT,
        event_time TIMESTAMP NOT NULL,
        timestamp TIMESTAMP,
        game_time_seconds INTEGER,
        event_type TEXT NOT NULL,
        event_category TEXT,
        importance INTEGER,
        event_description TEXT,
        entity_name TEXT,
        target_name TEXT,
        team_id INTEGER,
        location_x REAL,
        location_y REAL,
        value INTEGER,
        related_event_id INTEGER,
        other_entities TEXT,
        event_details TEXT
    );
    """)
    
    # Insert sample data
    cursor.execute("INSERT INTO matches (match_id, source_file, map_name, duration_seconds) VALUES ('test_match', 'test.log', 'Test Map', 1200)")
    
    cursor.execute("INSERT INTO players (match_id, player_name, team_id, role, god_name) VALUES ('test_match', 'Player1', 1, 'Mid', 'Zeus')")
    cursor.execute("INSERT INTO players (match_id, player_name, team_id, role, god_name) VALUES ('test_match', 'Player2', 2, 'Solo', 'Hades')")
    
    cursor.execute("""
        INSERT INTO player_stats (match_id, player_name, team_id, kills, deaths, assists, damage_dealt, damage_taken, 
                                 healing_done, damage_mitigated, gold_earned, experience_earned, cc_time_inflicted, structure_damage)
        VALUES ('test_match', 'Player1', 1, 5, 2, 3, 10000, 5000, 1000, 2000, 8000, 9000, 20, 1500)
    """)
    cursor.execute("""
        INSERT INTO player_stats (match_id, player_name, team_id, kills, deaths, assists, damage_dealt, damage_taken, 
                                 healing_done, damage_mitigated, gold_earned, experience_earned, cc_time_inflicted, structure_damage)
        VALUES ('test_match', 'Player2', 2, 2, 5, 4, 8000, 10000, 500, 3000, 7000, 8000, 15, 500)
    """)
    
    cursor.execute("""
        INSERT INTO timeline_events (match_id, event_time, game_time_seconds, event_type, event_category, 
                                    importance, entity_name, target_name, team_id)
        VALUES ('test_match', '2025-01-01 12:00:00', 120, 'Kill', 'Combat', 8, 'Player1', 'Player2', 1)
    """)
    
    conn.commit()
    return conn

def validate_query(conn, query, parameters=None):
    """Try to execute a query and return any errors."""
    try:
        cursor = conn.cursor()
        # Replace placeholders with test values
        test_query = query.replace('?', "'test'").replace('%s', "'test'")
        cursor.execute(test_query, parameters or [])
        cursor.fetchall()  # Consume the results
        return None
    except sqlite3.Error as e:
        return str(e)

def test_streamlit_queries():
    """Test all queries in the Streamlit application."""
    conn = create_test_db()
    print("Created test database with sample schema and data")
    
    # Get all Python files in the streamlit directory
    streamlit_dir = Path(__file__).parents[1]
    py_files = list(streamlit_dir.glob('**/*.py'))
    py_files = [f for f in py_files if 'tests' not in str(f)]
    
    errors = []
    
    for file_path in py_files:
        print(f"\nTesting queries in {file_path}")
        with open(file_path, 'r') as f:
            file_content = f.read()
        
        queries = extract_sql_queries(file_content)
        
        for i, query in enumerate(queries):
            # Basic variable replacement for f-strings
            # This is a simplified approach and won't handle complex cases
            query = query.replace('{', '').replace('}', '')
            
            print(f"  Testing query {i+1}...")
            error = validate_query(conn, query)
            if error:
                errors.append({
                    'file': file_path.name,
                    'query': query,
                    'error': error
                })
                print(f"  ❌ Error: {error}")
            else:
                print(f"  ✅ Query passed")
    
    conn.close()
    
    if errors:
        print("\n🚨 Found errors in SQL queries:")
        for i, error in enumerate(errors):
            print(f"\n{i+1}. File: {error['file']}")
            print(f"   Query: {error['query'][:100]}...")
            print(f"   Error: {error['error']}")
        print(f"\nTotal errors: {len(errors)}")
        return False
    else:
        print("\n✅ All queries are valid!")
        return True

if __name__ == "__main__":
    print("Testing SQL queries in Streamlit application")
    success = test_streamlit_queries()
    sys.exit(0 if success else 1) 