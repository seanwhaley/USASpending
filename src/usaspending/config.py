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
        if (entity_save_frequency is None):
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
            entity_config = contracts['entity_separation']
            if not isinstance(entity_config, dict):
                raise ValueError("Entity configuration must be a dictionary")
                
            if 'entities' not in entity_config:
                raise ValueError("Entity separation enabled but no entities configured")
                
            entities = entity_config['entities']
            if not isinstance(entities, dict):
                raise ValueError("Entities configuration must be a dictionary")
            
            for entity_type, config in entities.items():
                if not isinstance(config, dict):
                    raise ValueError(f"Invalid configuration for entity type {entity_type}")
                validate_entity_config(entity_type, config)
        
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

def validate_entity_config(entity_type: str, config: Dict[str, Any]) -> None:
    """Validate entity type configuration structure only."""
    if not config:
        return  # Empty config is valid, will use defaults
        
    # Validate levels if present
    if 'levels' in config:
        if not isinstance(config['levels'], dict):
            raise ValueError(f"Invalid 'levels' configuration for {entity_type}")
            
        for level, level_config in config['levels'].items():
            if not isinstance(level_config, dict):
                raise ValueError(f"Invalid level configuration for {level}")
            if 'field_mappings' not in level_config:
                raise ValueError(f"Missing field_mappings for {level}")
            if 'key_fields' not in level_config:
                raise ValueError(f"Missing key_fields for {level}")
                    
    # Only validate structure of key_fields and field_mappings
    if 'key_fields' in config:
        if not isinstance(config['key_fields'], (list, tuple)):
            raise ValueError("key_fields must be a list")
        if not all(isinstance(k, str) for k in config['key_fields']):
            raise ValueError("All key fields must be strings")
                
    if 'field_mappings' in config:
        field_mappings = config['field_mappings']
        if not isinstance(field_mappings, dict):
            raise ValueError("field_mappings must be a dictionary")
            
        # Validate field mapping structure only
        for target, source in field_mappings.items():
            if not isinstance(target, str):
                raise ValueError(f"Field mapping target '{target}' must be a string")
            if not isinstance(source, (str, list, tuple, dict)):
                raise ValueError(f"Field mapping for '{target}' must be a string, list, tuple or dictionary")
                
            # Validate nested structure if dict
            if isinstance(source, dict):
                for k, v in source.items():
                    if not isinstance(k, str) or not isinstance(v, (str, list, tuple)):
                        raise ValueError(f"Invalid nested mapping structure for '{target}'")

def validate_field_mappings(entity_config: Dict[str, Any]) -> None:
    """Validate field mapping structure only.
    
    Args:
        entity_config: Entity configuration containing field mappings
        
    Raises:
        ValueError: If field mappings structure is invalid
    """
    if not entity_config:
        return
        
    field_mappings = entity_config.get('field_mappings', {})
    if not isinstance(field_mappings, dict):
        raise ValueError("Field mappings must be a dictionary")
    
    # Only validate structure
    for target, source in field_mappings.items():
        if not isinstance(target, str):
            raise ValueError(f"Field mapping target '{target}' must be a string")
        if not isinstance(source, (str, list, tuple, dict)):
            raise ValueError(f"Field mapping for '{target}' must be a string, list, tuple or dictionary")

def validate_hierarchical_entity(entity_type: str, config: Dict[str, Any]) -> None:
    """Validate hierarchical entity structure."""
    if not isinstance(config.get('levels'), dict):
        raise ValueError(f"Invalid levels configuration for {entity_type}")

    # Only validate the required structure is present
    for level_name, level_config in config['levels'].items():
        if not isinstance(level_config, dict):
            raise ValueError(f"Invalid level configuration for {entity_type}.{level_name}")

def validate_regular_entity(entity_type: str, config: Dict[str, Any]) -> None:
    """Validate regular entity structure."""
    if not isinstance(config, dict):
        raise ValueError(f"Invalid configuration for entity type {entity_type}")
    
    # Only validate that minimum required structure exists
    if not any(key in config for key in ['field_mappings', 'key_fields']):
        raise ValueError(f"Entity type {entity_type} must have either field_mappings or key_fields defined")

def validate_relationships(entity_type: str, relationships: Union[Dict[str, Any], list[Any]]) -> None:
    """Validate relationship configurations structure.
    
    Args:
        entity_type: Type of entity being validated
        relationships: Relationship configurations to validate
        
    Raises:
        ValueError: If relationships structure is invalid
    """
    if isinstance(relationships, dict):
        if not all(isinstance(rel_type, str) for rel_type in relationships.keys()):
            raise ValueError("Relationship types must be strings")
        for rel_configs in relationships.values():
            if not isinstance(rel_configs, list):
                raise ValueError("Relationship configurations must be a list")
    elif isinstance(relationships, list):
        if not all(isinstance(rel, dict) for rel in relationships):
            raise ValueError("Each relationship must be a dictionary")
    else:
        raise ValueError("Relationships must be a dictionary or list")

