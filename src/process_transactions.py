#!/usr/bin/env python
"""
Transaction data processor and validator.
"""
import sys
import os
import argparse
import colorama
from colorama import Fore, Style
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from usaspending.logging_config import configure_logging, get_logger
from usaspending.config import ConfigManager
from usaspending.config_validation import ConfigValidator
from usaspending.config_schemas import ROOT_CONFIG_SCHEMA
from usaspending.exceptions import ConfigurationError
from usaspending.startup_checks import StartupValidator
from usaspending.processor import convert_csv_to_json
from usaspending.validation import validate_data

# Environment variable name for configuration
CONFIG_ENV_VAR = "CONVERSION_CONFIG"
DEFAULT_CONFIG = "conversion_config.yaml"

def get_config_path(cmd_arg=None):
    """
    Determine the configuration file path using precedence order:
    1. Command line argument (if provided)
    2. Environment variable (if set)
    3. Default value
    
    Args:
        cmd_arg: Command line argument value (if provided)
        
    Returns:
        Path to configuration file
    """
    if cmd_arg:
        # Command line argument takes highest precedence
        return cmd_arg
    
    # Check environment variable
    env_config = os.environ.get(CONFIG_ENV_VAR)
    if (env_config):
        return env_config
        
    # Fall back to default
    return DEFAULT_CONFIG

def validate_configuration(config_path, verbose=False):
    """Validate configuration file."""
    logger = get_logger(__name__)
    logger.info(f"Validating configuration file: {config_path}")
    
    print(f"{Fore.CYAN}Validating configuration file: {config_path}{Style.RESET_ALL}")
    
    # Create validator and validate configuration
    validator = ConfigValidator(ROOT_CONFIG_SCHEMA)
    errors = validator.validate_file(config_path)
    
    if errors:
        print(f"{Fore.RED}❌ Configuration validation failed:{Style.RESET_ALL}")
        for error in errors:
            print(f"  • [{error.severity.upper()}] {error.path}: {error.message}")
        return False
        
    # Run startup validation if config validation passed
    startup_validator = StartupValidator(validator)
    if not startup_validator.run_checks():
        print(f"{Fore.RED}❌ Startup validation failed:{Style.RESET_ALL}")
        for message in startup_validator.get_messages():
            print(f"  • {message}")
        return False
        
    print(f"{Fore.GREEN}✓ Configuration is valid!{Style.RESET_ALL}")
    if verbose:
        print("\nConfiguration sections validated:")
        print("  • system")
        print("  • validation_groups")
        print("  • data_dictionary")
        print("  • field_properties")
        print("  • entities")
        print("  • relationships")
        print("  • security")
    return True

def run_data_validation(config_path, skip_invalid=False):
    """Run validation on USASpending data."""
    logger = get_logger(__name__)
    logger.info("Starting data validation")
    
    try:
        config_manager = ConfigManager(config_path)
        config = config_manager.config
        
        # Override skip_invalid_rows if specified
        if skip_invalid:
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
        
        # Run validation
        logger.info("Starting validation process...")
        success = validate_data(config)
        
        if success:
            logger.info("Validation completed successfully!")
            print(f"{Fore.GREEN}✓ Data validation completed successfully!{Style.RESET_ALL}")
            return True
        else:
            logger.error("Validation failed!")
            print(f"{Fore.RED}❌ Data validation failed!{Style.RESET_ALL}")
            return False
        
    except Exception as e:
        logger.error(f"Error during validation: {str(e)}", exc_info=True)
        print(f"{Fore.RED}❌ Error during validation: {str(e)}{Style.RESET_ALL}")
        return False

