#!/usr/bin/env python3
"""
Transaction CSV to JSON Processor for USASpending data.

This script serves as the main entry point for converting USASpending 
transaction data from CSV format to structured JSON with entity separation.
"""
import sys
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

# Add the project root to the Python path to allow module imports
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.usaspending.config import setup_logging
from src.usaspending.processor import convert_csv_to_json

# Create a logger for this module
logger = logging.getLogger('usaspending')

def main() -> int:
    """Main entry point for the transaction CSV to JSON processor."""
    try:
        # Load environment variables
        load_dotenv()
        
        # Setup logging using environment variables
        setup_logging()
        logger.info("Starting USASpending transaction processing")
        
        # Get config file path from environment
        config_file = os.getenv('CONFIG_FILE')
        if not config_file:
            logger.error("CONFIG_FILE environment variable not set")
            return 1
        
        # Run conversion process
        success = convert_csv_to_json(config_file)
        if success:
            logger.info("Conversion completed successfully")
            return 0
        else:
            logger.error("Conversion failed")
            return 1
            
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        logger.debug("Stack trace:", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())