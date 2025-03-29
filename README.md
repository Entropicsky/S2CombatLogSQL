# SMITE 2 Combat Log Parser

A tool to parse SMITE 2 combat log files and store them in a SQLite database optimized for MOBA analytics.

## Features

- Parses JSON-formatted combat log entries from SMITE 2
- Normalizes and cleans data for robust analysis
- Stores data in a well-structured SQLite database
- Supports multiple match files
- Enables comprehensive game analysis
- Optimized for common MOBA analytics queries

## Installation

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

## Usage

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

### Advanced Usage

For more advanced use cases, you can use the CLI:

```bash
# Parse a combat log file
smite-parser parse /path/to/CombatLog.log

# Parse a combat log file with a specific output database
smite-parser parse /path/to/CombatLog.log --output smite_matches.db

# Show help
smite-parser --help
```

## Querying the Database

After loading your combat log, you can query the database using SQLite:

```bash
# Open the database
sqlite3 data/CombatLog.db

# Some example queries:
sqlite> SELECT * FROM matches;
sqlite> SELECT player_name, kills, deaths, assists FROM player_stats;
sqlite> SELECT * FROM timeline_events ORDER BY event_time;
```

## Database Schema

The database uses a normalized schema with tables for:

- Match information
- Player details
- Combat events (damage, healing, crowd control, kills)
- Reward events (experience, currency)
- Item purchases
- Player-specific events (role assignments, god selection)
- Derived statistics for analysis
- Timeline events for key match moments

For detailed schema information, see the technical specification in the `agent_notes` folder.

## Requirements

- Python 3.8+
- SQLite 3

## License

MIT 