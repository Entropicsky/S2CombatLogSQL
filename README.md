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
git clone https://github.com/username/smite_parser.git
cd smite_parser

# Install the package
pip install -e .
```

## Usage

```bash
# Parse a combat log file
smite-parser parse /path/to/CombatLog.log

# Parse a combat log file with a specific output database
smite-parser parse /path/to/CombatLog.log --output smite_matches.db

# Show help
smite-parser --help
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

For detailed schema information, see the technical specification in the `agent_notes` folder.

## Requirements

- Python 3.8+
- SQLite 3

## License

MIT 