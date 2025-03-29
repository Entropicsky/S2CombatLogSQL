"""Command-line interface for SMITE 2 Combat Log Parser."""
import os
import logging
import click
from pathlib import Path

from .config.config import ParserConfig, configure_logging
from .parser import CombatLogParser
from .models import init_db

logger = logging.getLogger(__name__)


@click.group()
@click.version_option()
def main():
    """SMITE 2 Combat Log Parser CLI."""
    pass


@main.command()
@click.argument("log_file", type=click.Path(exists=True, readable=True))
@click.option("--output", "-o", help="Output database file path", default=None)
@click.option("--batch-size", "-b", help="Batch size for database operations", type=int, default=1000)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--quiet", "-q", is_flag=True, help="Suppress progress display")
@click.option("--skip-malformed", is_flag=True, help="Skip malformed JSON lines", default=True)
def parse(log_file, output, batch_size, verbose, quiet, skip_malformed):
    """Parse a SMITE 2 combat log file into a SQLite database."""
    # Determine output path
    if output is None:
        log_path = Path(log_file)
        output = f"{log_path.stem}.db"
    
    # Configure parser
    config = ParserConfig(
        db_path=output,
        batch_size=batch_size,
        show_progress=not quiet,
        skip_malformed=skip_malformed,
        log_level=logging.DEBUG if verbose else logging.INFO,
    )
    
    # Configure logging
    configure_logging(config)
    
    logger.info(f"Parsing log file: {log_file}")
    logger.info(f"Output database: {output}")
    
    # Initialize database
    init_db(f"sqlite:///{output}")
    
    # Create and run parser
    parser = CombatLogParser(config)
    success = parser.parse_file(log_file)
    
    if success:
        logger.info(f"Successfully parsed log file to {output}")
        return 0
    else:
        logger.error("Failed to parse log file")
        return 1


@main.command()
@click.argument("db_file", type=click.Path(exists=True, readable=True))
def info(db_file):
    """Display information about a parsed SMITE 2 database."""
    import sqlite3
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Get match information
        cursor.execute("SELECT match_id, source_file, start_time, end_time, duration_seconds FROM matches")
        matches = cursor.fetchall()
        
        if not matches:
            click.echo("No matches found in database")
            return 1
        
        click.echo(f"Found {len(matches)} matches in database:")
        for match in matches:
            match_id, source_file, start_time, end_time, duration = match
            click.echo(f"\nMatch ID: {match_id}")
            click.echo(f"Source file: {source_file}")
            click.echo(f"Duration: {duration} seconds")
            
            # Get player information
            cursor.execute("""
                SELECT player_name, team_id, role, god_name 
                FROM players 
                WHERE match_id = ? 
                ORDER BY team_id, player_name
            """, (match_id,))
            players = cursor.fetchall()
            
            click.echo(f"\nPlayers ({len(players)}):")
            for player in players:
                name, team, role, god = player
                click.echo(f"  {name} (Team {team}, {role}, {god})")
            
            # Get event counts
            cursor.execute("""
                SELECT 'Combat events' as type, COUNT(*) FROM combat_events WHERE match_id = ?
                UNION ALL
                SELECT 'Reward events', COUNT(*) FROM reward_events WHERE match_id = ?
                UNION ALL
                SELECT 'Item events', COUNT(*) FROM item_events WHERE match_id = ?
                UNION ALL
                SELECT 'Player events', COUNT(*) FROM player_events WHERE match_id = ?
                UNION ALL
                SELECT 'Timeline events', COUNT(*) FROM timeline_events WHERE match_id = ?
            """, (match_id, match_id, match_id, match_id, match_id))
            event_counts = cursor.fetchall()
            
            click.echo("\nEvent counts:")
            for event_type, count in event_counts:
                click.echo(f"  {event_type}: {count}")
            
            # Get player statistics
            cursor.execute("""
                SELECT player_name, kills, deaths, assists, damage_dealt, healing_done, gold_earned 
                FROM player_stats 
                WHERE match_id = ? 
                ORDER BY team_id, player_name
            """, (match_id,))
            stats = cursor.fetchall()
            
            click.echo("\nPlayer statistics:")
            click.echo("  Player             K / D / A      Damage    Healing       Gold")
            click.echo("  --------------------------------------------------------------")
            for stat in stats:
                name, kills, deaths, assists, damage, healing, gold = stat
                click.echo(f"  {name:<18} {kills:2} / {deaths:2} / {assists:2}  {damage:8}  {healing:8}  {gold:8}")
        
        return 0
    
    except Exception as e:
        click.echo(f"Error reading database: {e}")
        return 1
    finally:
        if 'conn' in locals():
            conn.close()


