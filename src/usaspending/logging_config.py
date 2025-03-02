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

def get_logger(name: str = None) -> logging.Logger:
    """Get a logger instance with the specified name.
    
    Args:
        name: The name for the logger. If None, returns the root logger.
    
    Returns:
        A configured logger instance
    """
    return logging.getLogger(name if name else '')

def configure_logging(
    level: str = 'INFO',
    output_file: Optional[str] = None,
    debug_file: Optional[str] = None,
    log_format: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    config_file: Optional[str] = None
) -> None:
    """Configure the logging system.
    
    Args:
        level: The base logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        output_file: Path to the main log file
        debug_file: Path to the debug log file (will capture DEBUG level)
        log_format: Format string for log messages
        config_file: Path to a YAML config file for more detailed configuration
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # If config file is provided, use it for configuration
    if config_file and Path(config_file).exists():
        try:
            config_content = read_text_file(config_file, encoding='utf-8')
            config = yaml.safe_load(config_content)
            logging.config.dictConfig(config)
            return
        except (FileNotFoundError, FileOperationError) as e:
            print(f"Error loading logging config file: {str(e)}")
            # Fall back to basic configuration
        except yaml.YAMLError as e:
            print(f"Error parsing logging config YAML: {str(e)}")
            # Fall back to basic configuration

    formatter = logging.Formatter(log_format)
    
    # Console handler (always added)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Main log file
    if output_file:
        try:
            # Create directory for log file if needed
            log_dir = Path(output_file).parent
            if not log_dir.exists():
                ensure_directory(str(log_dir))
            file_handler = logging.FileHandler(output_file)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except (FileOperationError, OSError) as e:
            print(f"Error setting up log file {output_file}: {str(e)}")
    
    # Debug log file
    if debug_file:
        try:
            # Create directory for debug log if needed
            debug_dir = Path(debug_file).parent
            if not debug_dir.exists():
                ensure_directory(str(debug_dir))
            debug_handler = logging.FileHandler(debug_file)
            debug_handler.setLevel(logging.DEBUG)
            debug_handler.setFormatter(formatter)
            root_logger.addHandler(debug_handler)
        except (FileOperationError, OSError) as e:
            print(f"Error setting up debug log file {debug_file}: {str(e)}")

def set_logger_level(logger_name: str, level: str) -> None:
    """Set the logging level for a specific logger.
    
    Args:
        logger_name: Name of the logger to configure
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, level.upper()))