# SMITE 2 Combat Log Parser

A robust toolkit for parsing, processing, and analyzing SMITE 2 combat log files. This tool extracts rich game data and stores it in a SQLite database optimized for MOBA analytics and esports coaching.

![SMITE 2 Logo](https://example.com/smite2-logo.png)

## 🚀 Features

- **Advanced Parsing**: Process JSON-formatted combat log entries with robust error handling
- **Comprehensive Data Extraction**:
  - Player performance metrics (kills, deaths, assists, damage, healing)
  - Item purchases and build paths
  - Combat interactions between players and entities
  - Map positioning and movement data
  - Reward/economy tracking (gold, experience)
- **Optimized Database Storage**:
  - Well-structured SQLite database with proper relationships
  - Normalized schema for efficient queries
  - Support for multiple match analysis
  - Timeline event generation for match playback
- **Analytics Support**:
  - Accurate player statistics calculation
  - Team performance metrics
  - Combat pattern recognition
  - Item build efficiency analysis

## 📋 Recent Improvements

- **Assist Calculation**: Implemented a sophisticated system that tracks damage contributions to kills, awarding assists to players who dealt significant damage to victims shortly before their deaths
- **Kill Event Tracking**: Enhanced detection of both "Kill" and "KillingBlow" events for accurate timeline generation
- **Item Cost Extraction**: Fixed extraction of item costs from purchase events
- **Player Location Data**: Added default spawn locations when actual location data is missing
- **Match Metadata**: Improved extraction of match metadata including map name and match type

## 🛠️ Installation

```bash
# Clone the repository
git clone https://github.com/Entropicsky/S2CombatLogSQL.git
cd S2CombatLogSQL

# Set up a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -e .
```

## 📊 Usage

### Simple Loading (Recommended)

The easiest way to load combat log files is using the `load.py` script:

```bash
# Basic usage - automatically creates a database in ./data/
python load.py /path/to/CombatLog.log

# Specify output database location
python load.py /path/to/CombatLog.log -o my_database.db

# Load and verify the data was imported correctly
python load.py /path/to/CombatLog.log --verify

# Force reload even if match already exists
python load.py /path/to/CombatLog.log --force
```

### Advanced Reprocessing

For fixing data issues or reprocessing with advanced options, use `reprocess_data.py`:

```bash
# Reprocess a log file into a specific database
python reprocess_data.py /path/to/CombatLog.log /path/to/output.db
```

### Testing Parser Functionality

To verify the parser is working correctly:

```bash
# Run the test suite on a processed database
python test_parser_fixes.py /path/to/database.db

# This will check all tables, relationships, and calculated statistics
```

### Advanced CLI Usage

For more advanced use cases:

```bash
# Parse a combat log file with custom batch size
smite-parser parse /path/to/CombatLog.log --batch-size 5000

# Parse with custom options
smite-parser parse /path/to/CombatLog.log --output smite_matches.db --skip-malformed

# Show help and available commands
smite-parser --help
```

## 🔍 Analyzing the Data

### Example SQL Queries

After loading your combat log, you can perform rich analysis:

```sql
-- Basic player performance stats
SELECT player_name, team_id, kills, deaths, assists, damage_dealt, healing_done 
FROM player_stats 
ORDER BY team_id, damage_dealt DESC;

-- Timeline of kill events
SELECT event_time, entity_name, target_name, event_description 
FROM timeline_events 
WHERE event_type = 'Kill' 
ORDER BY event_time;

-- Item purchase progression
SELECT player_name, event_time, item_name, cost 
FROM item_events 
WHERE event_type = 'ItemPurchase' 
ORDER BY player_name, event_time;

-- Damage breakdown by ability
SELECT source_entity, ability_name, COUNT(*) as uses, 
       SUM(damage_amount) as total_damage,
       AVG(damage_amount) as avg_damage
FROM combat_events
WHERE event_type = 'Damage'
GROUP BY source_entity, ability_name
ORDER BY source_entity, total_damage DESC;
```

### Visualization Opportunities (Coming Soon)

- Player damage/healing timeline charts
- Kill location heatmaps
- Team fight analysis
- Economy advantage tracking
- Build path optimization

## 🔄 Data Processing Pipeline

The SMITE 2 Combat Log Parser processes data through a sophisticated pipeline:

### 1. Log File Reading
- Parses line-by-line JSON entries from combat log files
- Handles malformed entries and UTF-8 BOM markers
- Normalizes timestamps to a consistent datetime format

### 2. Metadata Collection
- Extracts match ID, start/end times, and map information
- Identifies player names, roles, and team assignments
- Catalogs all entities (players, NPCs, objectives, etc.)

### 3. Database Population
- Creates match, player, and entity records first to establish relationships
- Processes each event type with specialized transformers:
  - `transform_combat_event()`: Damage, healing, kills, crowd control
  - `transform_reward_event()`: Experience and gold acquisition
  - `transform_item_event()`: Item purchases and sales
  - `transform_player_event()`: Role assignments, god selection
- Uses batch processing for performance optimization

### 4. Derived Data Calculation
- Generates derived player statistics:
  - Kills, deaths, assists using sophisticated detection
  - Damage dealt/taken, healing performed
  - Gold and experience earned
- Creates timeline events for significant match moments
- Calculates match duration and performance metrics

### 5. Data Verification
- Validates database integrity and relationships
- Ensures all critical fields are populated
- Verifies statistical calculations match raw event data

### Parser Architecture

The parser is built on a modular architecture:

```
smite_parser/
├── __init__.py
├── config/
│   ├── __init__.py
│   └── config.py       # Configuration management
├── models.py           # SQLAlchemy ORM models
├── parser.py           # Core parser implementation
└── transformers.py     # Event transformation functions
```

- **Configuration Module**: Handles parser settings and options
- **Models Module**: Defines SQLAlchemy ORM models for the database
- **Transformers Module**: Contains functions to transform raw events to structured data
- **Parser Module**: Core implementation that reads and processes log files

## 📚 Database Schema

The database uses a comprehensive normalized schema with the following tables:

### Core Tables
- **matches**: Match metadata (ID, map, game type, duration)
- **players**: Player information (name, team, role, god)
- **entities**: All entities in the game (players, NPCs, structures)

### Event Tables
- **combat_events**: Combat interactions (damage, healing, kills)
- **reward_events**: Reward acquisitions (gold, experience)
- **item_events**: Item transactions (purchases, sales)
- **player_events**: Player-specific events (role assignments, god selection)

### Derived Tables
- **player_stats**: Calculated statistics for each player
- **timeline_events**: Key events for match timeline visualization
- **abilities**: Abilities used in the match
- **items**: Items used in the match

### Schema Details

Below are simplified SQL definitions for the main tables:

```sql
-- Match information
CREATE TABLE matches (
    match_id TEXT PRIMARY KEY,
    source_file TEXT,
    map_name TEXT,
    game_type TEXT,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration_seconds INTEGER,
    match_data TEXT
);

-- Player information
CREATE TABLE players (
    player_id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT,
    player_name TEXT,
    team_id INTEGER,
    role TEXT,
    god_id INTEGER,
    god_name TEXT,
    FOREIGN KEY (match_id) REFERENCES matches (match_id)
);

-- Player statistics
CREATE TABLE player_stats (
    stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT,
    player_name TEXT,
    team_id INTEGER,
    kills INTEGER,
    deaths INTEGER,
    assists INTEGER,
    damage_dealt INTEGER,
    damage_taken INTEGER,
    healing_done INTEGER,
    gold_earned INTEGER,
    experience_earned INTEGER,
    cc_time_inflicted INTEGER,
    FOREIGN KEY (match_id) REFERENCES matches (match_id)
);

-- Combat events
CREATE TABLE combat_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT,
    event_time TIMESTAMP,
    timestamp TIMESTAMP,
    event_type TEXT,
    source_entity TEXT,
    target_entity TEXT,
    ability_name TEXT,
    location_x REAL,
    location_y REAL,
    damage_amount INTEGER,
    damage_mitigated INTEGER,
    event_text TEXT,
    FOREIGN KEY (match_id) REFERENCES matches (match_id)
);

-- Timeline events
CREATE TABLE timeline_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT,
    event_time TIMESTAMP,
    timestamp TIMESTAMP,
    event_type TEXT,
    event_description TEXT,
    entity_name TEXT,
    target_name TEXT,
    location_x REAL,
    location_y REAL,
    event_details TEXT,
    FOREIGN KEY (match_id) REFERENCES matches (match_id)
);
```

For a complete schema diagram and detailed field descriptions, see the technical specification in the `agent_notes/technical_spec.md` file.

## 🧪 Testing

The project includes comprehensive testing:

```bash
# Run the basic test suite
pytest

# Run tests with coverage report
pytest --cov=smite_parser tests/

# Test data integrity on a specific database
python test_parser_fixes.py path/to/database.db
```

## 📋 Requirements

- Python 3.8+
- SQLite 3
- Packages: sqlalchemy, tqdm, pytest (for testing)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create a feature branch: `git checkout -b my-new-feature`
3. Commit your changes: `git commit -am 'Add some feature'`
4. Push to the branch: `git push origin my-new-feature`
5. Submit a pull request

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details. 