@main.command()
@click.argument("db_file", type=click.Path(exists=True, readable=True))
@click.argument("query_file", type=click.Path(exists=True, readable=True))
@click.option("--output", "-o", help="Output file for query results", default=None)
def query(db_file, query_file, output):
    """Run a SQL query from a file against a parsed SMITE 2 database."""
    import sqlite3
    import csv
    import sys
    
    try:
        # Read query from file
        with open(query_file, 'r') as f:
            query = f.read()
        
        # Connect to database and execute query
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        
        if not results:
            click.echo("Query returned no results")
            return 0
        
        # Determine output destination
        output_file = None
        if output:
            output_file = open(output, 'w', newline='')
            writer = csv.writer(output_file)
            writer.writerow([key for key in results[0].keys()])
            writer.writerows([[row[key] for key in row.keys()] for row in results])
            click.echo(f"Wrote {len(results)} rows to {output}")
        else:
            # Print to console
            columns = [key for key in results[0].keys()]
            # Calculate column widths
            col_widths = [max(len(str(row[col])) for row in results + [dict(zip(columns, columns))]) for col in columns]
            
            # Print header
            header = " | ".join(f"{col:{width}}" for col, width in zip(columns, col_widths))
            click.echo(header)
            click.echo("-" * len(header))
            
            # Print rows
            for row in results:
                click.echo(" | ".join(f"{str(row[col]):{width}}" for col, width in zip(columns, col_widths)))
            
            click.echo(f"\nReturned {len(results)} rows")
        
        return 0
    
    except Exception as e:
        click.echo(f"Error executing query: {e}")
        return 1
    finally:
        if 'conn' in locals():
            conn.close()
        if output_file:
            output_file.close()


@main.command()
@click.argument("log_file", type=click.Path(exists=True, readable=True))
@click.argument("db_file", type=click.Path(exists=True, readable=True))
@click.option("--batch-size", "-b", help="Batch size for database operations", type=int, default=1000)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--quiet", "-q", is_flag=True, help="Suppress progress display")
def reprocess(log_file, db_file, batch_size, verbose, quiet):
    """Reprocess a log file and update an existing database (overwriting existing match data)."""
    import sqlite3
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    # Configure parser
    config = ParserConfig(
        db_path=db_file,
        batch_size=batch_size,
        show_progress=not quiet,
        skip_malformed=True,
        log_level=logging.DEBUG if verbose else logging.INFO,
    )
    
    # Configure logging
    configure_logging(config)
    
    logger.info(f"Reprocessing log file: {log_file}")
    logger.info(f"Target database: {db_file}")
    
    # Initialize database connection
    engine = create_engine(f"sqlite:///{db_file}")
    Session = sessionmaker(bind=engine)
    
    # Create parser
    parser = CombatLogParser(config)
    
    try:
        # First, parse just to extract match ID
        with open(log_file, 'r') as f:
            for line in f:
                if '"eventType":"match"' in line.lower():
                    import json
                    try:
                        event = json.loads(line)
                        match_id = event.get("matchid", "unknown")
                        logger.info(f"Found match ID: {match_id}")
                        
                        # Now clear existing match data
                        with Session() as session:
                            parser.clear_existing_match(session, match_id)
                        break
                    except json.JSONDecodeError:
                        continue
        
        # Now parse the whole file again
        success = parser.parse_file(log_file)
        
        if success:
            logger.info(f"Successfully reprocessed log file in {db_file}")
            return 0
        else:
            logger.error("Failed to reprocess log file")
            return 1
            
    except Exception as e:
        logger.error(f"Error during reprocessing: {e}")
        return 1


if __name__ == "__main__":
    main() 