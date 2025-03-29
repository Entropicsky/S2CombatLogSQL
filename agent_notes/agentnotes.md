# Agent Notes: SMITE 2 Combat Log Parser

## Project Overview

This project is creating a parser for SMITE 2 Combat Log files that extracts data and stores it in a SQLite database for analysis. The parser handles different event types from the combat log and transforms them into a structured database format.

## Recent Improvements

We've made several significant improvements to the combat log parser:

1. **Assist Calculation**: Implemented a more accurate assist calculation system in `_calculate_player_stats` that tracks damage contributions to kills. Assists are now awarded to players who dealt significant damage to a victim shortly before their death.

2. **KillingBlow Events**: Updated the parser to properly account for both "Kill" and "KillingBlow" events when generating timeline events and calculating player statistics.

3. **Item Cost Extraction**: Fixed item cost extraction from purchase events.

4. **Player Location Data**: Added default spawn locations when actual location data is missing in player events:
   - Order team (1): (-10500.0, 0.0)
   - Chaos team (2): (10500.0, 0.0)

5. **Match Metadata**: Implemented extraction of match metadata from log files.

## Project Structure

- `smite_parser/` - Main package directory
  - `__init__.py` - Package initialization
  - `config/` - Configuration management
    - `__init__.py`
    - `config.py` - Configuration implementation
  - `models.py` - SQLAlchemy ORM models for database
  - `transformers.py` - Data transformation functions
  - `parser.py` - Core parser implementation
  - `cli.py` - Command-line interface
- `tests/` - Test directory
  - `__init__.py`
  - `conftest.py` - Test fixtures
  - `test_models.py` - Tests for database models
  - `test_transformers.py` - Tests for data transformation
  - `test_parser.py` - Tests for parser functionality
- `agent_notes/` - Documentation for agents
  - `project_checklist.md` - Project progress tracking
  - `agentnotes.md` - This file
  - `notebook.md` - Interesting findings and notes
  - `technical_spec.md` - Technical specifications

## Project Approach

The parser is implemented with a modular architecture that separates concerns:

1. **Configuration Module**: Handles parser settings and options
2. **Models Module**: Defines SQLAlchemy ORM models for the database
3. **Transformers Module**: Contains functions to transform raw events into model instances
4. **Parser Module**: Core implementation that reads log files and processes events
5. **CLI Module**: Command-line interface for user interaction

## Implementation Details

### Parser Design

The parser follows these key processing steps:

1. **File Reading**: Reads and parses the JSON lines in combat log files
2. **Metadata Collection**: Extracts match ID, player names, timestamps and other metadata
3. **Entity Processing**: Creates records for players and other entities
4. **Event Processing**: Processes events in batches for efficient database insertion
5. **Derived Data Generation**: Calculates statistics and generates timeline events

### Data Transformation

Each event type has a specialized transformer function:

- `transform_combat_event()`: Processes combat events (damage, healing, kills)
- `transform_reward_event()`: Processes reward events (gold, experience, objectives)
- `transform_item_event()`: Processes item events (purchases, sales)
- `transform_player_event()`: Processes player events (role assignments, level ups)

### Database Design

The database schema includes these key tables:

- **Match**: Information about each match
- **Player**: Player information and attributes
- **Entity**: All entities in the game (players, NPCs, structures)
- **CombatEvent**: Combat interactions (damage, healing, kills)
- **RewardEvent**: Reward acquisitions (gold, experience)
- **ItemEvent**: Item transactions (purchases, sales)
- **PlayerEvent**: Player-specific events
- **PlayerStat**: Aggregated statistics for each player
- **TimelineEvent**: Key events for match timeline visualization

## Testing Strategy

Testing is implemented with pytest and includes:

1. **Unit Tests**: For individual components (transformers, models)
2. **Functional Tests**: For parser functionality
3. **Integration Tests**: For database operations
4. **End-to-End Tests**: For complete parser pipeline

Test fixtures provide sample data for testing, including mock combat log entries.

## Current Status

The implementation is progressing well:

- [x] Configuration module complete
- [x] SQLAlchemy models defined
- [x] Data transformation functions implemented
- [x] Core parser functionality implemented
- [x] CLI interface created
- [x] Unit tests for transformers and models
- [x] Parser tests created
- [ ] Integration tests
- [ ] End-to-end tests
- [ ] Documentation
- [ ] Packaging

See `project_checklist.md` for detailed progress tracking.

## Future Directions

After completing the current implementation:

1. Add advanced statistics calculations
2. Create visualization tools for match analysis
3. Implement match comparison functionality
4. Add export options for different formats
5. Create a web interface for browsing match data

## Key Files
- `CombatLogExample.log` - Sample combat log file from SMITE 2
- `agent_notes/` - Folder containing project documentation
  - `project_checklist.md` - Tracks progress on the project tasks
  - `notebook.md` - Contains observations and insights about the data
  - `agentnotes.md` - This file, with critical project information
  - `technical_spec.md` - Technical specification for the database schema (in progress)
- `data_explore/` - Scripts used for data exploration

## Project Goals
1. Parse combat log files from SMITE 2
2. Clean and normalize the data for database storage
3. Create a well-structured SQLite database that supports:
   - Multiple match files
   - MOBA analytics queries
   - Timeline data
   - Player performance metrics
   - Map/location data for heat maps

## Data Structure
Combat logs contain JSON-formatted events with these main types:
- `start` - Match initialization
- `playermsg` - Player actions (god selection, role assignments)
- `itemmsg` - Item purchases
- `CombatMsg` - Combat actions (damage, healing, CC, kills)
- `RewardMsg` - Experience and currency rewards

Each event type has multiple subtypes and varying field structures.

## Development Status
Currently in Phase 2 (Database Design). Initial data exploration complete, working on technical specification for the database schema.

## Next Steps
1. Complete the technical specification
2. Review the spec with the user
3. Implement the parser and database creation scripts

## Notes to Self
- Remember to convert all string values to appropriate data types
- Handle match ID generation/tracking for multiple files
- Pay attention to team identification in the value1 field
- Consider performance optimizations for the large volume of combat events
- Build the database to support the analytics a MOBA esports coach would need 