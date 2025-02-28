"""Configuration handling module."""
import logging
import sys
import os
from pathlib import Path
from typing import Any, Dict, TypedDict, cast, Optional, Literal, Union
import yaml
from dotenv import load_dotenv

from .types import (
    ConfigType, TypeConversionConfig, ChunkingConfig,
    InputConfig, OutputConfig
)

# Load environment variables
load_dotenv()

class GlobalConfig(TypedDict):
    """Global configuration section."""
    encoding: str
    date_format: str
    datetime_format: str
    environment: Optional[str]  # Added missing optional field

class ContractsConfig(TypedDict, total=False):  # Made fields optional
    """Contracts configuration section."""
    input: InputConfig
    output: OutputConfig
    chunking: ChunkingConfig
    type_conversion: TypeConversionConfig
    entity_separation: Dict[str, Any] 
    field_categories: Dict[str, list[str]]
    entity_save_frequency: int  # Re-add type definition
    incremental_save: bool     # Re-add type definition

def _get_env_bool(key: str, default: bool = False) -> bool:
    """Convert environment variable to boolean."""
    value = os.getenv(key, str(default)).lower()
    return value in ('true', '1', 't', 'yes', 'y')

def _get_env_int(key: str, default: int) -> int:
    """Convert environment variable to integer."""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default

def setup_logging(output_file: Optional[str] = None, debug_file: Optional[str] = None) -> logging.Logger:
    """Setup logging configuration."""
    logger = logging.getLogger('usaspending')
    
    # Get log level from environment
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    logger.setLevel(getattr(logging, log_level))
    
    # Use environment variables for log files if not provided
    output_file = output_file or os.getenv('CONVERSION_LOG', 'conversion.log')
    debug_file = debug_file or os.getenv('DEBUG_LOG', 'debug.log')
    
    # Console handler with INFO level
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    console.setFormatter(console_formatter)
    logger.addHandler(console)
    
    # File handler for general logs
    if output_file is not None:
        file_handler = logging.FileHandler(output_file)
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    # Debug file handler
    if debug_file is not None:
        debug_handler = logging.FileHandler(debug_file)
    debug_handler.setLevel(logging.DEBUG)
    debug_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(funcName)s - %(message)s'
    )
    debug_handler.setFormatter(debug_formatter)
    logger.addHandler(debug_handler)
    
    return logger

def validate_contracts_config(config: Dict[str, Any]) -> bool:
    """Validate contracts configuration section."""
    try:
        if 'contracts' not in config:
            raise ValueError("Missing required section 'contracts'")
            
        contracts = config['contracts']
        
        # Validate save frequency - Fixed validation
        entity_save_frequency = contracts.get('entity_save_frequency')
        if entity_save_frequency is None:
            contracts['entity_save_frequency'] = 1000  # Default to 1000 records
        elif not isinstance(entity_save_frequency, int) or entity_save_frequency <= 0:
            raise ValueError("entity_save_frequency must be a positive integer")

        # Add incremental save option with default
        if 'incremental_save' not in contracts:
            contracts['incremental_save'] = True

        # Validate required sections
        required_sections = ['input', 'output', 'chunking', 'type_conversion']
        missing_sections = [section for section in required_sections 
                          if section not in contracts]
        if missing_sections:
            raise ValueError(f"Missing required section 'contracts.{missing_sections[0]}'")
        
        # Validate input settings
        input_config = contracts['input']
        if not isinstance(input_config['file'], str):
            raise ValueError("input.file must be a string")
        if not isinstance(input_config.get('batch_size'), int):
            raise ValueError("input.batch_size must be an integer")
        if input_config.get('batch_size', 0) <= 0:
            raise ValueError("batch_size must be greater than 0")
            
        # Validate type conversion configuration
        validate_type_conversion_config(contracts['type_conversion'])
            
        # Validate entity separation config if enabled
        if contracts.get('entity_separation', {}).get('enabled', False):
            validate_entity_config(contracts['entity_separation'])
        
        # Validate field categories
        if 'field_categories' in contracts:
            validate_field_categories(contracts['field_categories'])
        
        return True
        
    except KeyError as e:
        key = str(e).strip("'")
        raise ValueError(f"Missing required section 'contracts.{key}'")
    except (TypeError, ValueError) as e:
        raise ValueError(f"Invalid configuration: {str(e)}")
    except Exception as e:
        raise ValueError(f"Unexpected error validating contracts config: {str(e)}")

