#!/usr/bin/env python
"""Configuration validation tool."""
import sys
import argparse
import colorama
from colorama import Fore, Style
import json
from pathlib import Path

# Add src directory to path for importing local modules
src_dir = Path(__file__).resolve().parent / 'src'
sys.path.insert(0, str(src_dir))

from src.usaspending.logging_config import configure_logging, get_logger
from src.usaspending.config_validation import ConfigValidator
from src.usaspending.config_schemas import ROOT_CONFIG_SCHEMA
from src.usaspending.exceptions import ConfigurationError
from src.usaspending.startup_checks import StartupValidator

def main() -> int:
    """Main entry point for the validation script."""
    colorama.init()  # Initialize colorama for colored output
    configure_logging()
    logger = get_logger(__name__)
    logger.info("Starting validation configuration")
    
    parser = argparse.ArgumentParser(
        description="Validate a USASpending configuration YAML file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s config.yaml
  %(prog)s --print-schema config.yaml
  %(prog)s --verbose config.yaml
        """
    )
    parser.add_argument("config_file", help="Path to configuration YAML file")
    parser.add_argument("--print-schema", action="store_true", 
                       help="Print expected schema structure")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Show detailed validation information")
    args = parser.parse_args()
    
    try:
        if args.print_schema:
            print(json.dumps(ROOT_CONFIG_SCHEMA, indent=2))
            return 0
            
        print(f"{Fore.CYAN}Validating configuration file: {args.config_file}{Style.RESET_ALL}")
        
        # Create validator and validate configuration
        validator = ConfigValidator(ROOT_CONFIG_SCHEMA)
        errors = validator.validate_file(args.config_file)
        
        if errors:
            print(f"{Fore.RED}❌ Configuration validation failed:{Style.RESET_ALL}")
            for error in errors:
                print(f"  • [{error.severity.upper()}] {error.path}: {error.message}")
            return 1
            
        # Run startup validation if config validation passed
        startup_validator = StartupValidator(validator)
        if not startup_validator.run_checks():
            print(f"{Fore.RED}❌ Startup validation failed:{Style.RESET_ALL}")
            for message in startup_validator.get_messages():
                print(f"  • {message}")
            return 1
            
        print(f"{Fore.GREEN}✓ Configuration is valid!{Style.RESET_ALL}")
        if args.verbose:
            print("\nConfiguration sections validated:")
            print("  • system")
            print("  • validation_groups")
            print("  • data_dictionary")
            print("  • field_properties")
            print("  • entities")
            print("  • relationships")
            print("  • security")
        return 0
        
    except ConfigurationError as e:
        logger.error("Configuration validation failed", exc_info=True)
        print(f"{Fore.RED}❌ Configuration validation failed: {str(e)}{Style.RESET_ALL}")
        return 1
        
    except Exception as e:
        logger.error("Error occurred", exc_info=True)
        print(f"{Fore.RED}❌ Error: {str(e)}{Style.RESET_ALL}")
        return 1

if __name__ == "__main__":
    sys.exit(main())