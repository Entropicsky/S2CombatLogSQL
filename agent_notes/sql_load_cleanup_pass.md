# SQL Database Cleanup Specification

## Overview

This specification outlines the issues identified in the current database schema and data population process, along with the proposed solutions. The goal is to ensure a complete, accurate, and consistent database that meets both the technical requirements and analytical expectations.

## Identified Issues and Proposed Solutions

### 1. Abilities Table Not Populated

**Issue:** The abilities table is empty despite combat events referencing abilities.

**Proposed Solution:**
- Implement a dedicated method `_process_abilities()` in the parser
- Extract ability names, types, and IDs from combat events
- Create a lookup process to track unique abilities
- Populate the abilities table during combat event processing
- Link combat events to abilities via ability_id

### 2. Redundant Timestamp Columns

**Issue:** Tables have both `timestamp` and `event_time` columns containing the same data.

**Proposed Solution:**
- Confirm the intended purpose of each column (internal timestamp vs. game time)
- If truly redundant, keep `event_time` for consistency with game timestamps
- Update schema and transformers to handle a single timestamp
- Document the meaning of the remaining timestamp field

### 3. Entity Table Missing Information

**Issue:** The entity table has null values for `entity_type` and `team_id`.

**Proposed Solution:**
- Enhance entity detection to classify types (player, minion, monster, structure)
- Infer team_id based on entity name patterns and combat interactions
- Create an entity classification system based on naming patterns
- Update the entity processing to include this information
- Add fallback classification for unknown entities

### 4. Item Events Cost Issues

**Issue:** The `cost` column in item_events seems to always be 0.

**Proposed Solution:**
- Investigate the source of item cost in the logs
- Implement proper cost extraction in the item event transformer
- Add validation for cost values
- Consider a fallback lookup system for known items if costs aren't in logs
- Fix any data type conversion issues in the transformer

### 5. Items Table Not Populated

**Issue:** The items table is empty despite item_events referencing items.

**Proposed Solution:**
- Implement a dedicated method `_process_items()` in the parser
- Extract unique items from item events
- Populate items table with unique item entries
- Create a lookup process to track unique items
- Link item_events to items via item_id

### 6. Match Metadata Missing

**Issue:** The matches table has null values for `map_name` and `game_type`.

**Proposed Solution:**
- Enhance match event detection to extract map and game type information
- Update the match creation process to include this metadata
- Implement fallbacks based on other indicators in the log
- Add validation for match metadata fields
- Document the expected format of match start events

### 7. Player Events Missing Information

**Issue:** The player_events table has null values for multiple columns.

**Proposed Solution:**
- Investigate the expected source of these fields in the logs
- Update the player event transformer to properly handle these fields
- Implement proper fallbacks for missing data
- Add validation for player event fields
- Consider alternative sources for location data if not available in logs

### 8. Player Stats Not Accurate

**Issue:** Player statistics appear incorrect with many zero values.

**Proposed Solution:**
- Review and fix the player stats calculation logic
- Ensure all relevant event types are considered for calculations
- Add validation for player stats calculations
- Implement more sophisticated stat derivation if needed
- Add unit tests for player stats calculations
- Consider separate aggregation methods for different stat types

### 9. Players Missing God Information

**Issue:** The players table has null values for `god_name` and `god_id`.

**Proposed Solution:**
- Enhance player event detection to extract god selection information
- Update the player creation process to include god information
- Implement fallbacks based on ability usage if direct selection not available
- Add validation for player-god association
- Document the expected format of god selection events

### 10. Timeline Events Insufficient

**Issue:** The timeline_events table has too few entries and lacks important game events.

**Proposed Solution:**
- Expand timeline event criteria to include more significant events
- Add event detection for objectives, team fights, multi-kills
- Implement more sophisticated timephase classification
- Ensure location data is included for all timeline events
- Consider importance weighting for different event types
- Implement pagination or filtering options for large timelines
- Add methods to detect game phase transitions

## Implementation Strategy

1. **Analysis Phase**
   - Thoroughly examine log files to understand available data
   - Create mappings between log fields and database fields
   - Document all event types and their properties

2. **Design Phase**
   - Update schema as needed to address issues
   - Design enhanced transformers for each event type
   - Create lookup systems for entities, items, and abilities

3. **Implementation Phase**
   - Implement changes in a modular way to avoid regression
   - Add extensive logging for debugging and validation
   - Create test cases for each transformation process

4. **Testing Phase**
   - Create unit tests for each component
   - Implement integration tests for the full pipeline
   - Use synthetic test data for edge cases
   - Verify against reference data from real games

5. **Deployment Phase**
   - Update the load.py script to incorporate improvements
   - Create database migration path if schema changes
   - Update documentation with new features and fields

## Success Criteria

- All tables correctly populated with appropriate data
- No null values for required fields
- Accurate player statistics matching game outcomes
- Comprehensive timeline of game events
- All known event types properly handled
- Documentation updated to reflect changes
- Tests passing for all components

## Prioritization

1. Fix core data issues (match metadata, entity classification)
2. Address statistical calculation issues
3. Implement abilities and items tables
4. Enhance timeline events
5. Remove redundancies and optimize schema

Each issue will be addressed one by one with thorough testing before moving to the next, to ensure stability and correctness throughout the process. 