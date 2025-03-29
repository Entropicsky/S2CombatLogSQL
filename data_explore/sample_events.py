import json
import random
from collections import defaultdict

def sample_events(log_file, sample_size=5):
    """
    Extract and display samples of each event type from the log file.
    
    Args:
        log_file (str): Path to the combat log file
        sample_size (int): Number of samples to display for each event type
    """
    event_samples = defaultdict(list)
    event_type_counts = defaultdict(int)
    type_within_event_counts = defaultdict(lambda: defaultdict(int))
    
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
                
                # Count occurrences
                event_type_counts[event_type] += 1
                type_within_event_counts[event_type][inner_type] += 1
                
                # Store samples (up to sample_size)
                key = f"{event_type}_{inner_type}"
                if len(event_samples[key]) < sample_size:
                    event_samples[key].append(event)
                # Random sampling to ensure diverse representation
                elif random.random() < 0.1:
                    idx = random.randint(0, sample_size - 1)
                    event_samples[key][idx] = event
                    
            except json.JSONDecodeError as e:
                print(f"Error parsing line: {line}")
                print(f"Error: {e}")
    
    # Print event type counts
    print("EVENT TYPE COUNTS:")
    for event_type, count in sorted(event_type_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {event_type}: {count}")
    
    print("\nTYPE WITHIN EVENT TYPE COUNTS:")
    for event_type, type_counts in sorted(type_within_event_counts.items()):
        print(f"{event_type}:")
        for inner_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {inner_type}: {count}")
    
    # Print samples
    print("\nSAMPLES FOR EACH EVENT AND TYPE:")
    for key, samples in sorted(event_samples.items()):
        event_type, inner_type = key.split('_', 1)
        print(f"\n{event_type} - {inner_type}:")
        for i, sample in enumerate(samples, 1):
            print(f"  Sample {i}:")
            for field, value in sample.items():
                print(f"    {field}: {value}")

if __name__ == "__main__":
    sample_events("../CombatLogExample.log", sample_size=2) 