def validate_relationship_config(entity_type: str, rel_type: Optional[str], 
                              rel_config: Dict[str, Any]) -> None:
    """Validate a single relationship configuration structure.
    
    Args:
        entity_type: Type of entity
        rel_type: Type of relationship  
        rel_config: Relationship configuration to validate
        
    Raises:
        ValueError: If configuration structure is invalid
    """
    if not isinstance(rel_config, dict):
        raise ValueError("Relationship configuration must be a dictionary")

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
    """Validate type conversion configuration section structure."""
    if not isinstance(type_config, dict):
        raise ValueError("Type conversion config must be a dictionary")

    # Only validate structure, not content since that's in YAML
    for field_type in ['date_fields', 'numeric_fields', 'boolean_fields']:
        if field_type in type_config and not isinstance(type_config[field_type], list):
            raise ValueError(f"{field_type} must be a list")

    # Validate value mapping structure if present
    if 'value_mapping' in type_config:
        if not isinstance(type_config['value_mapping'], dict):
            raise ValueError("value_mapping must be a dictionary")

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

"""Configuration validation and processing."""
from typing import Dict, Any, List, Set
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def validate_entity_config(entity_type: str, config: Dict[str, Any]) -> None:
    """Validate entity type configuration.
    
    Args:
        entity_type: Type of entity being validated
        config: Entity configuration to validate
        
    Raises:
        ValueError: If configuration is invalid
    """
    if not config:
        return  # Empty config is valid, will use defaults
        
    # Validate levels if present
    if 'levels' in config:
        if not isinstance(config['levels'], dict):
            raise ValueError(f"Invalid 'levels' configuration for {entity_type}")
            
        for level, level_config in config['levels'].items():
            if not isinstance(level_config, dict):
                raise ValueError(f"Invalid level configuration for {level}")
            if 'field_mappings' not in level_config:
                raise ValueError(f"Missing field_mappings for {level}")
            if 'key_fields' not in level_config:
                raise ValueError(f"Missing key_fields for {level}")
                    
    # Validate key_fields if present at root level
    if 'key_fields' in config:
        if not isinstance(config['key_fields'], (list, tuple)):
            raise ValueError("key_fields must be a list")
        if not all(isinstance(k, str) for k in config['key_fields']):
            raise ValueError("All key fields must be strings")
                
        # Check key fields have mappings if field_mappings exists
        if 'field_mappings' in config:
            field_mappings = config['field_mappings']
            for key_field in config['key_fields']:
                # Check direct mapping
                if key_field in field_mappings:
                    continue
                    
                # Check alternate mappings (e.g. transaction_key maps to contract_transaction_unique_key)
                mapped = False
                for target, source in field_mappings.items():
                    if isinstance(source, str) and source == key_field:
                        mapped = True
                        break
                    elif isinstance(source, (list, tuple)) and key_field in source:
                        mapped = True
                        break
                    elif isinstance(source, dict) and any(v == key_field for v in source.values()):
                        mapped = True
                        break
                        
                if not mapped:
                    raise ValueError(f"Key field '{key_field}' missing from field_mappings and not referenced as a source")

def validate_field_mappings(entity_config: Dict[str, Any]) -> None:
    """Validate field mapping structure.
    
    Args:
        entity_config: Entity configuration containing field mappings
        
    Raises:
        ValueError: If field mappings structure is invalid
    """
    if not entity_config:
        return
        
    # Only validate the structure is correct, content validation is in YAML
    field_mappings = entity_config.get('field_mappings', {})
    if not isinstance(field_mappings, dict):
        raise ValueError("Field mappings must be a dictionary")
    
    # Validate each field mapping structure
    for target, source in field_mappings.items():
        if not isinstance(target, str):
            raise ValueError(f"Field mapping target '{target}' must be a string")
        
        if not isinstance(source, (str, list, tuple, dict)):
            raise ValueError(f"Field mapping for '{target}' must be a string, list, or dictionary")

def validate_relationships(entity_type: str, relationships: Dict[str, Any]) -> None:
    """Validate relationship configurations.
    
    Args:
        entity_type: Type of entity being validated
        relationships: Relationship configurations to validate
        
    Raises:
        ValueError: If relationships are invalid
    """
    if not isinstance(relationships, dict):
        raise ValueError(f"Invalid relationships format for {entity_type}")
    
    for rel_type, rel_configs in relationships.items():
        if not isinstance(rel_configs, list):
            raise ValueError(f"Relationship configurations for {entity_type}.{rel_type} must be a list")
            
        for rel_config in rel_configs:
            validate_relationship_config(entity_type, rel_type, rel_config)

def validate_relationship_config(entity_type: str, rel_type: str, rel_config: Dict[str, Any]) -> None:
    """Validate a single relationship configuration.
    
    Args:
        entity_type: Type of entity
        rel_type: Type of relationship
        rel_config: Relationship configuration to validate
        
    Raises:
        ValueError: If configuration is invalid
    """
    # For hierarchical relationships
    if rel_type == 'hierarchical':
        required = ['from_level', 'to_level', 'type']
    else:
        required = ['from_field', 'to_field', 'type']
    
    missing = [field for field in required if field not in rel_config]
    if missing:
        context = f"{entity_type}.{rel_type}" if rel_type else entity_type
        raise ValueError(f"Relationship in {context} missing {', '.join(missing)} fields")

