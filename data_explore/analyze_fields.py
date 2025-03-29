import json
from collections import defaultdict

def analyze_fields(log_file):
    """
    Analyze the structure of events in the log file.
    Identifies fields present in each event type and what data types they contain.
    
    Args:
        log_file (str): Path to the combat log file
    """
    field_structures = defaultdict(lambda: defaultdict(set))
    
    with open(log_file, 'r') as f:
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
                key = f"{event_type}_{inner_type}"
                
                # Record the fields and their data types
                for field, value in event.items():
                    data_type = type(value).__name__
                    field_structures[key][field].add(data_type)
                    
            except json.JSONDecodeError as e:
                print(f"Error parsing line: {line}")
                print(f"Error: {e}")
    
    # Print field structures
    print("FIELD STRUCTURES BY EVENT TYPE AND TYPE:")
    for key in sorted(field_structures.keys()):
        event_type, inner_type = key.split('_', 1)
        print(f"\n{event_type} - {inner_type}:")
        print("  Fields:")
        for field, types in sorted(field_structures[key].items()):
            type_str = ", ".join(sorted(types))
            print(f"    {field}: {type_str}")

if __name__ == "__main__":
    analyze_fields("../CombatLogExample.log") 