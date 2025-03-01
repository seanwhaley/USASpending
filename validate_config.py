#!/usr/bin/env python
"""Command-line tool to validate a USASpending configuration YAML file."""
import argparse
import sys
import json
from pathlib import Path
import colorama
from colorama import Fore, Style

# Add parent directory to path to import local modules
src_dir = Path(__file__).resolve().parent / 'src'
sys.path.insert(0, str(src_dir))

from usaspending.config import load_config
from usaspending.config_validator import ConfigValidationError, get_schema_description
from usaspending.types import ConfigType

def main():
    """Main entry point for the validation script."""
    colorama.init()  # Initialize colorama for colored output
    
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
    
    if args.print_schema:
        schema = get_schema_description(ConfigType)
        print(json.dumps(schema, indent=2))
        return 0
    
    try:
        print(f"{Fore.CYAN}Validating configuration file: {args.config_file}{Style.RESET_ALL}")
        config = load_config(args.config_file)
        print(f"{Fore.GREEN}✓ Configuration is valid!{Style.RESET_ALL}")
        
        if args.verbose:
            print("\nConfiguration sections found:")
            for section in config.keys():
                print(f"  • {section}")
        return 0
        
    except ConfigValidationError as e:
        print(f"{Fore.RED}❌ Configuration validation failed:{Style.RESET_ALL}")
        for error in e.errors:
            print(f"  • {error}")
        return 1
        
    except Exception as e:
        print(f"{Fore.RED}❌ Error: {str(e)}{Style.RESET_ALL}")
        return 1

if __name__ == "__main__":
    sys.exit(main())