def validate_entity_config(entity_config: Dict[str, Any]) -> None:
    """Validate entity separation configuration."""
    if not isinstance(entity_config, dict):
        raise ValueError("Entity configuration must be a dictionary")
        
    if 'entities' not in entity_config and not entity_config.get('enabled', False):
        return  # Entity separation is disabled, no further validation needed
        
    if 'entities' not in entity_config:
        raise ValueError("Entity separation enabled but no entities configured")
        
    entities = entity_config['entities']
    if not isinstance(entities, dict):
        raise ValueError("Entities configuration must be a dictionary")
    
    for entity_type, config in entities.items():
        if not isinstance(config, dict):
            raise ValueError(f"Invalid configuration for entity type {entity_type}")
        
        # Validate entity configurations
        if 'levels' in config:
            validate_hierarchical_entity(entity_type, config)
        else:
            validate_regular_entity(entity_type, config)
        
        # Validate relationships if present
        if 'relationships' in config:
            if not isinstance(config['relationships'], (dict, list)):
                raise ValueError(f"Invalid relationships format for {entity_type}")
            validate_relationships(entity_type, config['relationships'])

def validate_hierarchical_entity(entity_type: str, config: Dict[str, Any]) -> None:
    """Validate hierarchical entity configuration."""
    for level_name, level_config in config['levels'].items():
        if not isinstance(level_config, dict):
            raise ValueError(f"Invalid level configuration for {entity_type}.{level_name}")
        if 'field_mappings' not in level_config:
            raise ValueError(f"Missing field_mappings for {entity_type}.{level_name}")
        if 'key_fields' not in level_config:
            raise ValueError(f"Missing key_fields for {entity_type}.{level_name}")

def validate_regular_entity(entity_type: str, config: Dict[str, Any]) -> None:
    """Validate regular entity configuration."""
    if not config.get('field_mappings') and not config.get('key_fields'):
        raise ValueError(f"Entity type {entity_type} must have either field_mappings or key_fields defined")

def validate_relationships(entity_type: str, relationships: Union[Dict[str, Any], list[Any]]) -> None:
    """Validate relationship configurations."""
    if isinstance(relationships, dict):
        for rel_type, rel_configs in relationships.items():
            if not isinstance(rel_configs, list):
                raise ValueError(f"Relationship configurations for {entity_type}.{rel_type} must be a list")
            for rel_config in rel_configs:
                validate_relationship_config(entity_type, rel_type, rel_config)
    elif isinstance(relationships, list):
        for rel_config in relationships:
            validate_relationship_config(entity_type, None, rel_config)
    else:
        raise ValueError(f"Invalid relationships format for {entity_type}")

def validate_relationship_config(entity_type: str, rel_type: Optional[str], 
                              rel_config: Dict[str, Any]) -> None:
    """Validate a single relationship configuration."""
    # For hierarchical relationships
    if rel_type == 'hierarchical':
        required = ['from_level', 'to_level', 'type']
    else:
        required = ['from_field', 'to_field', 'type']
    
    missing = [field for field in required if field not in rel_config]
    if missing:
        context = f"{entity_type}.{rel_type}" if rel_type else entity_type
        raise ValueError(f"Relationship in {context} missing {', '.join(missing)} fields")

def validate_field_categories(categories: Dict[str, Any]) -> None:
    """Validate field category configuration."""
    if not isinstance(categories, dict):
        raise ValueError("Field categories must be a dictionary")
    for category, fields in categories.items():
        if not isinstance(category, str):
            raise ValueError(f"Category name must be a string: {category}")
        if not isinstance(fields, list):
            raise ValueError(f"Fields for category {category} must be a list")
        if not all(isinstance(f, str) for f in fields):
            raise ValueError(f"All fields in category {category} must be strings")

def validate_type_conversion_config(type_config: Dict[str, Any]) -> None:
    """Validate type conversion configuration section."""
    if not isinstance(type_config, dict):
        raise ValueError("Type conversion config must be a dictionary")

    # Validate date fields
    date_fields = type_config.get('date_fields', [])
    if not isinstance(date_fields, list):
        raise ValueError("date_fields must be a list")
    if not all(isinstance(f, str) for f in date_fields):
        raise ValueError("All date fields must be strings")

    # Validate numeric fields
    numeric_fields = type_config.get('numeric_fields', [])
    if not isinstance(numeric_fields, list):
        raise ValueError("numeric_fields must be a list")
    if not all(isinstance(f, str) for f in numeric_fields):
        raise ValueError("All numeric fields must be strings")

    # Validate boolean fields - Added validation
    boolean_fields = type_config.get('boolean_fields', [])
    if not isinstance(boolean_fields, list):
        raise ValueError("boolean_fields must be a list")
    if not all(isinstance(f, str) for f in boolean_fields):
        raise ValueError("All boolean fields must be strings")

    # Validate boolean values
    value_mapping = type_config.get('value_mapping', {})
    for field in ['true_values', 'false_values']:
        values = value_mapping.get(field, [])
        if not isinstance(values, list):
            raise ValueError(f"{field} must be a list")
        if not all(isinstance(v, str) for v in values):
            raise ValueError(f"All {field} must be strings")

    # Validate no overlap between field types
    all_fields = set(date_fields) | set(numeric_fields) | set(boolean_fields)
    if len(all_fields) != len(date_fields) + len(numeric_fields) + len(boolean_fields):
        raise ValueError("Fields cannot be configured for multiple types")

