# Technical Specification: SMITE 2 Combat Log SQL Parser

## 1. Introduction

This document outlines the technical specifications for parsing SMITE 2 combat log files and storing them in a SQLite database optimized for MOBA data analysis. The system will process JSON-formatted combat log entries, normalize the data, and create a relational database structure that supports multiple match files and enables comprehensive game analysis.

## 2. Questions Exploration

Before designing the database schema, I explored several key questions:

1. **Match identification?** - How to track multiple match files
2. **Entity relationships?** - How players, gods, items connect
3. **Event normalization?** - Handling varied event structures
4. **Performance optimization?** - Managing high-volume combat data
5. **Data transformation?** - Converting strings to appropriate types
6. **Derived metrics?** - Supporting calculations for KDA, gold/min
7. **Query patterns?** - Optimizing for common MOBA analytics
8. **Time-series support?** - Handling match timeline events
9. **Location data?** - Supporting heatmap and positioning analysis
10. **Schema flexibility?** - Accommodating future game updates

For each question, I considered:
- Data integrity requirements
- Query performance implications
- Normalization vs. denormalization tradeoffs
- Support for common MOBA analysis patterns
- Suitability for SQLite implementation
- Future extensibility needs

## 3. Database Schema

### 3.1 Core Tables

#### `matches`
Stores information about each match processed.

| Column | Type | Description |
|--------|------|-------------|
| `match_id` | TEXT | Primary key, unique identifier for the match |
| `source_file` | TEXT | Original log filename (without extension) |
| `start_time` | TIMESTAMP | Match start timestamp |
| `end_time` | TIMESTAMP | Match end timestamp |
| `duration_seconds` | INTEGER | Match duration in seconds |
| `match_data` | TEXT | Any additional match metadata (JSON) |

#### `players`
Stores normalized player information.

| Column | Type | Description |
|--------|------|-------------|
| `player_id` | INTEGER | Primary key, auto-incrementing |
| `match_id` | TEXT | Foreign key to matches.match_id |
| `player_name` | TEXT | Player's username |
| `team_id` | INTEGER | Team identifier (1 or 2) |
| `role` | TEXT | Player's assigned role (jungle, solo, etc.) |
| `god_id` | INTEGER | God ID selected by player |
| `god_name` | TEXT | God name selected by player |

#### `entities`
Stores information about all game entities (players, NPCs, objectives).

| Column | Type | Description |
|--------|------|-------------|
| `entity_id` | INTEGER | Primary key, auto-incrementing |
| `match_id` | TEXT | Foreign key to matches.match_id |
| `entity_name` | TEXT | Name of the entity |
| `entity_type` | TEXT | Type of entity (player, minion, jungle camp, etc.) |
| `team_id` | INTEGER | Team identifier (1 or 2, NULL for neutral) |

#### `items`
Stores information about items in the game.

| Column | Type | Description |
|--------|------|-------------|
| `item_id` | INTEGER | Primary key from game (itemid) |
| `item_name` | TEXT | Item name |
| `item_type` | TEXT | Item category (if available) |

#### `abilities`
Stores information about abilities used in the game.

| Column | Type | Description |
|--------|------|-------------|
| `ability_id` | INTEGER | Primary key, auto-incrementing |
| `match_id` | TEXT | Foreign key to matches.match_id |
| `ability_name` | TEXT | Name of the ability |
| `ability_source` | TEXT | Source of the ability (god, item, etc.) |

### 3.2 Event Tables

#### `combat_events`
Stores all combat-related events (damage, healing, CC, kills).

| Column | Type | Description |
|--------|------|-------------|
| `event_id` | INTEGER | Primary key, auto-incrementing |
| `match_id` | TEXT | Foreign key to matches.match_id |
| `event_time` | TIMESTAMP | When the event occurred |
| `event_type` | TEXT | Type of combat event (Damage, Healing, CrowdControl, KillingBlow, CritDamage) |
| `source_entity` | TEXT | Entity causing the event |
| `target_entity` | TEXT | Entity affected by the event |
| `ability_name` | TEXT | Ability or source that caused the event |
| `location_x` | REAL | X coordinate on the map |
| `location_y` | REAL | Y coordinate on the map |
| `value_amount` | INTEGER | Primary value (damage, healing amount) |
| `value_mitigated` | INTEGER | Secondary value (damage mitigated, etc.) |
| `event_text` | TEXT | Original text description of the event |

