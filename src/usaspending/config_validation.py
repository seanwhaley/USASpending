"""Configuration validation system."""
from typing import List, Dict, Any, Optional, Union, TypeVar, Type, Generic
from pathlib import Path
from dataclasses import dataclass
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import importlib
import yaml
import jsonschema
import threading
import json
import traceback
import sys
import os

from . import (
    get_logger, ConfigurationError, 
    create_component, create_component_from_config,
    create_components_from_config, implements_interface
)
from .interfaces import (
    IEntityStore, IEntityFactory, IValidationService, 
    ITransformerFactory, IDataProcessor
)
from .config_schemas import DEFAULT_ENTITY_FACTORY, DEFAULT_ENTITY_STORE, DEFAULT_VALIDATION_SERVICE
from .file_utils import ensure_directory, FileOperationError

logger = get_logger(__name__)

T = TypeVar('T')

@dataclass
class ValidationError:
    """Configuration validation error."""
    path: str
    message: str
    severity: str = "error"

class ComponentManager(Generic[T]):
    """Manages component lifecycle and configuration."""
    
    def __init__(self, 
                 interface: Type[T],
                 config: Dict[str, Any],
                 required: bool = True):
        """Initialize component manager."""
        self.interface = interface
        self.config = config
        self.required = required
        self._instance: Optional[T] = None
        self._instance_lock = threading.RLock()
        
    @property
    def instance(self) -> Optional[T]:
        """Get component instance, creating it if needed."""
        if self._instance is None:
            with self._instance_lock:
                if self._instance is None:
                    self._instance = self._create_instance()
        return self._instance
    
    def _create_instance(self) -> Optional[T]:
        """Create component instance from configuration."""
        class_path = self.config.get('class')
        if not class_path:
            if self.required:
                raise ConfigurationError(f"Required component {self.interface.__name__} missing class configuration")
            return None
        
        # Use the central create_component function
        try:
            config_data = self.config.get('config', {})
            return create_component(class_path, config_data)
        except Exception as e:
            if self.required:
                raise ConfigurationError(f"Error creating {self.interface.__name__} instance: {str(e)}")
            logger.warning(f"Optional component {self.interface.__name__} creation failed: {str(e)}")
            return None

