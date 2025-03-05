#!/usr/bin/env python
"""Main entry point for USASpending data processing."""
import os
import sys
from pathlib import Path
import logging.config
import argparse
import colorama
from colorama import Fore, Style

# Add src directory to path for importing local modules
src_dir = Path(__file__).resolve().parent / 'src'
sys.path.insert(0, str(src_dir))

from src.usaspending.logging_config import configure_logging, get_logger
from src.usaspending.config_validation import ConfigValidator
from src.usaspending.config_schemas import ROOT_CONFIG_SCHEMA
from src.usaspending.startup_checks import StartupValidator
from src.usaspending.exceptions import ConfigurationError
from src.usaspending.processor import convert_csv_to_json
from src.usaspending.fallback_messages import print_error
from src.usaspending.config import ConfigManager

def main() -> int:
    """Main entry point for data processing."""
    colorama.init()  # Initialize colorama for colored output
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Process USASpending transaction data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s
  %(prog)s custom_config.yaml
  %(prog)s --verbose conversion_config.yaml
        """
    )
    parser.add_argument("config_file", nargs='?', default="conversion_config.yaml",
                       help="Path to configuration YAML file (default: conversion_config.yaml)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Show detailed processing information")
    args = parser.parse_args()
    
    try:
        # Set up logging with explicit config file path
        logging_config_path = Path(__file__).resolve().parent / "logging_config.yaml"
        configure_logging(str(logging_config_path))
        logger = get_logger(__name__)
        logger.info("Starting USASpending data processing")
        
        # Create and validate configuration
        validator = ConfigValidator(ROOT_CONFIG_SCHEMA)
        errors = validator.validate_file(args.config_file)
        
        if errors:
            print(f"{Fore.RED}Configuration validation failed:{Style.RESET_ALL}")
            for error in errors:
                print(f"  • [{error.severity.upper()}] {error.path}: {error.message}")
            return 1
            
        # Run startup validation
        startup_validator = StartupValidator(validator)
        if not startup_validator.run_checks():
            print(f"{Fore.RED}Startup validation failed:{Style.RESET_ALL}")
            for message in startup_validator.get_messages():
                print(f"  • {message}")
            return 1
            
        # Process data with validated configuration using component context
        with validator.component_context() as config:
            result = convert_csv_to_json(config)
            
        if result:
            print(f"{Fore.GREEN}✓ Processing completed successfully!{Style.RESET_ALL}")
            return 0
        else:
            print(f"{Fore.RED}✗ Processing failed{Style.RESET_ALL}")
            return 1
            
    except ConfigurationError as e:
        print_error(f"Configuration error: {str(e)}")
        logger.error("Configuration error", exc_info=True)
        return 1
        
    except Exception as e:
        print_error(f"Unexpected error: {str(e)}")
        logger.error("Processing failed", exc_info=True)
        return 1
        
    finally:
        logging.shutdown()

if __name__ == "__main__":
    sys.exit(main())