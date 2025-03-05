"""Logging configuration for USASpending data processing."""
import os
import sys
import logging
from typing import Dict, Any, Optional

def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance for the given name.
    
    Args:
        name: Logger name, typically __name__
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)

def configure_logging(config: Dict[str, Any]) -> bool:
    """Configure logging based on configuration settings.
    
    Args:
        config: Configuration dictionary containing logging settings
        
    Returns:
        True if logging was configured successfully, False otherwise
    """
    try:
        log_level = config.get('system', {}).get('logging', {}).get('level', 'INFO')
        log_file = config.get('system', {}).get('logging', {}).get('file')
        log_format = config.get('system', {}).get('logging', {}).get(
            'format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        handlers = []
        
        # Always add console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(console_handler)
        
        # Add file handler if specified
        if log_file:
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
                
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(logging.Formatter(log_format))
            handlers.append(file_handler)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper()))
        
        # Remove any existing handlers
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)
            
        # Add new handlers
        for handler in handlers:
            root_logger.addHandler(handler)
            
        return True
        
    except Exception as e:
        print(f"Error configuring logging: {str(e)}")
        return False

# Removed backward compatibility alias: setup_logging = configure_logging

# Initialize basic logging for module imports
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)