def validate_data_dictionary_config(config: Dict[str, Any]) -> bool:
    """Validate data dictionary configuration section."""
    try:
        dict_config = config['data_dictionary']
        
        # Validate required sections exist
        required_sections = ['input', 'output', 'parsing']
        for section in required_sections:
            if section not in dict_config:
                raise ValueError(f"Missing required section: {section}")
        
        # Validate input configuration
        input_cfg = dict_config['input']
        if not isinstance(input_cfg.get('file'), str):
            raise ValueError("input.file must be a string")
        if not isinstance(input_cfg.get('required_columns', []), list):
            raise ValueError("input.required_columns must be a list")
        
        # Validate output configuration
        output_cfg = dict_config['output']
        if not isinstance(output_cfg.get('file'), str):
            raise ValueError("output.file must be a string")
            
        # Validate parsing configuration
        parsing_cfg = dict_config['parsing']
        if not isinstance(parsing_cfg.get('preserve_newlines_for', []), list):
            raise ValueError("parsing.preserve_newlines_for must be a list")
            
        return True
        
    except KeyError as e:
        raise ValueError(f"Missing required configuration field: {e}")
    except TypeError as e:
        raise ValueError(f"Invalid configuration type: {e}")

def load_config(config_file: str = '../conversion_config.yaml',
               section: Optional[Literal['contracts', 'data_dictionary']] = None) -> ConfigType:
    """Load and validate configuration from YAML file and environment variables."""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # Apply environment variable overrides to global section
        config['global'].update({
            'encoding': os.getenv('FILE_ENCODING', config['global']['encoding']),
            'date_format': os.getenv('DATE_FORMAT', config['global']['date_format']),
            'datetime_format': os.getenv('DATETIME_FORMAT', config['global']['datetime_format']),
            'error_handling': {
                'max_retries': _get_env_int('MAX_RETRIES', config['global']['error_handling']['max_retries']),
                'log_errors': _get_env_bool('LOG_ERRORS', config['global']['error_handling']['log_errors'])
            },
            'log_frequency': _get_env_int('LOG_FREQUENCY', config['global']['log_frequency'])
        })

        # Apply environment variable overrides to contracts section
        if 'contracts' in config:
            # Preserve existing type_conversion and other configs
            existing_config = config['contracts'].copy()
            
            # Update only the sections that should be overridden by env vars
            env_updates = {
                'input': {
                    'file': os.getenv('INPUT_FILE', existing_config['input']['file']),
                    'batch_size': _get_env_int('BATCH_SIZE', existing_config['input']['batch_size']),
                    'validate_input': _get_env_bool('VALIDATE_INPUT', existing_config['input']['validate_input']),
                    'skip_invalid_rows': _get_env_bool('SKIP_INVALID_ROWS', existing_config['input']['skip_invalid_rows'])
                },
                'output': {
                    'directory': os.getenv('OUTPUT_DIR', existing_config['output']['directory']),
                    'main_file': os.getenv('TRANSACTION_FILE', existing_config['output']['main_file']),
                    'indent': _get_env_int('JSON_INDENT', existing_config['output']['indent']),
                    'ensure_ascii': _get_env_bool('ENSURE_ASCII', existing_config['output']['ensure_ascii'])
                },
                'chunking': {
                    'enabled': True,  # Always enabled
                    'records_per_chunk': _get_env_int('RECORDS_PER_CHUNK', existing_config['chunking']['records_per_chunk']),
                    'create_index': True,  # Always enabled
                    'max_chunk_size_mb': _get_env_int('MAX_CHUNK_SIZE_MB', existing_config['chunking']['max_chunk_size_mb'])
                },
                'entity_save_frequency': _get_env_int('ENTITY_SAVE_FREQUENCY', existing_config['entity_save_frequency']),
                'incremental_save': _get_env_bool('INCREMENTAL_SAVE', existing_config['incremental_save'])
            }
            
            # Update the config while preserving other sections
            existing_config.update(env_updates)
            config['contracts'] = existing_config

        # Validate configuration based on section
        if section == 'contracts' or section is None:
            validate_contracts_config(config)
        if section == 'data_dictionary' or section is None:
            validate_data_dictionary_config(config)
            
        return cast(ConfigType, config)
        
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing YAML configuration: {str(e)}")
    except FileNotFoundError:
        raise
    except Exception as e:
        raise ValueError(f"Error loading configuration: {str(e)}")