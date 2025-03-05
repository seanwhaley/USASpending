#!/usr/bin/env python3
"""Transaction CSV to JSON Processor for USASpending data."""
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.usaspending import ConfigManager
from src.usaspending.logging_config import configure_logging, get_logger
from src.usaspending.processor import convert_csv_to_json  # Updated import path
from src.usaspending.fallback_messages import get_fallback_message
from src.usaspending.startup_checks import perform_startup_checks
from src.usaspending import (
    load_json, 
    save_json, 
    get_files, 
    ensure_directory_exists,
    IDataProcessor
)

def load_configuration() -> ConfigManager:
    """Load system configuration from environment or default location."""
    try:
        config_path = os.getenv(
            'USASPENDING_CONFIG',
            str(project_root / 'conversion_config.yaml')
        )
        
        if not Path(config_path).exists():
            error_msg = get_fallback_message('yaml_not_found', path=config_path)
            print(error_msg)
            return None
            
        config = ConfigManager(config_path)
        return config
    except Exception as e:
        error_msg = get_fallback_message('config_load_failed', error=str(e))
        print(error_msg)
        return None

def main() -> int:
    """Main entry point for processing."""
    try:
        # 1. Load configuration first
        config = load_configuration()
        if not config:
            return 1

        # 2. Setup basic logging for startup phase
        # Changed from setup_logging to configure_logging
        if not configure_logging({'system': {'logging': {'level': 'INFO'}}}):
            print("Failed to configure startup logging")
            return 1

        # 3. Perform startup checks and full initialization
        if not perform_startup_checks(config.config):
            return 1

        # 4. Re-configure logging with full config
        # Changed from setup_logging to configure_logging
        if not configure_logging(config):
            print("Failed to configure main logging")
            return 1

        # 5. Get logger only after setup is complete
        logger = get_logger(__name__)
        
        # 6. Process transactions with validated configuration
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
        # Use fallback error handling if logging is not available
        error_msg = get_fallback_message('system_error', error=str(e))
        try:
            logger = get_logger(__name__)
            logger.error(f"ERROR: {error_msg}")
        except:
            print(f"ERROR: {error_msg}")
        return 1

if __name__ == "__main__":
    sys.exit(main())