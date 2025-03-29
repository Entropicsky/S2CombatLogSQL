#!/usr/bin/env python3
"""
Test script to validate parser fixes.
This script will process a sample log file and verify that the fixed issues are resolved.
"""
import os
import sys
import logging
import sqlite3
from pathlib import Path

from smite_parser.config.config import ParserConfig
from smite_parser.parser import CombatLogParser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def verify_db_table(db_path, table_name, expected_count=None, null_check_columns=None, sample_rows=3):
    """Verify table contents and check for nulls in specific columns."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get row count
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    if expected_count is not None:
        if count == 0 and expected_count > 0:
            logger.error(f"❌ Table {table_name} is empty (expected {expected_count} rows)")
            return False
        if count < expected_count:
            logger.warning(f"⚠️ Table {table_name} has fewer rows than expected ({count} vs {expected_count})")
    
    logger.info(f"Table {table_name}: {count} rows found")
    
    # Check for nulls in specific columns
    if null_check_columns:
        for column in null_check_columns:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {column} IS NULL")
            null_count = cursor.fetchone()[0]
            if null_count > 0:
                percent_null = (null_count / count) * 100 if count > 0 else 0
                if percent_null > 95:  # If more than 95% are null, it's a serious issue
                    logger.error(f"❌ Column {column} in {table_name} has {null_count} NULL values ({percent_null:.1f}%)")
                else:
                    logger.warning(f"⚠️ Column {column} in {table_name} has {null_count} NULL values ({percent_null:.1f}%)")
    
    # Get sample rows
    cursor.execute(f"SELECT * FROM {table_name} LIMIT {sample_rows}")
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    
    for i, row in enumerate(rows):
        row_dict = {columns[j]: row[j] for j in range(len(columns))}
        logger.info(f"Sample row {i+1}: {row_dict}")
    
    conn.close()
    return True

def verify_timeline_coverage(db_path):
    """Verify timeline event coverage across the match timespan."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get match duration
    cursor.execute("SELECT start_time, end_time FROM matches")
    match_times = cursor.fetchone()
    if not match_times or not match_times[0] or not match_times[1]:
        logger.error("❌ Match start/end times not found")
        return False
    
    start_time, end_time = match_times
    
    # Get timeline event count and distribution
    cursor.execute("SELECT COUNT(*), MIN(event_time), MAX(event_time) FROM timeline_events")
    timeline_stats = cursor.fetchone()
    if not timeline_stats or timeline_stats[0] == 0:
        logger.error("❌ No timeline events found")
        return False
    
    event_count, min_time, max_time = timeline_stats
    
    # Count events by type
    cursor.execute("SELECT event_type, COUNT(*) FROM timeline_events GROUP BY event_type")
    event_types = cursor.fetchall()
    
    logger.info(f"Timeline has {event_count} events from {min_time} to {max_time}")
    for event_type, count in event_types:
        logger.info(f"  - {event_type}: {count} events")
    
    conn.close()
    return True

def verify_entity_types(db_path):
    """Verify entity type classification."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check entity types
    cursor.execute("SELECT entity_type, COUNT(*) FROM entities GROUP BY entity_type")
    entity_types = cursor.fetchall()
    
    if not entity_types:
        logger.error("❌ No entity types found")
        return False
    
    for entity_type, count in entity_types:
        if entity_type is None:
            logger.error(f"❌ {count} entities have NULL entity_type")
        else:
            logger.info(f"Entity type '{entity_type}': {count} entities")
    
    conn.close()
    return True

def verify_player_stats(db_path):
    """Verify player stats are calculated correctly."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check player stats
    cursor.execute("""
        SELECT p.player_name, p.team_id, p.role, 
               ps.kills, ps.deaths, ps.assists, ps.damage_dealt, ps.damage_taken, 
               ps.healing_done, ps.gold_earned, ps.experience_earned
        FROM player_stats ps
        JOIN players p ON ps.player_name = p.player_name AND ps.match_id = p.match_id
    """)
    player_stats = cursor.fetchall()
    
    if not player_stats:
        logger.error("❌ No player stats found")
        return False
    
    # Count zeroes to check for potential calculation issues
    zero_counts = {"kills": 0, "deaths": 0, "assists": 0, "damage": 0, "healing": 0, "gold": 0, "xp": 0}
    
    for stat in player_stats:
        name, team, role, kills, deaths, assists, damage, taken, healing, gold, xp = stat
        logger.info(f"Player {name} (Team {team}, {role}): K/D/A: {kills}/{deaths}/{assists}, Damage: {damage}")
        
        # Check for potential issues (all zeroes might indicate calculation problems)
        if kills == 0: zero_counts["kills"] += 1
        if deaths == 0: zero_counts["deaths"] += 1
        if assists == 0: zero_counts["assists"] += 1
        if damage == 0: zero_counts["damage"] += 1
        if healing == 0: zero_counts["healing"] += 1
        if gold == 0: zero_counts["gold"] += 1
        if xp == 0: zero_counts["xp"] += 1
    
    total_players = len(player_stats)
    for stat, count in zero_counts.items():
        if count == total_players:
            logger.error(f"❌ All players have 0 {stat} - likely a calculation issue")
        elif count > total_players * 0.7:  # If more than 70% are zero, might be an issue
            logger.warning(f"⚠️ {count}/{total_players} players have 0 {stat} - possible calculation issue")
    
    conn.close()
    return True