#### `reward_events`
Stores experience and currency rewards.

| Column | Type | Description |
|--------|------|-------------|
| `event_id` | INTEGER | Primary key, auto-incrementing |
| `match_id` | TEXT | Foreign key to matches.match_id |
| `event_time` | TIMESTAMP | When the event occurred |
| `event_type` | TEXT | Type of reward (Experience, Currency) |
| `entity_name` | TEXT | Entity receiving the reward |
| `location_x` | REAL | X coordinate on the map |
| `location_y` | REAL | Y coordinate on the map |
| `value_amount` | INTEGER | Amount of reward |
| `source_type` | TEXT | Source of the reward if available |
| `event_text` | TEXT | Original text description of the event |

#### `item_events`
Stores item purchase events.

| Column | Type | Description |
|--------|------|-------------|
| `event_id` | INTEGER | Primary key, auto-incrementing |
| `match_id` | TEXT | Foreign key to matches.match_id |
| `event_time` | TIMESTAMP | When the event occurred |
| `player_name` | TEXT | Player who purchased the item |
| `item_id` | INTEGER | ID of the item purchased |
| `item_name` | TEXT | Name of the item purchased |
| `location_x` | REAL | X coordinate on the map |
| `location_y` | REAL | Y coordinate on the map |
| `value` | INTEGER | Value associated with purchase (often cost) |
| `event_text` | TEXT | Original text description of the event |

#### `player_events`
Stores player-specific events like role assignments, god selection.

| Column | Type | Description |
|--------|------|-------------|
| `event_id` | INTEGER | Primary key, auto-incrementing |
| `match_id` | TEXT | Foreign key to matches.match_id |
| `event_time` | TIMESTAMP | When the event occurred |
| `event_type` | TEXT | Type of player event (RoleAssigned, GodHovered, GodPicked) |
| `player_name` | TEXT | Player involved |
| `team_id` | INTEGER | Team identifier (1 or 2) |
| `value` | TEXT | Event-specific value |
| `item_id` | INTEGER | ID related to event (god id, etc.) |
| `item_name` | TEXT | Name related to event (god name, role name) |
| `event_text` | TEXT | Original text description of the event |

### 3.3 Derived Tables (For Analysis)

#### `player_stats`
Aggregated player statistics per match.

| Column | Type | Description |
|--------|------|-------------|
| `stat_id` | INTEGER | Primary key, auto-incrementing |
| `match_id` | TEXT | Foreign key to matches.match_id |
| `player_name` | TEXT | Player name |
| `team_id` | INTEGER | Team identifier (1 or 2) |
| `kills` | INTEGER | Number of killing blows |
| `deaths` | INTEGER | Number of times killed |
| `assists` | INTEGER | Number of assists on kills |
| `damage_dealt` | INTEGER | Total damage dealt |
| `damage_taken` | INTEGER | Total damage taken |
| `healing_done` | INTEGER | Total healing performed |
| `gold_earned` | INTEGER | Total currency earned |
| `experience_earned` | INTEGER | Total experience earned |
| `cc_time_inflicted` | INTEGER | Total crowd control time inflicted |

#### `timeline_events`
Significant events for match timeline analysis.

| Column | Type | Description |
|--------|------|-------------|
| `event_id` | INTEGER | Primary key, auto-incrementing |
| `match_id` | TEXT | Foreign key to matches.match_id |
| `event_time` | TIMESTAMP | When the event occurred |
| `event_type` | TEXT | Type of timeline event (kill, objective, etc.) |
| `entity_name` | TEXT | Primary entity involved |
| `target_name` | TEXT | Secondary entity involved (if applicable) |
| `location_x` | REAL | X coordinate on the map |
| `location_y` | REAL | Y coordinate on the map |
| `event_details` | TEXT | Additional event details (JSON) |

## 4. Database Indexes

The following indexes will be created to optimize common query patterns:

1. `matches(match_id)` - Primary key index
2. `players(match_id, player_name)` - Fast player lookup within match
3. `combat_events(match_id, event_time)` - Timeline queries
4. `combat_events(match_id, source_entity)` - Player action queries
5. `combat_events(match_id, target_entity)` - Player received action queries
6. `combat_events(match_id, event_type)` - Event type filtering
7. `reward_events(match_id, entity_name)` - Player reward queries
8. `item_events(match_id, player_name)` - Player item purchase history
9. `player_stats(match_id, player_name)` - Fast player stats lookup
10. `timeline_events(match_id, event_time)` - Timeline analysis

