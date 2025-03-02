#!/usr/bin/env python
"""
Data validation runner.
"""
import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.usaspending.logging_config import configure_logging, get_logger
from src.usaspending.validation import validate_data
from src.usaspending.config import ConfigManager

def main() -> int:
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
    parser.add_argument('--log-file', help='Path to log file')
    parser.add_argument('--debug-file', help='Path to debug log file')
    
    args = parser.parse_args()
    
    # Initialize logging before any other operations
    configure_logging(
        level=args.log_level,
        output_file=args.log_file,
        debug_file=args.debug_file
    )
    
    logger = get_logger(__name__)
    logger.info("Starting data validation")
    
    try:
        config_manager = ConfigManager(args.config)
        config = config_manager.config
        
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
        
        # Run validation
        logger.info("Starting validation process...")
        success = validate_data(config)
        
        if success:
            logger.info("Validation completed successfully!")
            return 0
        else:
            logger.error("Validation failed!")
            return 1
        
    except Exception as e:
        logger.error(f"Error during validation: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())