#!/usr/bin/env python3
"""Converts USASpending data dictionary to internal format."""
import csv
from pathlib import Path
from usaspending.config import ConfigManager
from usaspending.logging_config import configure_logging, get_logger

def convert_dictionary(input_path: str, output_path: str) -> None:
    """Convert data dictionary from CSV to internal format."""
    try:
        config_manager = ConfigManager('config/data_dictionary.yaml')
        config = config_manager.config.get('data_dictionary', {})
        # Only load and validate data dictionary section
        if csv_to_json(config):
            logger.info("Data dictionary conversion completed successfully")
        else:
            logger.error("Data dictionary conversion failed")
    except Exception as e:
        logger.error(f"Error during conversion: {str(e)}")
        return False
    
    return True

def main():
    """Main entry point for data dictionary conversion."""
    # Initialize logging
    configure_logging(
        output_file='dictionary_conversion.log',
        debug_file='dictionary_debug.log'
    )
    
    logger = get_logger(__name__)
    
    input_path = 'path/to/input.csv'
    output_path = 'path/to/output.json'
    convert_dictionary(input_path, output_path)

if __name__ == "__main__":
    main()