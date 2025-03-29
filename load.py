#!/usr/bin/env python3
"""
Simple script to load SMITE 2 combat log files into a SQLite database.
"""
import os
import sys
import argparse
from pathlib import Path

from smite_parser.config.config import ParserConfig
from smite_parser.parser import CombatLogParser
from reprocess_data import verify_data
from scripts.export_to_excel import export_to_excel

def main():
    """Process a combat log file and load it into a SQLite database."""
    parser = argparse.ArgumentParser(description="Load SMITE 2 combat log files into a SQLite database")
    
    parser.add_argument("log_file", help="Path to the combat log file")
    parser.add_argument("-o", "--output", help="Output database file path (default: auto-generated based on log file name)")
    parser.add_argument("--verify", action="store_true", help="Verify the database after loading")
    parser.add_argument("--force", action="store_true", help="Force reload if match already exists")
    parser.add_argument("--no-excel", action="store_true", help="Skip exporting to Excel")
    
    args = parser.parse_args()
    
    # Check if log file exists
    log_path = Path(args.log_file)
    if not log_path.exists():
        print(f"Error: Log file '{args.log_file}' does not exist")
        return 1
    
    # Determine output path
    if args.output:
        db_path = args.output
    else:
        # Use the log file name but with .db extension in a data directory
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        db_path = data_dir / f"{log_path.stem}.db"
    
    print(f"Processing log file: {log_path}")
    print(f"Output database: {db_path}")
    
    # Configure parser
    config = ParserConfig(
        db_path=str(db_path),
        batch_size=1000,
        show_progress=True,
        skip_malformed=True,
    )
    
    # Create parser
    parser = CombatLogParser(config)
    
    # If force reload and database exists with match data, clear it
    if args.force and os.path.exists(db_path):
        print("Force reload requested. Clearing existing match data...")
        # This will be done automatically by the parser for matching match IDs
    
    # Parse the file
    success = parser.parse_file(str(log_path))
    
    if success:
        print(f"\n✅ Successfully processed log file: {log_path}")
        print(f"Data stored in: {db_path}")
        
        # Verify if requested
        if args.verify:
            print("\nVerifying database contents...")
            verify_data(str(db_path))
        
        # Export to Excel
        if not args.no_excel:
            try:
                excel_path = export_to_excel(str(db_path))
                print(f"Data exported to Excel: {excel_path}")
            except Exception as e:
                print(f"Failed to export to Excel: {e}")
                print("Install required packages with: pip install pandas openpyxl")
            
        print("\nRun the following to query the database:")
        print(f"sqlite3 {db_path}")
        
        return 0
    else:
        print(f"\n❌ Failed to process log file: {log_path}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 