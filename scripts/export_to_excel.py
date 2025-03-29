#!/usr/bin/env python3
"""
Export all tables from a SQLite database to an Excel file.
Each table will be in a separate worksheet.
"""

import os
import sys
import sqlite3
import pandas as pd
import argparse
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('excel_exporter')

def get_table_names(db_path):
    """Get all table names from the SQLite database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    conn.close()
    return [table[0] for table in tables]

def export_to_excel(db_path, excel_path=None):
    """Export all tables from the SQLite database to an Excel file."""
    if excel_path is None:
        excel_path = os.path.splitext(db_path)[0] + '.xlsx'
    
    logger.info(f"Exporting database {db_path} to Excel file {excel_path}")
    
    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    
    # Get all table names
    tables = get_table_names(db_path)
    
    # Create a Pandas Excel writer using openpyxl as the engine
    writer = pd.ExcelWriter(excel_path, engine='openpyxl')
    
    # Export each table to a separate worksheet
    for table in tables:
        logger.info(f"Exporting table: {table}")
        try:
            # Read the table into a DataFrame
            df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
            
            # Write the DataFrame to an Excel worksheet
            df.to_excel(writer, sheet_name=table, index=False)
            
            # Set column widths to make data readable
            worksheet = writer.sheets[table]
            for i, col in enumerate(df.columns):
                max_width = max(df[col].astype(str).map(len).max(), len(col)) + 2
                # Excel has a maximum column width of 255
                col_width = min(max_width, 100)
                # Convert to Excel column width which is in characters
                worksheet.column_dimensions[chr(65 + i)].width = col_width
        except Exception as e:
            logger.error(f"Error exporting table {table}: {e}")
    
    # Close the Excel writer and save the file
    writer.close()
    conn.close()
    
    logger.info(f"Successfully exported all tables to {excel_path}")
    return excel_path

def main():
    parser = argparse.ArgumentParser(description='Export SQLite database to Excel file')
    parser.add_argument('db_path', help='Path to the SQLite database file')
    parser.add_argument('-o', '--output', help='Path to the output Excel file')
    
    args = parser.parse_args()
    
    try:
        export_path = export_to_excel(args.db_path, args.output)
        print(f"✅ Successfully exported database to: {export_path}")
    except Exception as e:
        logger.error(f"Failed to export database: {e}")
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 