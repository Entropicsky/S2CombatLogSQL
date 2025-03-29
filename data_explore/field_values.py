import json
from collections import defaultdict
import re
from datetime import datetime

def analyze_field_values(log_file):
    """
    Analyze the values in key fields to understand their patterns and ranges.
    
    Args:
        log_file (str): Path to the combat log file
    """
    # Track player names, locations, times, and other key information
    players = set()
    enemies = set()
    items = set()
    abilities = set()
    locations = []
    timestamp_min = None
    timestamp_max = None
    
    # Value ranges
    damage_values = []
    healing_values = []
    experience_values = []
    currency_values = []
    
    with open(log_file, 'r', encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if not line.endswith(','):
                line = line.rstrip('}') + '}'
            else:
                line = line.rstrip(',')
                
            try:
                event = json.loads(line)
                event_type = event.get('eventType')
                inner_type = event.get('type', 'NONE')
                
                # Track all player names
                if 'sourceowner' in event:
                    players.add(event['sourceowner'])
                
                if 'targetowner' in event:
                    # Some targets might be NPCs/monsters
                    if event_type == 'CombatMsg' and inner_type in ['Damage', 'KillingBlow']:
                        if event['targetowner'] != event.get('sourceowner'):
                            enemies.add(event['targetowner'])
                    
                # Track items and abilities
                if 'itemname' in event and event['itemname']:
                    if event_type == 'itemmsg' and inner_type == 'ItemPurchase':
                        items.add(event['itemname'])
                    elif event_type == 'CombatMsg':
                        abilities.add(event['itemname'])
                
                # Track locations for heatmap data
                if 'locationx' in event and 'locationy' in event:
                    try:
                        x = float(event['locationx'])
                        y = float(event['locationy'])
                        locations.append((x, y))
                    except (ValueError, TypeError):
                        pass
                
                # Track timestamps
                if 'time' in event:
                    try:
                        timestamp = datetime.strptime(event['time'], '%Y.%m.%d-%H.%M.%S')
                        if timestamp_min is None or timestamp < timestamp_min:
                            timestamp_min = timestamp
                        if timestamp_max is None or timestamp > timestamp_max:
                            timestamp_max = timestamp
                    except ValueError:
                        pass
                
                # Track value ranges
                if event_type == 'CombatMsg':
                    if inner_type == 'Damage' and 'value1' in event:
                        try:
                            damage_values.append(int(event['value1']))
                        except (ValueError, TypeError):
                            pass
                    elif inner_type == 'Healing' and 'value1' in event:
                        try:
                            healing_values.append(int(event['value1']))
                        except (ValueError, TypeError):
                            pass
                elif event_type == 'RewardMsg':
                    if inner_type == 'Experience' and 'value1' in event:
                        try:
                            experience_values.append(int(event['value1']))
                        except (ValueError, TypeError):
                            pass
                    elif inner_type == 'Currency' and 'value1' in event:
                        try:
                            currency_values.append(int(event['value1']))
                        except (ValueError, TypeError):
                            pass
                
            except json.JSONDecodeError as e:
                continue
    
    # Calculate statistics for numeric values
    def calc_stats(values):
        if not values:
            return {"min": None, "max": None, "avg": None, "count": 0}
        return {
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "count": len(values)
        }
    
    damage_stats = calc_stats(damage_values)
    healing_stats = calc_stats(healing_values)
    exp_stats = calc_stats(experience_values)
    currency_stats = calc_stats(currency_values)
    
    # Calculate match duration if timestamps were found
    match_duration = None
    if timestamp_min and timestamp_max:
        match_duration = timestamp_max - timestamp_min
    
    # Print results
    print("PLAYER ANALYSIS:")
    print(f"  Total Players: {len(players)}")
    print(f"  Player Names: {', '.join(sorted(players))}")
    print(f"\nENEMY ANALYSIS:")
    print(f"  Total Enemies/NPCs: {len(enemies)}")
    print(f"  Enemy Names: {', '.join(sorted(enemies))}")
    
    print(f"\nITEM ANALYSIS:")
    print(f"  Total Items: {len(items)}")
    print(f"  Items: {', '.join(sorted(items))}")
    
    print(f"\nABILITY ANALYSIS:")
    print(f"  Total Abilities: {len(abilities)}")
    print(f"  Sample Abilities: {', '.join(sorted(list(abilities)[:20]))}")
    
    print(f"\nLOCATION ANALYSIS:")
    print(f"  Total Location Points: {len(locations)}")
    if locations:
        x_values = [loc[0] for loc in locations]
        y_values = [loc[1] for loc in locations]
        print(f"  X-Range: {min(x_values)} to {max(x_values)}")
        print(f"  Y-Range: {min(y_values)} to {max(y_values)}")
    
    print(f"\nTIME ANALYSIS:")
    print(f"  Match Start: {timestamp_min}")
    print(f"  Match End: {timestamp_max}")
    print(f"  Match Duration: {match_duration}")
    
    print(f"\nVALUE ANALYSIS:")
    print(f"  Damage: min={damage_stats['min']}, max={damage_stats['max']}, avg={damage_stats['avg']:.2f}, count={damage_stats['count']}")
    print(f"  Healing: min={healing_stats['min']}, max={healing_stats['max']}, avg={healing_stats['avg']:.2f}, count={healing_stats['count']}")
    print(f"  Experience: min={exp_stats['min']}, max={exp_stats['max']}, avg={exp_stats['avg']:.2f}, count={exp_stats['count']}")
    print(f"  Currency: min={currency_stats['min']}, max={currency_stats['max']}, avg={currency_stats['avg']:.2f}, count={currency_stats['count']}")

if __name__ == "__main__":
    analyze_field_values("../CombatLogExample.log") 