## 5. Data Transformation

The parser will perform the following data transformations:

1. **Match ID Normalization** - Extract match ID from log start event or generate a UUID
2. **Timestamp Conversion** - Convert string timestamps (YYYY.MM.DD-HH.MM.SS) to SQLite TIMESTAMP format
3. **Numeric Value Conversion** - Convert string value1, value2 fields to INTEGER type
4. **Location Normalization** - Convert locationx, locationy strings to REAL type
5. **Entity Normalization** - Deduplicate and categorize entity names (players, NPCs)
6. **Team ID Extraction** - Extract team ID from value1 field in player events
7. **Text Parsing** - Extract additional info from text field where applicable
8. **Role Standardization** - Normalize role names (EJungle → Jungle)

## 6. Parser Implementation

The parser will be implemented in Python and follow this workflow:

1. **File Loading** - Read combat log file(s) line by line
2. **JSON Parsing** - Parse each line as JSON, handle malformed entries
3. **Event Categorization** - Categorize events by eventType and type
4. **Data Transformation** - Apply the transformations described in section 5
5. **Database Initialization** - Create SQLite database file and schema
6. **Data Insertion** - Insert processed events into appropriate tables
7. **Index Creation** - Create indexes after data insertion for performance
8. **Statistics Calculation** - Populate derived tables with aggregated stats
9. **Validation** - Perform validation checks on inserted data

## 7. Error Handling

The parser will implement these error-handling strategies:

1. **Malformed JSON** - Skip and log malformed entries
2. **Missing Fields** - Set NULL for optional fields, error for required fields
3. **Type Conversion Errors** - Fallback to string storage, log issue
4. **Database Errors** - Transaction rollback, detailed error reporting
5. **File Access Errors** - Clear error message, graceful termination

## 8. Performance Considerations

To optimize performance:

1. **Batch Inserts** - Use parameterized batch inserts for better performance
2. **Transaction Control** - Wrap operations in transactions
3. **Memory Management** - Process file in chunks to avoid memory issues
4. **Index Timing** - Create indexes after data insertion
5. **Query Optimization** - Optimize derived table queries
6. **Progress Reporting** - Implement progress feedback for large files

## 9. Implementation Notes

### 9.1 Required Python Libraries

- `sqlite3` - For database operations
- `json` - For parsing JSON entries
- `datetime` - For timestamp handling
- `uuid` - For generating unique match IDs if needed
- `re` - For text field parsing
- `logging` - For error and activity logging

### 9.2 SQLite Configuration

- `PRAGMA journal_mode=WAL` - Write-ahead logging for better concurrency
- `PRAGMA synchronous=NORMAL` - Balance between durability and performance
- `PRAGMA foreign_keys=ON` - Enable foreign key constraints
- `PRAGMA temp_store=MEMORY` - Store temporary tables in memory

## 10. Sample Queries

The database schema supports these analytics queries:

1. **Player KDA**: Calculate kills, deaths, assists per player
2. **Damage Statistics**: Analyze damage dealt and taken by player
3. **Gold/XP Efficiency**: Track currency and experience gained over time
4. **Item Build Timeline**: Analyze item purchase order and timing
5. **Lane Matchup Analysis**: Compare performance between opposing laners
6. **Team Fight Analysis**: Identify team fights by clustering combat events
7. **Objective Control**: Track objective kills and associated rewards
8. **Map Control Heatmaps**: Analyze player positions throughout match
9. **Crowd Control Impact**: Measure CC time applied by players
10. **Power Spike Analysis**: Identify key moments in player progression

## 11. Future Considerations

While outside the initial scope, these enhancements could be valuable:

1. **Match Comparison** - Cross-match analytics
2. **Player Profiling** - Track player tendencies across matches
3. **Meta Analysis** - Item and god pick/win rate statistics
4. **Visualization Layer** - Create a visualization API on top of the database
5. **Machine Learning Integration** - Predictive analytics for match outcomes

## 12. Conclusion

This technical specification outlines the database schema, parser implementation, and analytical capabilities for the SMITE 2 Combat Log SQL Parser. The design prioritizes data integrity, query performance, and analytical flexibility to support comprehensive MOBA match analysis. 