def main() -> int:
    """Process USASpending transaction data."""
    colorama.init()  # Initialize colorama for colored output
    
    parser = argparse.ArgumentParser(description="Process and validate USASpending data")
    parser.add_argument(
        "--config", 
        default=None,  # Changed from hardcoded default to None
        help=f"Path to configuration file (overrides {CONFIG_ENV_VAR} environment variable and default '{DEFAULT_CONFIG}')"
    )
    
    # Validation arguments
    validation_group = parser.add_argument_group('Validation Options')
    validation_group.add_argument(
        "--validate-config-only", 
        action="store_true", 
        help="Only validate configuration file without processing data"
    )
    validation_group.add_argument(
        "--validate-data-only", 
        action="store_true", 
        help="Only validate data without processing"
    )
    validation_group.add_argument(
        "--skip-validation", 
        action="store_true", 
        help="Skip all validation checks and proceed with processing"
    )
    validation_group.add_argument(
        "--skip-invalid", 
        action="store_true", 
        help="Skip invalid records instead of failing"
    )
    validation_group.add_argument(
        "--print-schema", 
        action="store_true", 
        help="Print expected schema structure and exit"
    )
    validation_group.add_argument(
        "--verbose", "-v", 
        action="store_true",
        help="Show detailed validation information"
    )
    
    # Logging arguments
    logging_group = parser.add_argument_group('Logging Options')
    logging_group.add_argument(
        "--log-level", 
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO", 
        help="Set the logging level"
    )
    logging_group.add_argument('--log-file', help='Path to log file')
    logging_group.add_argument('--debug-file', help='Path to debug log file')
    
    args = parser.parse_args()
    
    # Determine config path using precedence order
    config_path = get_config_path(args.config)
    
    # Initialize logging before any other operations
    configure_logging(
        level=args.log_level,
        output_file=args.log_file,
        debug_file=args.debug_file
    )
    
    logger = get_logger(__name__)
    logger.info(f"Starting USASpending data processing with config: {config_path}")
    
    try:
        # Handle print schema request
        if args.print_schema:
            print(json.dumps(ROOT_CONFIG_SCHEMA, indent=2))
            return 0
            
        # Validate configuration first
        config_valid = True
        if not args.skip_validation:
            config_valid = validate_configuration(config_path, args.verbose)
            if not config_valid and not args.validate_config_only:
                logger.error("Configuration validation failed, aborting")
                return 1
        
        # Exit if only validating config
        if args.validate_config_only:
            return 0 if config_valid else 1
            
        # Validate data if requested
        if args.validate_data_only and not args.skip_validation:
            data_valid = run_data_validation(config_path, args.skip_invalid)
            return 0 if data_valid else 1
        
        # Otherwise process the data
        logger.info("Starting data processing...")
        
        # Apply configuration overrides
        config_manager = ConfigManager(config_path)
        config = config_manager.config
        
        # Enable validation unless explicitly skipped
        if not args.skip_validation:
            if 'contracts' not in config:
                config['contracts'] = {}
            if 'input' not in config['contracts']:
                config['contracts']['input'] = {}
            config['contracts']['input']['validate_input'] = True
            config['contracts']['input']['skip_invalid_rows'] = args.skip_invalid
        
        # Process the data
        success = convert_csv_to_json(config_manager)
        
        if success:
            logger.info("Data processing completed successfully")
            print(f"{Fore.GREEN}✓ Data processing completed successfully!{Style.RESET_ALL}")
            return 0
        else:
            logger.error("Data processing failed")
            print(f"{Fore.RED}❌ Data processing failed!{Style.RESET_ALL}")
            return 1
            
    except ConfigurationError as e:
        logger.error("Configuration error", exc_info=True)
        print(f"{Fore.RED}❌ Configuration error: {str(e)}{Style.RESET_ALL}")
        return 1
        
    except Exception as e:
        logger.error("Error occurred", exc_info=True)
        print(f"{Fore.RED}❌ Error: {str(e)}{Style.RESET_ALL}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

"""Process transactions module for USASpending data."""

def process_transaction(transaction_data):
    """Process a single transaction."""
    pass

def process_transactions(transactions_data):
    """Process multiple transactions."""
    return [process_transaction(t) for t in transactions_data]