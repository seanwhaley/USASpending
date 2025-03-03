#!/usr/bin/env python3
"""
Transaction CSV to JSON Processor for USASpending data.

This script serves as the main entry point for converting USASpending 
transaction data from CSV format to structured JSON with entity separation.
"""
import sys
import argparse
from pathlib import Path

# Add the project root to the Python path to allow module imports
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.usaspending.config import ConfigManager
from src.usaspending.logging_config import configure_logging, get_logger
from src.usaspending.processor import convert_csv_to_json
from src.usaspending.fallback_messages import get_fallback_message

logger = get_logger(__name__)

def main() -> int:
    """Main entry point for the transaction CSV to JSON processor."""
    try:
        parser = argparse.ArgumentParser(
            description="Convert USASpending transaction data from CSV to JSON format",
            formatter_class=argparse.RawDescriptionHelpFormatter
        )
        parser.add_argument(
            "--config",
            default="conversion_config.yaml",
            help="Path to configuration file (default: conversion_config.yaml)"
        )
        parser.add_argument(
            "--log-file",
            help="Path to output log file"
        )
        parser.add_argument(
            "--debug-file",
            help="Path to debug log file"
        )
        parser.add_argument(
            "--log-level",
            default="INFO",
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            help="Logging level"
        )
        parser.add_argument(
            "-v", "--verbose",
            action="store_true",
            help="Enable verbose output (same as --log-level DEBUG)"
        )
        
        args = parser.parse_args()
        
        # Initialize logging first
        configure_logging(
            level="DEBUG" if args.verbose else args.log_level,
            output_file=args.log_file,
            debug_file=args.debug_file
        )
        
        logger.info("Starting USASpending transaction processing")
        
        # Initialize config manager with the specified config file
        config_manager = ConfigManager(args.config)
        
        # Process transactions using the ConfigManager instance directly
        if convert_csv_to_json(config_manager):
            logger.info("Processing completed successfully")
            return 0
        
        logger.error("Processing completed with status: failed")
        return 1
            
    except Exception as e:
        logger.error(get_fallback_message('system_error', error=str(e)))
        logger.debug("Stack trace:", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())