def verify_god_data(db_path):
    """Verify god data is populated correctly."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check god data
    cursor.execute("SELECT player_name, god_name, god_id FROM players")
    god_data = cursor.fetchall()
    
    null_god_count = 0
    for player in god_data:
        name, god_name, god_id = player
        if god_name is None and god_id is None:
            null_god_count += 1
            logger.warning(f"Player {name} has no god data")
        else:
            logger.info(f"Player {name} is using {god_name} (ID: {god_id})")
    
    if null_god_count == len(god_data):
        logger.error("❌ All players have NULL god data")
    
    conn.close()
    return null_god_count < len(god_data)

def verify_abilities_table(db_path):
    """Verify the abilities table is populated correctly."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check abilities table
    cursor.execute("SELECT COUNT(*) FROM abilities")
    ability_count = cursor.fetchone()[0]
    
    if ability_count == 0:
        logger.error("❌ Abilities table is empty")
        conn.close()
        return False
    
    # Get sample abilities
    cursor.execute("SELECT ability_id, ability_name, ability_source FROM abilities LIMIT 5")
    abilities = cursor.fetchall()
    
    for ability in abilities:
        ability_id, name, source = ability
        logger.info(f"Ability: {name}, Source: {source}, ID: {ability_id}")
    
    conn.close()
    return True

def verify_items_table(db_path):
    """Verify the items table is populated correctly."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check items table
    cursor.execute("SELECT COUNT(*) FROM items")
    item_count = cursor.fetchone()[0]
    
    if item_count == 0:
        logger.error("❌ Items table is empty")
        conn.close()
        return False
    
    # Get sample items
    cursor.execute("SELECT item_id, item_name, item_type FROM items LIMIT 5")
    items = cursor.fetchall()
    
    for item in items:
        item_id, name, type = item
        logger.info(f"Item: {name}, Type: {type}, ID: {item_id}")
    
    conn.close()
    return True

def verify_item_costs(db_path):
    """Verify item costs are populated correctly."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check item costs
    cursor.execute("SELECT COUNT(*) FROM item_events WHERE cost > 0")
    items_with_cost = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM item_events")
    total_items = cursor.fetchone()[0]
    
    if total_items > 0:
        percent_with_cost = (items_with_cost / total_items) * 100
        logger.info(f"Item events with cost: {items_with_cost}/{total_items} ({percent_with_cost:.1f}%)")
        
        if percent_with_cost < 10:
            logger.error("❌ Very few item events have cost values")
            conn.close()
            return False
    
    # Get sample item costs
    cursor.execute("SELECT item_name, cost FROM item_events WHERE cost > 0 LIMIT 5")
    item_costs = cursor.fetchall()
    
    for item in item_costs:
        name, cost = item
        logger.info(f"Item: {name}, Cost: {cost}")
    
    conn.close()
    return True

def run_tests(db_path):
    """Run all tests on the database."""
    logger.info(f"Running tests on database: {db_path}")
    
    results = []
    
    # Verify each table
    tables = [
        ("matches", 1, ["map_name", "game_type"]),
        ("players", None, ["god_name", "god_id"]),
        ("entities", None, ["entity_type", "team_id"]),
        ("combat_events", None, None),
        ("reward_events", None, None),
        ("item_events", None, ["cost"]),
        ("player_events", None, ["entity_name", "team_id", "location_x", "location_y"]),
        ("player_stats", None, ["kills", "deaths", "assists", "damage_dealt", "damage_taken", 
                               "healing_done", "gold_earned", "experience_earned"]),
        ("timeline_events", None, None),
        ("abilities", None, ["ability_name"]),
        ("items", None, ["item_name"])
    ]
    
    for table, expected_count, null_checks in tables:
        logger.info(f"\n=== Testing {table} table ===")
        try:
            result = verify_db_table(db_path, table, expected_count, null_checks)
            results.append((f"Table {table}", result))
        except Exception as e:
            logger.error(f"Error testing {table} table: {e}")
            results.append((f"Table {table}", False))
    
    # Verify specific features
    feature_tests = [
        ("Timeline coverage", verify_timeline_coverage),
        ("Entity type classification", verify_entity_types),
        ("Player stats calculation", verify_player_stats),
        ("God data population", verify_god_data),
        ("Abilities table population", verify_abilities_table),
        ("Items table population", verify_items_table),
        ("Item costs population", verify_item_costs)
    ]
    
    for name, test_func in feature_tests:
        logger.info(f"\n=== Testing {name} ===")
        try:
            result = test_func(db_path)
            results.append((name, result))
        except Exception as e:
            logger.error(f"Error testing {name}: {e}")
            results.append((name, False))
    
    # Print summary
    logger.info("\n=== Test Summary ===")
    passed = 0
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} - {name}")
        if result:
            passed += 1
    
    logger.info(f"\n{passed}/{len(results)} tests passed")
    
    return passed == len(results)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <db_path>")
        sys.exit(1)
    
    db_path = sys.argv[1]
    if not os.path.exists(db_path):
        logger.error(f"Database file {db_path} not found")
        sys.exit(1)
    
    success = run_tests(db_path)
    sys.exit(0 if success else 1) 