def validate_entity_references(entity_config: Dict[str, Any]) -> None:
    """Validate entity reference configurations.
    
    Args:
        entity_config: Entity configuration containing references
        
    Raises:
        ValueError: If references are invalid
    """
    refs = entity_config.get("entity_references", {})
    if not isinstance(refs, dict):
        raise ValueError("Entity references configuration must be a dictionary")
            
    for ref_type, ref_config in refs.items():
        if not isinstance(ref_type, str):
            raise ValueError(f"Entity reference type must be a string: {ref_type}")
        if not isinstance(ref_config, dict):
            raise ValueError(f"Configuration for reference '{ref_type}' must be a dictionary")
        
        # Validate fields list
        fields = ref_config.get("fields", [])
        if not isinstance(fields, (list, tuple)):
            raise ValueError(f"Fields for reference '{ref_type}' must be a list")
        if not all(isinstance(f, str) for f in fields):
            raise ValueError(f"All fields in reference '{ref_type}' must be strings")
                
        # Validate field processors if present
        if "field_processors" in ref_config:
            procs = ref_config["field_processors"]
            if not isinstance(procs, dict):
                raise ValueError(f"Field processors for reference '{ref_type}' must be a dictionary")
            valid_processors = {"boolean", "int", "float", "date"}
            for field, proc in procs.items():
                if not isinstance(field, str):
                    raise ValueError(f"Field name in processors for '{ref_type}' must be a string")
                if proc not in valid_processors:
                    raise ValueError(f"Invalid processor '{proc}' for field '{field}' in reference '{ref_type}'. Valid processors: {', '.join(valid_processors)}")

def _validate_hierarchical_mappings(entity_config: Dict[str, Any]) -> None:
    """Validate field mappings in hierarchical levels structure only.
    
    Args:
        entity_config: Entity configuration to validate
        
    Raises:
        ValueError: If hierarchical mappings structure is invalid
    """
    levels = entity_config.get('levels', {})
    if not isinstance(levels, dict):
        raise ValueError("Levels configuration must be a dictionary")
            
    for level, config in levels.items():
        if not isinstance(config, dict):
            raise ValueError(f"Invalid config for level: {level}")
                
        level_mappings = config.get('field_mappings', {})
        if not isinstance(level_mappings, dict):
            raise ValueError(f"Invalid field mappings for level: {level}")
                
        # Validate each level's field mappings structure
        for target, source in level_mappings.items():
            if not isinstance(target, str):
                raise ValueError(f"Field mapping target '{target}' in level '{level}' must be a string")
            if isinstance(source, str):
                continue
            if isinstance(source, (list, tuple)):
                if not all(isinstance(s, str) for s in source):
                    raise ValueError(f"All source fields for target '{target}' in level '{level}' must be strings")
            elif isinstance(source, dict):
                if not all(isinstance(k, str) and isinstance(v, str) for k, v in source.items()):
                    raise ValueError(f"All nested keys and values for '{target}' in level '{level}' must be strings")
            else:
                raise ValueError(f"Field mapping for '{target}' in level '{level}' must be a string, list of strings, or dictionary of strings")
            
        # Validate key fields structure 
        key_fields = config.get('key_fields', [])
        if not isinstance(key_fields, (list, tuple)):
            raise ValueError(f"key_fields for level '{level}' must be a list")
        if not all(isinstance(k, str) for k in key_fields):
            raise ValueError(f"All key fields for level '{level}' must be strings")

def load_and_validate_config(config_path: Path) -> Dict[str, Any]:
    """Load and validate full configuration.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Validated configuration dictionary
        
    Raises:
        ValueError: If configuration is invalid
    """
    import yaml
    
    if not config_path.exists():
        raise ValueError(f"Configuration file not found: {config_path}")
        
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        raise ValueError(f"Error loading configuration: {str(e)}")
        
    # Validate required sections
    required_sections = {'global', 'contracts'}
    missing = required_sections - set(config.keys())
    if missing:
        raise ValueError(f"Configuration missing required sections: {', '.join(missing)}")
        
    # Validate global settings
    global_config = config['global']
    if not isinstance(global_config, dict):
        raise ValueError("Global configuration must be a dictionary")
        
    # Validate contracts section
    contracts = config['contracts']
    if not isinstance(contracts, dict):
        raise ValueError("Contracts configuration must be a dictionary")
        
    # Validate entity configurations
    entity_config = contracts.get('entity_separation', {}).get('entities', {})
    if not isinstance(entity_config, dict):
        raise ValueError("Entity configuration must be a dictionary")
        
    for entity_type, entity_conf in entity_config.items():
        validate_entity_config(entity_type, entity_conf)
        validate_field_mappings(entity_conf)
        
        if "relationships" in entity_conf:
            validate_relationships(entity_type, entity_conf["relationships"])
            
        if "entity_references" in entity_conf:
            validate_entity_references(entity_conf)
            
    return config