"""Logging configuration system."""
import os
import sys
import logging
import logging.config
import yaml
from pathlib import Path
from threading import Lock
from typing import Optional

# Default basic logging format for early initialization
DEFAULT_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
DEFAULT_LEVEL = logging.INFO

# Global state
_logging_initialized = False
_logging_lock = Lock()

def configure_logging(config_file: Optional[str] = None) -> None:
    """Configure logging system.
    
    Args:
        config_file: Optional path to logging configuration file
    """
    global _logging_initialized
    
    with _logging_lock:
        if _logging_initialized:
            return
            
        try:
            if config_file:
                _configure_from_file(config_file)
            else:
                # Basic configuration if no file provided
                logging.basicConfig(
                    format=DEFAULT_FORMAT,
                    level=DEFAULT_LEVEL
                )
            
            _logging_initialized = True
            
        except Exception as e:
            # Fallback to basic configuration
            logging.basicConfig(
                format=DEFAULT_FORMAT,
                level=DEFAULT_LEVEL
            )
            logging.error(f"Error configuring logging: {str(e)}")

def _configure_from_file(config_file: str) -> None:
    """Configure logging from configuration file."""
    try:
        path = Path(config_file)
        if not path.exists():
            raise FileNotFoundError(f"Logging config file not found: {config_file}")
            
        with open(path) as f:
            config = yaml.safe_load(f)
            
        # Ensure log directory exists for file handlers
        _ensure_log_directories(config)
            
        # Apply configuration
        logging.config.dictConfig(config)
        
    except Exception as e:
        raise RuntimeError(f"Failed to configure logging: {str(e)}")

def _ensure_log_directories(config: dict) -> None:
    """Ensure log directories exist for file handlers."""
    handlers = config.get('handlers', {})
    for handler in handlers.values():
        if 'filename' in handler:
            log_path = Path(handler['filename'])
            log_path.parent.mkdir(parents=True, exist_ok=True)

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance.
    
    Args:
        name: Logger name, typically __name__
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)