#!/usr/bin/env python3
"""Convert USASpending Data Dictionary from CSV to JSON format."""
from usaspending.config import load_config, setup_logging
from usaspending.dictionary import csv_to_json

def main():
    """Main entry point for data dictionary conversion."""
    logger = setup_logging(output_file='dictionary_conversion.log',
                         debug_file='dictionary_debug.log')
    
    try:
        # Only load and validate data dictionary section
        config = load_config(section='data_dictionary')
        if csv_to_json(config):
            logger.info("Data dictionary conversion completed successfully")
        else:
            logger.error("Data dictionary conversion failed")
    except Exception as e:
        logger.error(f"Error during conversion: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    main()