class ConfigValidator:
    """Consolidated configuration validation system."""
    
    def __init__(self, schema: Dict[str, Any]):
        """Initialize validator with schema."""
        self.schema = schema
        self.errors: List[ValidationError] = []
        self.config: Optional[Dict[str, Any]] = None
        self._components: Dict[str, ComponentManager] = {}
        self._config_lock = threading.RLock()
        
    def validate_file(self, file_path: str) -> List[ValidationError]:
        """Validate configuration file."""
        try:
            config = self._load_config_file(file_path)
            return self.validate_config(config)
            
        except ConfigurationError as e:
            return [ValidationError(file_path, str(e))]
            
        except Exception as e:
            return [ValidationError(file_path, f"Unexpected error: {str(e)}")]
    
    def validate_config(self, config: Dict[str, Any]) -> List[ValidationError]:
        """Validate configuration dict."""
        with self._config_lock:
            self.errors = []
            self.config = config
            
            # Add default components if missing
            self.config = self._inject_default_components(config)
            
            # Perform all validations
            try:
                self._validate_schema(config)
                self._validate_io_paths(config)  # Updated to handle system.io paths
                self._validate_components(config)
                self._validate_field_dependencies(config)
            except Exception as e:
                self.errors.append(
                    ValidationError("", f"Validation error: {str(e)}")
                )
            
            return self.errors
    
    def _inject_default_components(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Inject default components if they don't exist in the config."""
        logger.debug(f"BEFORE INJECTION - Config keys: {list(config.keys())}")
        config = config.copy()
        
        # Make sure system section exists
        if 'system' not in config:
            config['system'] = {}
        
        # Add entity_factory if missing
        if 'entity_factory' not in config['system']:
            logger.info("Injecting default entity_factory component")
            logger.debug(f"Default entity_factory structure: {json.dumps(DEFAULT_ENTITY_FACTORY, indent=2)}")
            config['system']['entity_factory'] = DEFAULT_ENTITY_FACTORY
        
        # Add entity_store if missing
        if 'entity_store' not in config['system']:
            logger.info("Injecting default entity_store component")
            logger.debug(f"Default entity_store structure: {json.dumps(DEFAULT_ENTITY_STORE, indent=2)}")
            config['system']['entity_store'] = DEFAULT_ENTITY_STORE
            # Set path from system.io.output if available
            if 'io' in config['system']:
                output_config = config['system']['io'].get('output', {})
                if 'directory' in output_config:
                    base_dir = output_config['directory']
                    entities_dir = output_config.get('entities_subfolder', 'entities')
                    store_path = str(Path(base_dir) / entities_dir)
                    logger.info(f"Setting entity store path to: {store_path}")
                    logger.debug(f"Entity store path source: system.io.output.directory={base_dir}, entities_subfolder={entities_dir}")
                    config['system']['entity_store']['config']['path'] = store_path
        
        # Add validation_service if missing
        if 'validation_service' not in config['system']:
            logger.info("Injecting default validation_service component")
            logger.debug(f"Default validation_service structure: {json.dumps(DEFAULT_VALIDATION_SERVICE, indent=2)}")
            config['system']['validation_service'] = DEFAULT_VALIDATION_SERVICE
        
        logger.debug(f"AFTER INJECTION - Config keys: {list(config.keys())}")
        logger.debug(f"Injected components check: entity_factory={'class' in config['system'].get('entity_factory', {})}, " +
                    f"entity_store={'class' in config['system'].get('entity_store', {})}, " +
                    f"validation_service={'class' in config['system'].get('validation_service', {})}")
        
        return config
    
    def get_component(self, interface: Type[T], required: bool = True) -> Optional[T]:
        """Get a component instance by interface."""
        component_id = interface.__name__
        
        if component_id not in self._components:
            if not self.config:
                raise ConfigurationError("Configuration not loaded")
                
            config_key = _interface_to_config_key(interface)
            component_config = self.config.get('system', {}).get(config_key, {})
            
            self._components[component_id] = ComponentManager(
                interface, component_config, required
            )
            
        return self._components[component_id].instance
    
    @contextmanager
    def component_context(self):
        """Context manager for component lifecycle.
        
        Returns:
            The ConfigValidator instance for use within the context.
        """
        try:
            # Return self to allow access to validator methods within context
            yield self
        finally:
            # Clean up components on exit
            self._components.clear()
    
    def _load_config_file(self, file_path: str) -> Dict[str, Any]:
        """Load configuration from file."""
        path = Path(file_path)
        if not path.exists():
            raise ConfigurationError(f"Configuration file not found: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise ConfigurationError(f"Error loading configuration file: {str(e)}")
    
    def _validate_schema(self, config: Dict[str, Any]) -> None:
        """Validate configuration against JSON schema."""
        try:
            jsonschema.validate(instance=config, schema=self.schema)
            
        except jsonschema.exceptions.ValidationError as e:
            self.errors.append(
                ValidationError(e.path[-1], e.message)
            )
            
        except Exception as e:
            self.errors.append(
                ValidationError("", f"Schema validation error: {str(e)}")
            )
    
    def _validate_io_paths(self, config: Dict[str, Any]) -> None:
        """Validate path configurations from system.io section."""
        # First check if we have direct paths section (legacy configuration)
        paths = config.get('paths', {})
        if paths:
            self._validate_path_section(paths)
            
        # Otherwise use system.io section
        system_config = config.get('system', {})
        if not system_config:
            return
            
        io_config = system_config.get('io', {})
        if not io_config:
            return
            
        # Extract paths from system.io configuration
        paths_to_validate = {}
        
        # Extract output directory
        output_config = io_config.get('output', {})
        output_dir = output_config.get('directory')
        if output_dir:
            paths_to_validate['output_dir'] = output_dir
            # Ensure output directory exists
            try:
                ensure_directory(output_dir)
            except FileOperationError as e:
                self.errors.append(
                    ValidationError("system.io.output.directory", str(e))
                )
        else:
            self.errors.append(
                ValidationError("system.io.output.directory", "Output directory is required")
            )
            
        # Extract data directory from input config if available
        input_config = io_config.get('input', {})
        input_file = input_config.get('file')
        if input_file:
            paths_to_validate['input_file'] = input_file
            
        # Validate the extracted paths
        self._validate_path_section(paths_to_validate)
        
    def _validate_path_section(self, paths: Dict[str, str]) -> None:
        """Validate a set of path configurations."""
        for key, path in paths.items():
            if not path:
                self.errors.append(
                    ValidationError(f"paths.{key}", "Path cannot be empty")
                )
                continue
                
            # Convert to Path object for validation
            try:
                path_obj = Path(path)
                
                # Check if path contains parent directory traversal
                if '..' in path_obj.parts:
                    self.errors.append(
                        ValidationError(
                            f"paths.{key}",
                            "Path cannot contain parent directory traversal (..)"
                        )
                    )
                    
                # For input paths, check they exist
                if key.startswith('input'):
                    if not path_obj.exists():
                        self.errors.append(
                            ValidationError(
                                f"paths.{key}",
                                f"Input path does not exist: {path}"
                            )
                        )
                        
            except Exception as e:
                self.errors.append(
                    ValidationError(
                        f"paths.{key}",
                        f"Invalid path: {str(e)}"
                    )
                )
    
    def _validate_components(self, config: Dict[str, Any]) -> None:
        """Validate component configurations."""
        logger.debug(f"Validating components with config keys: {list(config.keys())}")
        
        # Get system config where components are stored
        system_config = config.get('system', {})
        
        # Test component creation without storing instances
        self._validate_component_class(
            system_config.get('entity_factory', {}),
            'entity_factory',
            IEntityFactory,
            required=True
        )
        
        self._validate_component_class(
            system_config.get('entity_store', {}),
            'entity_store',
            IEntityStore,
            required=True
        )
        
        self._validate_component_class(
            system_config.get('validation_service', {}),
            'validation_service',
            IValidationService,
            required=True
        )
        
        # Optional components
        self._validate_component_class(
            system_config.get('transformer_factory', {}),
            'transformer_factory',
            ITransformerFactory,
            required=False
        )
    
    def _validate_component_class(
        self,
        config: Dict[str, Any],
        name: str,
        interface: type,
        required: bool = True
    ) -> None:
        """Validate a component class configuration."""
        logger.debug(f"Validating component '{name}' with config: {json.dumps(config, indent=2)[:200]}...")
        
        class_path = config.get('class')
        if not class_path:
            if required:
                error_msg = f"Required component {name} missing class configuration"
                logger.error(f"VALIDATION ERROR: {error_msg}")
                self.errors.append(
                    ValidationError(
                        f"{name}.class",
                        error_msg
                    )
                )
            return
        
        # Use the interface checking functionality from component_utils
        try:
            class_path = config['class']
            logger.debug(f"Attempting to load class {class_path} for component {name}")
            module_path, class_name = class_path.rsplit('.', 1)
            module = importlib.import_module(module_path)
            class_type = getattr(module, class_name)
            
            # Changed from _implements_interface to implements_interface
            if not implements_interface(class_type, interface):
                error_msg = f"Class {class_path} does not implement {interface.__name__}"
                logger.error(f"VALIDATION ERROR: {error_msg}")
                self.errors.append(
                    ValidationError(
                        f"{name}.class",
                        error_msg
                    )
                )
                
        except ImportError as e:
            error_msg = f"Could not import module for class {class_path}: {str(e)}"
            logger.error(f"VALIDATION ERROR: {error_msg}")
            self.errors.append(
                ValidationError(
                    f"{name}.class",
                    error_msg
                )
            )
        except AttributeError as e:
            error_msg = f"Class {class_name} not found in module {module_path}: {str(e)}"
            logger.error(f"VALIDATION ERROR: {error_msg}")
            self.errors.append(
                ValidationError(
                    f"{name}.class",
                    error_msg
                )
            )
        except Exception as e:
            error_msg = f"Error validating class {class_path}: {str(e)}"
            logger.error(f"VALIDATION ERROR: {error_msg}")
            self.errors.append(
                ValidationError(
                    f"{name}.class",
                    error_msg
                )
            )

    def _validate_field_dependencies(self, config: Dict[str, Any]) -> None:
        """Validate field dependency configurations."""
        field_properties = config.get('field_properties', {})
        field_dependencies = config.get('field_dependencies', {})
        
        for field, deps in field_dependencies.items():
            if not isinstance(deps, list):
                self.errors.append(
                    ValidationError(
                        f"field_dependencies.{field}",
                        "Dependencies must be a list"
                    )
                )
                continue
                
            for dep in deps:
                if not isinstance(dep, dict):
                    self.errors.append(
                        ValidationError(
                            f"field_dependencies.{field}",
                            "Each dependency must be an object"
                        )
                    )
                    continue
                    
                # Validate dependency configuration
                if 'type' not in dep:
                    self.errors.append(
                        ValidationError(
                            f"field_dependencies.{field}",
                            "Dependency missing required 'type' field"
                        )
                    )
                    
                if 'target_field' not in dep:
                    self.errors.append(
                        ValidationError(
                            f"field_dependencies.{field}",
                            "Dependency missing required 'target_field' field"
                        )
                    )

    def get_entity_types(self) -> List[str]:
        """Get list of configured entity types.
        
        Returns:
            List of entity type names from configuration
        
        Raises:
            ConfigurationError: If configuration has not been loaded or validated
        """
        if self.config is None:
            raise ConfigurationError("Configuration has not been loaded")
        
        # Get entities from top-level config or system section
        entities = self.config.get('entities', {})
        if not entities and 'system' in self.config:
            entities = self.config['system'].get('entities', {})
            
        return list(entities.keys())

    def get_config(self) -> Dict[str, Any]:
        """Get the validated configuration.
        
        Returns:
            The validated configuration dictionary
        
        Raises:
            ConfigurationError: If configuration has not been loaded or validated
        """
        if self.config is None:
            raise ConfigurationError("Configuration has not been loaded")
        return self.config

def _check_implements_interface(cls: Type, interface: Type) -> bool:
    """Legacy interface check, use component_utils.implements decorator instead.
    
    This function will be deprecated. Use @implements decorator from component_utils instead.
    """
    from .component_utils import implements_interface
    return implements_interface(cls, interface)

def _interface_to_config_key(interface: Type) -> str:
    """Convert interface class to configuration key."""
    name = interface.__name__
    if name.startswith('I'):
        name = name[1:]  # Remove leading 'I'
    return ''.join(
        '_' + c.lower() if c.isupper() else c
        for c in name
    ).lstrip('_')

def validate_configuration(file_path: str, schema: Dict[str, Any]) -> List[ValidationError]:
    """Validate configuration file against schema and additional rules."""
    validator = ConfigValidator(schema)
    return validator.validate_file(file_path)

if __name__ == '__main__':
    print("This module is not meant to be executed directly.")
    print("The error you're seeing is due to a circular import with a local 'types.py' file.")
    print("\nPossible solutions:")
    print("1. Rename 'src/usaspending/types.py' to 'src/usaspending/type_definitions.py'")
    print("   and update all imports accordingly.")
    print("2. Import this module from another file instead of executing it directly.")
    sys.exit(1)