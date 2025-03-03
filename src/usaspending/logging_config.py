"""Centralized logging configuration for USASpending."""
import logging
import logging.config
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import yaml

from .file_utils import (
    read_text_file, FileOperationError, FileNotFoundError,
    ensure_directory
)

# Define project root relative to this module
MODULE_DIR = Path(__file__).parent
PROJECT_ROOT = MODULE_DIR.parent.parent

def get_logger(name: str = None) -> logging.Logger:
    """Get a logger instance with the specified name."""
    return logging.getLogger(name if name else '')

def setup_logging(config: Dict[str, Any]) -> bool:
    """Configure logging system from configuration dictionary."""
    try:
        # Get logging configuration using proper path
        log_config = config.get('logging', {})
        
        # Load base logging config
        config_path = PROJECT_ROOT / 'logging_config.yaml'
        if not config_path.exists():
            print(f"Logging config not found: {config_path}")
            return False
            
        with open(config_path, 'r', encoding='utf-8') as f:
            base_config = yaml.safe_load(f)

        # Ensure logs directory exists first
        log_dir = PROJECT_ROOT / 'logs'
        if 'directory' in log_config:
            log_dir = PROJECT_ROOT / log_config['directory']
        
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Failed to create log directory {log_dir}: {e}")
            return False
            
        # Update handler paths with absolute paths
        for handler in base_config['handlers'].values():
            if 'filename' in handler:
                # Convert relative path to absolute
                handler['filename'] = str(log_dir / Path(handler['filename']).name)
                
                # Ensure parent directory exists
                Path(handler['filename']).parent.mkdir(parents=True, exist_ok=True)
        
        # Apply any level overrides from config
        if log_config.get('level'):
            base_config['root']['level'] = log_config['level']
            
            # Also update the src.usaspending logger if it exists
            if 'src.usaspending' in base_config.get('loggers', {}):
                base_config['loggers']['src.usaspending']['level'] = log_config['level']
        
        # Configure logging
        logging.config.dictConfig(base_config)
        
        # Verify configuration worked by attempting to log
        root_logger = logging.getLogger()
        root_logger.info("Logging setup complete")
        return True
        
    except Exception as e:
        print(f"Logging configuration failed: {str(e)}")
        return False

# Keep other functions but simplify their implementation since setup_logging handles most cases
def configure_logging(
    level: str = 'INFO',
    output_file: Optional[str] = None,
    debug_file: Optional[str] = None,
    log_format: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    config_file: Optional[str] = None
) -> None:
    """Legacy method maintained for backwards compatibility."""
    config = {
        'logging': {
            'level': level,
            'directory': str(Path(output_file).parent) if output_file else 'logs'
        }
    }
    setup_logging(config)

def set_logger_level(logger_name: str, level: str) -> None:
    """Set the logging level for a specific logger."""
    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, level.upper()))

def verify_logging_configuration() -> bool:
    """Verify logging is properly configured and files are writable."""
    root_logger = logging.getLogger()
    
    if not root_logger.handlers:
        print("No logging handlers configured")
        return False
    
    # Test file handlers
    file_handlers = [h for h in root_logger.handlers 
                    if isinstance(h, logging.FileHandler)]
    
    for handler in file_handlers:
        try:
            handler.stream.write("")
            handler.stream.flush()
        except Exception as e:
            print(f"Failed to write to log file {handler.baseFilename}: {e}")
            return False
    
    return True