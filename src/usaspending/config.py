"""Enhanced configuration management with integrated validation."""
import yaml
import jsonschema
import logging
import inspect
import copy
import os
import msvcrt  # For Windows
from pathlib import Path
from typing import Dict, Any, Optional, List, TypeVar, Type, Set, Union, get_type_hints, get_origin, get_args
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict
from functools import lru_cache

# Only import fcntl on Unix systems
if os.name != 'nt':
    import fcntl

from .exceptions import ConfigurationError
from .config_schema import ENTITY_CONFIG_SCHEMA
from .types import ValidationResult

logger = logging.getLogger(__name__)
T = TypeVar('T')

def atomic_file_operation(file_path: Path, operation: callable):
    """Execute file operation with proper locking."""
    try:
        with open(file_path, 'r+' if os.path.exists(file_path) else 'w+') as f:
            if os.name == 'nt':  # Windows
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError as e:
                    # Handle case where file is already locked
                    logger.error(f"File is locked: {e}")
                    raise ConfigurationError(f"File is locked: {e}") from e
            else:  # Unix
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            try:
                return operation(f)
            finally:
                if os.name == 'nt':
                    try:
                        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass  # Ignore errors during unlock
                else:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    except IOError as e:
        logger.error(f"File operation failed: {e}")
        raise ConfigurationError(f"File operation failed: {e}") from e

@dataclass
class CachedValidation:
    """Represents a cached validation result."""
    timestamp: datetime
    result: ValidationResult

