"""Configuration module for SMITE 2 Combat Log Parser."""
import os
import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional
import dotenv

# Load environment variables from .env file if present
dotenv.load_dotenv()

@dataclass
class ParserConfig:
    """Configuration for the parser."""
    # Database settings
    db_path: str
    batch_size: int = 1000
    journal_mode: str = "WAL"
    synchronous: str = "NORMAL"
    foreign_keys: bool = True
    temp_store: str = "MEMORY"
    
    # Logging settings
    log_level: int = logging.INFO
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file: Optional[str] = None
    
    # Parser settings
    chunk_size: int = 10000  # Number of lines to process at once
    show_progress: bool = True
    skip_malformed: bool = True
    
    @classmethod
    def from_env(cls, db_path: Optional[str] = None) -> 'ParserConfig':
        """Create a configuration from environment variables."""
        return cls(
            db_path=db_path or os.environ.get("SMITE_DB_PATH", "smite_matches.db"),
            batch_size=int(os.environ.get("SMITE_BATCH_SIZE", "1000")),
            journal_mode=os.environ.get("SMITE_JOURNAL_MODE", "WAL"),
            synchronous=os.environ.get("SMITE_SYNCHRONOUS", "NORMAL"),
            foreign_keys=os.environ.get("SMITE_FOREIGN_KEYS", "True").lower() == "true",
            temp_store=os.environ.get("SMITE_TEMP_STORE", "MEMORY"),
            log_level=getattr(logging, os.environ.get("SMITE_LOG_LEVEL", "INFO")),
            log_format=os.environ.get("SMITE_LOG_FORMAT", 
                               "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
            log_file=os.environ.get("SMITE_LOG_FILE"),
            chunk_size=int(os.environ.get("SMITE_CHUNK_SIZE", "10000")),
            show_progress=os.environ.get("SMITE_SHOW_PROGRESS", "True").lower() == "true",
            skip_malformed=os.environ.get("SMITE_SKIP_MALFORMED", "True").lower() == "true",
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the configuration to a dictionary."""
        return {
            "db_path": self.db_path,
            "batch_size": self.batch_size,
            "journal_mode": self.journal_mode,
            "synchronous": self.synchronous,
            "foreign_keys": self.foreign_keys,
            "temp_store": self.temp_store,
            "log_level": self.log_level,
            "log_format": self.log_format,
            "log_file": self.log_file,
            "chunk_size": self.chunk_size,
            "show_progress": self.show_progress,
            "skip_malformed": self.skip_malformed,
        }


def configure_logging(config: ParserConfig) -> None:
    """Configure logging based on the configuration."""
    handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(config.log_format))
    handlers.append(console_handler)
    
    # File handler if log file specified
    if config.log_file:
        file_handler = logging.FileHandler(config.log_file)
        file_handler.setFormatter(logging.Formatter(config.log_format))
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=config.log_level,
        handlers=handlers,
        format=config.log_format,
    ) 