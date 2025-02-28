#!/usr/bin/env python
"""
Script to run validation on USASpending data.

This script shows how to use the validation framework with process_transactions.py.
"""
import sys
import os
import argparse
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.usaspending.config import load_config, setup_logging
from src.usaspending.processor import convert_csv_to_json

def main():
    """Run validation on USASpending data."""
    parser = argparse.ArgumentParser(description="Run validation on USASpending data")
    parser.add_argument(
        "--config", 
        default="conversion_config.yaml", 
        help="Path to configuration file"
    )
    parser.add_argument(
        "--skip-invalid", 
        action="store_true", 
        help="Skip invalid records instead of failing"
    )
    parser.add_argument(
        "--log-level", 
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO", 
        help="Set the logging level"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("validation.log"),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    
    # Load configuration
    try:
        config = load_config(args.config)
        
        # Override skip_invalid_rows if specified
        if args.skip_invalid:
            if 'contracts' not in config:
                config['contracts'] = {}
            if 'input' not in config['contracts']:
                config['contracts']['input'] = {}
            config['contracts']['input']['skip_invalid_rows'] = True
        
        # Ensure validation is enabled
        if 'contracts' not in config:
            config['contracts'] = {}
        if 'input' not in config['contracts']:
            config['contracts']['input'] = {}
        config['contracts']['input']['validate_input'] = True
        
        # Save modified config if needed
        # (uncomment if you want to save changes)
        # with open(args.config, 'w') as f:
        #     yaml.dump(config, f)
        
        # Run conversion with validation
        logger.info("Starting validation process...")
        success = convert_csv_to_json(args.config)
        
        if success:
            logger.info("Validation and conversion completed successfully!")
            return 0
        else:
            logger.error("Validation and conversion failed!")
            return 1
        
    except Exception as e:
        logger.error(f"Error during validation: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())