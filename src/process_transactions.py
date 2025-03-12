#!/usr/bin/env python
"""Process transactions from input files."""
import os
from pathlib import Path
from typing import Dict, Any, Optional, List

from usaspending.core.config import ComponentConfig
from usaspending.config import ConfigurationProvider as ConfigProvider
from usaspending.core.validation import ValidationService
from usaspending.core.validation_mediator import ValidationMediator
from usaspending.entity_mediator import USASpendingEntityMediator as EntityMediator
from usaspending.entity_mapper import EntityMapper
from usaspending.entity_store import EntityStore
from usaspending.entity_factory import EntityFactory
from usaspending.dictionary import Dictionary
from usaspending.core.exceptions import ConfigurationError
from usaspending.core.utils import safe_operation
from usaspending.core.types import (
    EntityData, ValidationResult, ValidationRule, ValidationSeverity, 
    RuleType, EntityConfig, EntityType
)
from usaspending.core.logging_config import configure_logging, get_logger

# Environment variable name for configuration
CONFIG_ENV_VAR = "USASPENDING_CONFIG"
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "conversion_config.yaml"

logger = get_logger(__name__)

def setup_validation(config: Dict[str, Any]) -> ValidationService:
    """Set up validation components."""
    validation_service = ValidationService(config)
    validation_service.configure(ComponentConfig(settings=config.get('validation', {})))
    return validation_service

def setup_entity_mediator(config: Dict[str, Any], validation_service: ValidationService) -> EntityMediator:
    """Set up entity mediation components."""
    entity_factory = EntityFactory()
    entity_store = EntityStore()
    entity_mapper = EntityMapper()
    
    # Configure components with proper settings structure
    factory_settings = config.get('entity_factory', {})
    factory_settings['entities'] = config.get('entities', {})
    factory_settings['mappings'] = config.get('mappings', {})
    
    entity_factory.configure(ComponentConfig(settings=factory_settings))
    entity_store.configure(ComponentConfig(settings=config.get('entity_store', {})))
    entity_mapper.configure(ComponentConfig(settings=config.get('entity_mapper', {})))
    
    mediator = EntityMediator(
        factory=entity_factory,
        store=entity_store,
        mapper=entity_mapper
    )
    mediator.configure(ComponentConfig(settings=config.get('entity_mediator', {})))

    return mediator

def process_chunk(entity_mediator: EntityMediator, chunk: list[Dict[str, Any]]) -> None:
    """Process a chunk of transaction records."""
    for record in chunk:
        try:
            entity_id = entity_mediator.process_entity(cast(EntityType, 'transaction'), record)
            if not entity_id:
                logger.warning(f"Failed to process transaction: {record.get('contract_transaction_unique_key')}")
        except Exception as e:
            logger.error(f"Error processing transaction {record.get('contract_transaction_unique_key')}: {str(e)}")
            continue

@safe_operation
def process_transactions(config_path: str, input_file: Optional[str] = None) -> None:
    """Process transaction data using configuration."""
    # Load configuration
    config_provider = ConfigProvider()
    config = config_provider.load_config(config_path)

    if not config:
        raise ConfigurationError(f"Failed to load configuration from {config_path}")

    # Override input file if specified
    if input_file:
        config['system']['io']['input']['file'] = input_file

    # Set up components
    validation_service = setup_validation(config)
    entity_mediator = setup_entity_mediator(config, validation_service)

    # Process entities using mediator
    try:
        chunk_size = config.get('processing', {}).get('chunk_size', 1000)
        input_file_path = config['system']['io']['input']['file']

        if not os.path.exists(input_file_path):
            raise FileNotFoundError(f"Input file not found: {input_file_path}")

        processed_count = 0
        try:
            with open(input_file_path, 'r', encoding='utf-8') as f:
                chunk: list[Dict[str, Any]] = []
                for line in f:
                    try:
                        record = json.loads(line)
                        chunk.append(record)
                        
                        if len(chunk) >= chunk_size:
                            process_chunk(entity_mediator, chunk)
                            processed_count += len(chunk)
                            logger.info(f"Processed {processed_count} records")
                            chunk = []  # Clear the chunk
                            

                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON in line: {e}")
                        continue

                # Process remaining records
                if chunk:
                    process_chunk(entity_mediator, chunk)
                    processed_count += len(chunk)
                    logger.info(f"Processed {processed_count} total records")

        except Exception as e:
            logger.error(f"Processing failed: {str(e)}")
            raise

    finally:
        # Clean up resources
        entity_mediator.cleanup()

def get_config_path(cli_config: Optional[str] = None) -> str:
    """
    Get configuration file path based on priority:
    1. Command line argument
    2. Environment variable
    3. Default in-code path
    """
    if cli_config and os.path.exists(cli_config):
        return cli_config
        
    env_config = os.getenv(CONFIG_ENV_VAR)
    if env_config and os.path.exists(env_config):
        return env_config
        
    if os.path.exists(DEFAULT_CONFIG_PATH):
        return str(DEFAULT_CONFIG_PATH)
        
    raise ConfigurationError(
        f"No valid configuration file found. Checked:\n"
        f"  - CLI argument: {cli_config or 'Not provided'}\n"
        f"  - Environment variable {CONFIG_ENV_VAR}: {env_config or 'Not set'}\n"
        f"  - Default path: {DEFAULT_CONFIG_PATH}"
    )

def main() -> None:
    """Main entry point."""
    colorama.init()
    
    parser = argparse.ArgumentParser(description="Process USASpending transaction data")
    parser.add_argument('--config', help=f'Path to configuration file (default: {DEFAULT_CONFIG_PATH})')
    parser.add_argument('--input', help='Input file path (overrides config)')
    args = parser.parse_args()

    try:
        config_path = get_config_path(args.config)
        process_transactions(config_path, args.input)
        print(f"{Fore.GREEN}Processing completed successfully{Style.RESET_ALL}")

    except Exception as e:
        print(f"{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")
        sys.exit(1)

if __name__ == '__main__':
    main()