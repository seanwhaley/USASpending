#!/usr/bin/env python3
"""Transaction CSV to JSON Processor for USASpending data."""
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to Python path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.usaspending.config import ConfigManager
from src.usaspending.logging_config import setup_logging, get_logger
from src.usaspending.processor import convert_csv_to_json
from src.usaspending.fallback_messages import get_fallback_message

def test_logging():
    """Test logging configuration."""
    config = {'system': {'logging': {'level': 'INFO'}}}
    if not setup_logging(config):
        print("Failed to configure logging")
        return False
        
    logger = get_logger(__name__)
    logger.debug("Debug test message")
    logger.info("Info test message")
    logger.warning("Warning test message")
    logger.error("Error test message")
    return True

def load_configuration() -> Optional[ConfigManager]:
    """Load system configuration from environment or default location."""
    try:
        config_path = os.getenv(
            'USASPENDING_CONFIG',
            str(project_root / 'conversion_config.yaml')
        )
        config = ConfigManager(config_path)
        return config
    except Exception as e:
        print(f"Configuration error: {str(e)}")
        return None

def main() -> int:
    """Main entry point for processing."""
    # Test logging first
    if not test_logging():
        return 1
        
    try:
        # 1. Load configuration first
        config = load_configuration()
        if not config:
            print("Failed to load configuration")
            return 1

        # 2. Setup logging using configuration BEFORE any logging calls
        system_config = config.get('system', {})
        if not setup_logging(system_config):
            print("Failed to configure logging")
            return 1
            
        # 3. Only get logger after setup is complete
        logger = get_logger(__name__)
        
        # Validate configuration after logging is set up
        system_config = config.get('system')
        if not system_config:
            logger.error("Missing 'system' configuration section")
            return 1
            
        io_config = system_config.get('io')
        if not io_config:
            logger.error("Missing 'system.io' configuration section")
            return 1
            
        input_config = io_config.get('input')
        if not input_config or 'file' not in input_config:
            logger.error("Missing or invalid input file configuration")
            return 1
            
        logger.info("Configuration and logging setup complete")
        
        # 4. Process transactions with validated configuration
        input_file = config.get('system', {}).get('io', {}).get('input', {}).get('file')
        if not input_file:
            logger.error("No input file specified in configuration")
            return 1
            
        logger.info(f"Processing input file: {input_file}")
        if convert_csv_to_json(config):
            logger.info("Processing completed successfully")
            return 0
        
        logger.error("Processing completed with status: failed")
        return 1
        
    except Exception as e:
        # Handle the case where logging might not be set up
        error_msg = get_fallback_message('system_error', error=str(e))
        try:
            logger = get_logger(__name__)
            logger.error(f"ERROR: {error_msg}")
        except:
            print(f"ERROR: {error_msg}")
        return 1

if __name__ == "__main__":
    sys.exit(main())