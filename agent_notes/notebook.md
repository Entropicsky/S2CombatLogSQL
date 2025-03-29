# Combat Log Analysis Notebook

## Data Insights

### Event Types and Frequencies
- **CombatMsg**: 24,253 entries - Combat-related events (damage, healing, crowd control, kills)
- **RewardMsg**: 4,654 entries - Experience and currency rewards
- **itemmsg**: 247 entries - Item purchases
- **playermsg**: 39 entries - Player actions (god selection, role assignments)
- **start**: 1 entry - Match initialization

### Field Structure Analysis
- All fields are stored as strings in the JSON, requiring type conversion
- Common fields across events: eventType, type, itemid, itemname, time, sourceowner
- Combat events include: targetowner, locationx, locationy, value1, value2
- Timestamps are in format: YYYY.MM.DD-HH.MM.SS

### Match Details
- **Duration**: 31 minutes, 42 seconds (from 03:38:15 to 04:09:57)
- **Players**: 10 players total (two teams of 5)
- **Map Coordinates**: Range from approximately -11,000 to 11,000 on both axes

### Value Ranges
- **Damage**: 0-797 (avg: 61.58)
- **Healing**: 0-433 (avg: 10.75)
- **Experience**: 0-1,260 (avg: 63.88)
- **Currency**: 1-604 (avg: 29.56)

### Game Elements
- **Items**: 88 unique items identified
- **Abilities**: 82 unique abilities tracked
- **NPCs/Monsters**: Multiple types including minions, jungle camps, objectives

## Observations for Database Design

1. Need to track match ID for supporting multiple match files
2. Player names should be normalized into a players table
3. Items and abilities should be normalized into lookup tables
4. Location data provides opportunity for heatmapping analysis
5. Combat events are the most voluminous and will need optimized storage
6. Timestamps should be converted to proper datetime format
7. Numeric values (damage, healing, currency, etc.) should be stored as integers
8. Text field often contains human-readable descriptions that can be parsed for additional data
9. Need to handle team identification (seems to be in value1 field: 1 or 2)
10. itemid field appears to be a unique identifier for gods, items, abilities

## Questions for Further Investigation

- What additional metadata might be useful to capture about each match?
- How to best structure queries for common MOBA analytics (KDA, gold/min, etc.)?
- Are there additional data points that could be inferred from existing data?

# Project Notebook: SMITE 2 Combat Log Parser

## Parser Implementation Notes

### Design Decisions

- **Modular Architecture**: Split the parser into distinct modules (config, models, transformers, parser, cli) for better maintainability and testability.

- **Event Type Processing**: Implemented specialized transformer functions for each event type rather than a generic approach to handle the specific nuances of each event type.

- **Batch Processing**: Using batch inserts for database operations significantly improves performance when parsing large log files.

- **SQLAlchemy ORM**: Using SQLAlchemy provides a clean abstraction over SQL operations and handles the database connection management.

- **Defensive Parsing**: Implemented robust error handling to deal with malformed events and inconsistent formatting in log files.

- **Sequential Processing**: The parser processes events in a specific sequence (metadata -> entities -> events -> derived data) to ensure proper relationships.

### Implementation Challenges

1. **Timestamp Parsing**: Combat logs may have timestamps in different formats (ISO format in newer logs, custom format in older logs). The parser needs to handle both formats.

2. **Inconsistent Field Names**: Different event types and versions use inconsistent field names for the same data (e.g., "source" vs "sourceowner" for the entity initiating an action).

3. **Type Conversion**: Many fields need careful type conversion, as they may be strings in the log but should be numeric in the database.

4. **Missing Data**: Not all events contain all fields, so the parser must handle missing data gracefully.

5. **Batch Size Tuning**: Finding the optimal batch size for database operations requires careful tuning based on log size and available memory.

### Performance Considerations

- **Memory Usage**: For large log files, memory usage can become significant. The parser processes events in batches to manage memory consumption.

- **Database Transactions**: Wrapping multiple inserts in a single transaction significantly improves database write performance.

- **Index Creation Timing**: Creating indexes after data insertion is faster than having them active during insertion.

- **Connection Pooling**: For future improvements, implementing connection pooling could help with concurrent parsing.

### Code Organization Insights

- **Config Management**: Using a dedicated config class with validation ensures the parser is correctly configured.