class ConfigManager:
    """Enhanced configuration manager with integrated validation."""
    _instance = None
    _initialized = False
    
    def __new__(cls, config_path_or_dict: Union[str, Path, Dict[str, Any]] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config_path_or_dict: Union[str, Path, Dict[str, Any]] = None):
        if self._initialized:
            if config_path_or_dict:
                self._update_config(config_path_or_dict)
            return

        self._setup_initial_state()
        
        if config_path_or_dict is not None:
            self._update_config(config_path_or_dict)
        
        ConfigManager._initialized = True

    def _setup_initial_state(self):
        """Initialize configuration manager state."""
        self._config: Dict[str, Any] = {}
        self._config_path: Optional[Path] = None
        self._last_load_time = 0
        self._validation_cache: Dict[str, CachedValidation] = {}
        self._cache_ttl = timedelta(minutes=5)
        self._cache_stats = defaultdict(int)
        self._dynamic_types: Dict[str, Type] = {}
        self.essential_fields: Set[str] = set()
        self.validation_types: Dict[str, Any] = {}

    def _update_config(self, config_path_or_dict: Union[str, Path, Dict[str, Any]]):
        """Update configuration from path or dictionary."""
        if isinstance(config_path_or_dict, dict):
            self._config_path = None
            self._config = self._merge_default_schemas(config_path_or_dict)
            self._validate_config_structure(self._config)
        else:
            self._config_path = Path(config_path_or_dict)
            self._load_config()

    def _load_config(self) -> None:
        """Load and validate configuration from YAML with atomic file operations."""
        if not self._config_path:
            return

        def read_config(f):
            raw_config = yaml.safe_load(f.read())
            merged_config = self._merge_default_schemas(raw_config)
            self._validate_config_structure(merged_config)
            return merged_config, self._config_path.stat().st_mtime

        try:
            self._config, self._last_load_time = atomic_file_operation(
                self._config_path, read_config)
            self._build_dynamic_types()
            self._init_validation_types()
            self._clear_validation_cache()
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise ConfigurationError(f"Configuration load failed: {e}") from e

    def _validate_config_structure(self, config: Dict[str, Any]) -> None:
        """Validate core configuration structure."""
        if not isinstance(config, dict):
            raise ConfigurationError("Root config must be a dictionary")

        # Ensure system section exists
        if 'system' not in config:
            config['system'] = {}

        # Initialize required sections if missing
        required_sections = {
            'processing': {
                'max_workers': 4,
                'queue_size': 1000,
                'create_index': True,
                'entity_save_frequency': 100,
                'incremental_save': True,
                'log_frequency': 50
            },
            'io': {
                'input': {
                    'batch_size': 1000,
                    'validate_input': True,
                    'skip_invalid_rows': True
                },
                'output': {
                    'entities_subfolder': 'entities',
                    'transaction_base_name': 'transactions',
                    'chunk_size': 5000
                }
            },
            'formats': {
                'csv': {
                    'encoding': 'utf-8',
                    'delimiter': ',',
                    'quotechar': '"'
                },
                'json': {
                    'indent': None,
                    'ensure_ascii': False
                }
            },
            'error_handling': {
                'log_errors': True,
                'stop_on_error': False,
                'max_errors': 100
            }
        }

        for section, defaults in required_sections.items():
            if section not in config['system']:
                config['system'][section] = defaults.copy()
            else:
                # Deep merge existing config with defaults
                config['system'][section] = self._deep_merge(
                    defaults,
                    config['system'][section]
                )

    def _deep_merge(self, defaults: Dict, override: Dict) -> Dict:
        """Recursively merge two dictionaries."""
        result = defaults.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _build_dynamic_types(self) -> None:
        """Build type definitions from configuration."""
        self._dynamic_types.clear()
        
        # Build validation type configurations
        if 'validation_types' in self._config:
            for type_name, type_config in self._config['validation_types'].items():
                self._dynamic_types[f"{type_name}Config"] = type(
                    f"{type_name}Config",
                    (dict,),
                    {'__annotations__': self._build_type_annotations(type_config)}
                )

        # Build entity configurations
        for entity_name, entity_config in self._config.items():
            if isinstance(entity_config, dict) and 'entity_processing' in entity_config:
                self._dynamic_types[f"{entity_name}Config"] = type(
                    f"{entity_name}Config",
                    (dict,),
                    {'__annotations__': self._build_type_annotations(entity_config)}
                )

    def _build_type_annotations(self, config: Dict[str, Any]) -> Dict[str, type]:
        """Build type annotations from configuration structure."""
        annotations = {}
        for key, value in config.items():
            if isinstance(value, dict):
                annotations[key] = Dict[str, Any]
            elif isinstance(value, list):
                annotations[key] = List[str if all(isinstance(x, str) for x in value) else Any]
            elif isinstance(value, bool):
                annotations[key] = bool
            elif isinstance(value, int):
                annotations[key] = int
            elif isinstance(value, float):
                annotations[key] = float
            else:
                annotations[key] = str
        return annotations

    def _init_validation_types(self) -> None:
        """Initialize validation configuration."""
        self.validation_types = self._config.get('validation_types', {})
        
        # Extract essential fields
        self.essential_fields.clear()
        for entity_config in self._config.values():
            if isinstance(entity_config, dict) and 'key_fields' in entity_config:
                self.essential_fields.update(entity_config['key_fields'])

    def validate_entity_config(self, entity_name: str, entity_config: Dict[str, Any]) -> ValidationResult:
        """Validate entity configuration with caching."""
        cache_key = f"entity_config:{entity_name}"
        cached = self._get_cached_validation(cache_key)
        if cached:
            self._cache_stats['hits'] += 1
            return cached.result
            
        self._cache_stats['misses'] += 1
        
        result = self._validate_entity_config_impl(entity_name, entity_config)
        self._cache_validation(cache_key, result)
        return result

    def _validate_entity_config_impl(self, entity_name: str, entity_config: Dict[str, Any]) -> ValidationResult:
        """Implement entity configuration validation."""
        if not isinstance(entity_config, dict):
            return ValidationResult(
                valid=False,
                message=f"Entity configuration for {entity_name} must be a dictionary",
                error_type="config_invalid",
                field_name=entity_name
            )

        required_fields = ['key_fields', 'entity_processing']
        missing = [f for f in required_fields if f not in entity_config]
        if missing:
            return ValidationResult(
                valid=False,
                message=f"Missing required fields in {entity_name} config: {', '.join(missing)}",
                error_type="config_missing_fields",
                field_name=entity_name
            )

        if not entity_config.get('key_fields'):
            return ValidationResult(
                valid=False,
                message=f"Entity {entity_name} must have at least one key field",
                error_type="missing_key_fields",
                field_name=entity_name
            )

        return ValidationResult(True)

    def validate_chunk_config(self) -> ValidationResult:
        """Validate chunking configuration with caching."""
        cache_key = "chunk_config"
        cached = self._get_cached_validation(cache_key)
        if cached:
            self._cache_stats['hits'] += 1
            return cached.result
            
        self._cache_stats['misses'] += 1
        
        result = self._validate_chunk_config_impl()
        self._cache_validation(cache_key, result)
        return result

    def _validate_chunk_config_impl(self) -> ValidationResult:
        """Implement chunk configuration validation."""
        if 'global' not in self._config or 'processing' not in self._config['global']:
            return ValidationResult(
                valid=False,
                message="Missing global.processing configuration section",
                error_type="config_missing_section",
                field_name="global.processing"
            )

        chunk_config = self._config['global']['processing']
        if 'records_per_chunk' not in chunk_config:
            return ValidationResult(
                valid=False,
                message="records_per_chunk required in global.processing config",
                error_type="missing_chunk_size",
                field_name="global.processing.records_per_chunk"
            )

        return ValidationResult(True)

    def validate_processing_order(self) -> List[ValidationResult]:
        """Validate entity processing order with caching."""
        cache_key = "processing_order"
        cached = self._get_cached_validation(cache_key)
        if cached:
            self._cache_stats['hits'] += 1
            return cached.result
            
        self._cache_stats['misses'] += 1
        
        results = []
        seen_orders = {}
        
        for entity_name, config in self._config.items():
            if isinstance(config, dict):
                order = config.get('entity_processing', {}).get('processing_order')
                if order is None:
                    results.append(ValidationResult(
                        valid=False,
                        message=f"Missing processing_order for {entity_name}",
                        error_type="missing_processing_order",
                        field_name=entity_name
                    ))
                elif order in seen_orders:
                    results.append(ValidationResult(
                        valid=False,
                        message=f"Duplicate order {order} for {entity_name} and {seen_orders[order]}",
                        error_type="duplicate_processing_order",
                        field_name=entity_name
                    ))
                else:
                    seen_orders[order] = entity_name
                    
        self._cache_validation(cache_key, results)
        return results

    def get_processing_order(self) -> List[tuple[int, str]]:
        """Get ordered list of entities by processing order."""
        entities = []
        for entity_name, config in self._config.items():
            if isinstance(config, dict):
                order = config.get('entity_processing', {}).get('processing_order', 999)
                entities.append((order, entity_name))
        return sorted(entities)

    def _get_cached_validation(self, key: str) -> Optional[CachedValidation]:
        """Get cached validation result if valid."""
        cached = self._validation_cache.get(key)
        if cached and datetime.now() - cached.timestamp < self._cache_ttl:
            return cached
        return None

    def _cache_validation(self, key: str, result: Union[ValidationResult, List[ValidationResult]]) -> None:
        """Cache a validation result."""
        self._validation_cache[key] = CachedValidation(
            timestamp=datetime.now(),
            result=result
        )

    def _clear_validation_cache(self) -> None:
        """Clear the validation cache."""
        self._validation_cache.clear()
        self._cache_stats = defaultdict(int)

    def get_cache_stats(self) -> Dict[str, int]:
        """Get validation cache statistics."""
        return dict(self._cache_stats)

    @property
    def config(self) -> Dict[str, Any]:
        """Get full validated config dictionary with atomic reload."""
        if self._config_path and self._config_has_changed():
            self._load_config()
        return self._config

    def _config_has_changed(self) -> bool:
        """Check if configuration file has changed with atomic operations."""
        if not self._config_path or not self._config_path.exists():
            return False

        def check_modified_time(f):
            return f.stat().st_mtime > self._last_load_time

        try:
            return atomic_file_operation(self._config_path, check_modified_time)
        except ConfigurationError:
            return False
        
    def get_entity_config(self, entity_type: str) -> Optional[Dict[str, Any]]:
        """Get validated config for entity type."""
        if self._config_path and self._config_has_changed():
            self._load_config()
        return self._config.get(entity_type)

    def _merge_default_schemas(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure configuration has all required default values."""
        result = copy.deepcopy(config)
        
        # Define default validation schema
        default_validation_schema = {
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
        
        # Apply defaults recursively
        if 'validation_types' not in result:
            result['validation_types'] = {}
        
        validation_types = result['validation_types']
        default_types = default_validation_schema['validation_types']
        
        for type_name, type_config in default_types.items():
            if type_name not in validation_types:
                validation_types[type_name] = type_config
            else:
                for subtype, subconfig in type_config.items():
                    if subtype not in validation_types[type_name]:
                        validation_types[type_name][subtype] = subconfig
        
        # Add validation error messages
        if 'validation' not in result:
            result['validation'] = {}
        
        validation = result['validation']
        if 'errors' not in validation:
            validation['errors'] = default_validation_schema['validation']['errors']
        
        if 'empty_values' not in validation:
            validation['empty_values'] = default_validation_schema['validation']['empty_values']
        
        return result

    # Section-based access methods
    
    @lru_cache(maxsize=32)
    def get_section(self, section_path: str, default=None) -> Any:
        """
        Get configuration section using dot notation path.
        Example: get_section("system.processing.batch_size")
        """
        if not self._config:
            return default
            
        parts = section_path.split('.')
        current = self._config
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
                
        return current
    
    def get_system_config(self) -> Dict[str, Any]:
        """Get system configuration section."""
        return self.get_section("system", {})
    
    def get_processing_config(self) -> Dict[str, Any]:
        """Get processing configuration section."""
        return self.get_section("system.processing", {})
    
    def get_io_config(self) -> Dict[str, Any]:
        """Get I/O configuration section."""
        return self.get_section("system.io", {})
    
    def get_entity_configs(self) -> Dict[str, Any]:
        """Get all entity configurations."""
        entities = {}
        for name, config in self._config.items():
            if isinstance(config, dict) and 'field_mappings' in config and 'key_fields' in config:
                entities[name] = config
        return entities
    
    def get_relationships(self) -> Dict[str, Any]:
        """Get entity relationships configuration."""
        return self.get_section("relationships", {})
    
    def get_data_dictionary(self) -> Dict[str, Any]:
        """Get data dictionary configuration."""
        return self.get_section("data_dictionary", {})
    
    def get_field_properties(self) -> Dict[str, Any]:
        """Get field properties configuration."""
        return self.get_section("field_properties", {})
    
    def get_validation_config(self) -> Dict[str, Any]:
        """Get validation configuration."""
        return self.get_section("system.validation", {})
    
    def reload_config(self):
        """Reload configuration from file."""
        if self._config_path:
            self._load_config()
        # Clear caches
        self.get_section.cache_clear()

    # Methods to support iteration interface
    def __iter__(self):
        return iter(self._config.items())
        
    def items(self):
        return self._config.items()
        
    def get(self, key, default=None):
        return self._config.get(key, default)
    
    # Method needed by processor.py
    def get_config(self):
        return self._config

# ConfigManager singleton provides all needed functionality
__all__ = ['ConfigManager']