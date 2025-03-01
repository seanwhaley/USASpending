"""Configuration handling module."""
import logging
import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Literal
import yaml
from dotenv import load_dotenv
import copy

from .types import ConfigType, ValidationRule
from .config_validator import validate_config_structure, ConfigValidationError, get_schema_description

logger = logging.getLogger(__name__)

def setup_logging(output_file: Optional[str] = None, debug_file: Optional[str] = None) -> logging.Logger:
    """Setup logging configuration."""
    logger = logging.getLogger('usaspending')
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    logger.setLevel(getattr(logging, log_level))
    
    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
    logger.addHandler(console)
    
    # File handlers
    if output_file:
        file_handler = logging.FileHandler(output_file)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)
    
    if debug_file:
        debug_handler = logging.FileHandler(debug_file)
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(funcName)s - %(message)s'
        ))
        logger.addHandler(debug_handler)
    
    return logger

def load_config(config_file: str = '../conversion_config.yaml',
                section: Optional[Literal['contracts', 'data_dictionary']] = None) -> ConfigType:
    """Load and validate configuration from YAML file and environment variables."""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        if not isinstance(config, dict):
            raise ValueError("Configuration must be a dictionary")
            
        # Apply environment variable overrides
        config = _apply_env_overrides(config)
            
        # Validate configuration structure against TypedDict definitions
        try:
            validate_config_structure(config)
        except ConfigValidationError as e:
            # Optional: print schema to help with debugging
            print("Expected configuration schema:")
            import json
            print(json.dumps(get_schema_description(ConfigType), indent=2))
            raise
            
        # Return specific section if requested
        if section:
            if section not in config:
                raise ValueError(f"Section '{section}' not found in configuration")
            return config[section]
        
        return config
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in configuration file: {e}")

def _apply_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """Apply environment variable overrides to configuration."""
    env_mappings = config.get('_environment_mappings', {})
    
    def apply_mapping(config_dict: Dict[str, Any], mappings: Dict[str, Any], prefix: str = "") -> None:
        for key, value in mappings.items():
            if isinstance(value, dict):
                if key not in config_dict:
                    config_dict[key] = {}
                apply_mapping(config_dict[key], value, f"{prefix}{key}_")
            else:
                env_key = f"{prefix}{key}".upper()
                env_value = os.getenv(env_key)
                if env_value is not None:
                    if value == 'bool':
                        config_dict[key] = _get_env_bool(env_key)
                    elif value == 'int':
                        config_dict[key] = _get_env_int(env_key)
                    else:
                        config_dict[key] = env_value
    
    apply_mapping(config, env_mappings)
    return config

def _get_env_bool(key: str, default: bool = False) -> bool:
    """Convert environment variable to boolean."""
    value = os.getenv(key, str(default)).lower()
    return value in ('true', '1', 't', 'yes', 'y')

def _get_env_int(key: str, default: int = 0) -> int:
    """Convert environment variable to integer."""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default

def _merge_default_schemas(config: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure configuration has all required default values."""
    result = copy.deepcopy(DEFAULT_VALIDATION_SCHEMA)
    
    # Recursively merge config into defaults
    def deep_merge(target, source):
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                deep_merge(target[key], value)
            else:
                target[key] = value
    
    deep_merge(result, config)
    return result

# Add a configuration schema definition
DEFAULT_VALIDATION_SCHEMA = {
    "validation_types": {
        "numeric": {
            "decimal": {
                "strip_characters": "$,.",
                "precision": 2
            }
        },
        "date": {
            "standard": {
                "format": "%Y-%m-%d"
            }
        },
        "string": {
            "pattern": {}
        }
    },
    "validation": {
        "errors": {
            "numeric": {
                "invalid": "Invalid numeric value for {field}",
                "rule_violation": "Invalid numeric value for {field} based on rule {rule}"
            },
            "date": {
                "invalid": "Invalid date value for {field}",
                "rule_violation": "Invalid date value for {field} based on rule {rule}"
            },
            "general": {
                "rule_violation": "Validation failed for {field} based on rule {rule}"
            }
        },
        "empty_values": ["", "None", "null", "na", "n/a"]
    }
}