- **Transformers**: Each transformer function is focused on a single event type, making the code more maintainable and testable.

- **Parser Logic**: The main parser class orchestrates the process but delegates specific transformations to dedicated functions.

- **Database Models**: Clear separation between different event types in the database schema makes queries more efficient.

## Testing Observations

- **Test Data Generation**: Creating realistic test data is important for effective testing of the parser.

- **Fixture Reuse**: Using pytest fixtures allows test data to be reused across multiple tests.

- **Temporary Database**: Using a temporary SQLite database for tests ensures isolation between test runs.

- **Edge Case Testing**: Special attention is needed for testing edge cases like malformed events, missing fields, and invalid data.

## Future Improvement Ideas

- **Async Processing**: Implement asynchronous processing for handling multiple log files concurrently.

- **Progress Reporting**: Add more detailed progress reporting for long-running parsing operations.

- **Data Validation**: Add more validation rules for incoming data to catch potential issues earlier.

- **Caching**: Implement caching for frequently accessed reference data to improve performance.

- **Query Optimization**: Create optimized query methods for common analysis patterns.

- **Incremental Updates**: Add support for incrementally updating the database with new log files without duplicating data.

## Timestamp Parsing Fix (Mar 29, 2025)

We identified and fixed an issue with the timestamp parsing in the `parse_timestamp` function. 
The log files contain timestamps in the format `2025.03.19-04.09.28` (using dots as separators), 
but the parser wasn't correctly handling this format.

The solution involved:
1. Simplifying the `parse_timestamp` function
2. Explicitly defining the timestamp formats to try:
   - `%Y.%m.%d-%H.%M.%S` format with dots: 2025.03.19-04.09.28
   - `%Y-%m-%d-%H:%M:%S` format with dashes and colons: 2025-03-19-04:09:28
3. Proper error handling and logging

After the fix, we successfully parsed the log file without any timestamp parsing errors, 
and confirmed that all events were properly recorded:
- 24,253 combat events
- 4,654 reward events
- 247 item events
- 39 player events

The match duration was from 03:38:15 to 04:09:57 on 2025-03-19.

## Database Field Inconsistency Fixes (Mar 29, 2025)

We identified and fixed inconsistencies in how event fields were being populated in the database:

1. **NULL values issue**: Several important fields were null in the event tables:
   - `match_id` - Not being set in transformer functions
   - `timestamp` - Only being set in combat events, but not in reward, item, or player events
   - `location_x` and `location_y` - Not being extracted from the raw event data

2. **Timestamp vs. event_time confusion**: We found inconsistent use of these fields:
   - Some transformers set only `event_time`
   - Some functions expected `timestamp`
   - Timeline generation had missing fields in some cases

These issues were fixed by:
1. Updating all transformer functions to consistently set both `timestamp` and `event_time` fields
2. Explicitly extracting and setting location data (x,y) in all transformers
3. Ensuring `match_id` is set in all event processors
4. Making timeline event generation consistent

Additionally, we created comprehensive tests to ensure these fields are properly populated in the future.

# Development Notes

## Fixed Issues

### Assist Calculation
- Implemented a more accurate assist calculation system that properly tracks player contributions to kills
- The system now tracks damage dealt to each player with timestamps
- Assists are awarded to players who dealt significant damage (>= 50) to a victim within 10 seconds before their death
- This calculation takes place in the `_calculate_player_stats` method in `smite_parser/parser.py`
- Testing confirms both kills/deaths (70 total each) and assists (80 total) are correctly calculated

### KillingBlow Events
- Updated the parser to properly account for both "Kill" and "KillingBlow" events
- Timeline now includes all player kill events
- Player statistics (kills/deaths) are accurate

### Item Cost Extraction
- Item costs are now correctly extracted from item purchase events
- Costs are displayed in the format "Item Name (cost)"

### Player Location Data
- Added default spawn locations when location data is missing
- Order team (1): (-10500.0, 0.0)
- Chaos team (2): (10500.0, 0.0)

### Match Metadata
- Implemented extraction of match metadata including map name and match type
- Match ID is derived from the log file name when not available in the log

## Performance Notes
- The parser successfully processes large log files with thousands of events
- Database operations are batched for efficiency
- Timeline generation focuses on significant events to prevent overwhelming the database 