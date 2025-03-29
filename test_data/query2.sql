.tables

-- Examine matches table
SELECT * FROM matches;

-- Examine entities table
SELECT COUNT(*) AS entity_count FROM entities;

-- Sample of entities
SELECT * FROM entities LIMIT 10;

-- Check other tables
SELECT COUNT(*) AS player_count FROM players;
SELECT COUNT(*) AS combat_count FROM combat_events;
SELECT COUNT(*) AS item_count FROM item_events;
SELECT COUNT(*) AS reward_count FROM reward_events;
SELECT COUNT(*) AS player_event_count FROM player_events;
SELECT COUNT(*) AS timeline_count FROM timeline_events;
SELECT COUNT(*) AS player_stat_count FROM player_stats; 