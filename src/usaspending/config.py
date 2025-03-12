"""Configuration management system."""
from typing import Dict, Any, Optional, List, Type, Set
import logging
import os.path
from functools import lru_cache

from .core.config import (
    BaseConfigProvider,
    IConfigurable,
    ComponentConfig,
    ConfigRegistry
)
from .core.exceptions import ConfigurationError
from .core.utils import (
    safe_operation, 
    read_json_file, 
    read_yaml_file,
    ensure_directory
)

logger = logging.getLogger(__name__)

class ConfigurationProvider(BaseConfigProvider):
    """Manages configuration loading and validation."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration provider."""
        super().__init__()
        self._config: Dict[str, Any] = {}
        self._component_configs: Dict[str, ComponentConfig] = {}
        self._registry = ConfigRegistry()
        self._validation_errors: List[str] = []
        self._initialized = False
        self._schema_validated = False
        self._component_dependencies: Dict[str, Set[str]] = {}
        
        if config_path:
            self.load_config(config_path)

    @safe_operation
    def load_config(self, config_path: str) -> None:
        """Load configuration from path."""
        if not os.path.exists(config_path):
            raise ConfigurationError(f"Configuration file not found: {config_path}")

        # Load based on file extension
        if config_path.endswith('.json'):
            self._config = read_json_file(config_path)
        elif config_path.endswith(('.yml', '.yaml')):
            self._config = read_yaml_file(config_path)
        else:
            raise ConfigurationError(f"Unsupported configuration format: {config_path}")

        # Initialize component configurations
        self._initialize_component_configs()
        self._initialized = True

    def _initialize_component_configs(self) -> None:
        """Initialize component configurations."""
        components = self._config.get('components', {})
        for component_name, component_config in components.items():
            if isinstance(component_config, dict):
                self._component_configs[component_name] = ComponentConfig(
                    class_path=component_config.get('class_path', ''),
                    settings=component_config.get('settings', {})
                )

    @safe_operation
    def get_config(self, section: Optional[str] = None) -> Any:
        """Get configuration data."""
        if not self._initialized:
            raise ConfigurationError("Configuration not initialized")

        if section:
            return self._config.get(section, {})
        return self._config

    @safe_operation
    def get_component_config(self, component_name: str) -> Optional[ComponentConfig]:
        """Get component configuration."""
        return self._component_configs.get(component_name)

    def get_config_section(self, section_path: str, default: Any = None) -> Any:
        """Get nested configuration section using dot notation."""
        if not self._initialized:
            raise ConfigurationError("Configuration not initialized")

        current = self._config
        for key in section_path.split('.'):
            if not isinstance(current, dict):
                return default
            if key not in current:
                return default
            current = current[key]
        return current

    def register_component(self, name: str, component_class: Type[IConfigurable]) -> None:
        """Register a configurable component."""
        self._registry.register(name, component_class)

    def configure_component(self, name: str, component: IConfigurable) -> None:
        """Configure a component with its settings."""
        config = self.get_component_config(name)
        if config:
            component.configure(config)

    @safe_operation
    def validate_config(self) -> bool:
        """Validate configuration."""
        try:
            self._validation_errors.clear()
            
            # Check required sections
            required_sections = ['paths', 'components', 'entities']
            for section in required_sections:
                if section not in self._config:
                    self._validation_errors.append(f"Missing required section: {section}")

            # Run all validations unconditionally to collect all errors
            self._validate_paths_exist()
            self._validate_components_config()

            # Validate entities
            entities = self._config.get('entities', {})
            if not isinstance(entities, dict):
                self._validation_errors.append("Entities must be a dictionary")
            else:
                for entity_name, entity_config in entities.items():
                    if not isinstance(entity_config, dict):
                        self._validation_errors.append(f"Invalid entity configuration for {entity_name}")
                    else:
                        self._validate_entity_config(entity_name, entity_config)

            # Validate component dependencies
            self.validate_component_dependencies()

            # Return True only if there are no validation errors
            return len(self._validation_errors) == 0

        except Exception as e:
            logger.error(f"Configuration validation error: {str(e)}")
            self._validation_errors.append(f"Validation error: {str(e)}")
            return False

    def _validate_paths_exist(self) -> None:
        """Validate that configured paths exist or can be created."""
        paths = self._config.get('paths', {})
        for path_name, path in paths.items():
            if not isinstance(path, str):
                self._validation_errors.append(f"Invalid path value for {path_name}")
                continue
            
            try:
                ensure_directory(path)
            except Exception as e:
                self._validation_errors.append(f"Failed to create/verify path {path_name}: {str(e)}")

    def _validate_components_config(self) -> None:
        """Validate component configurations."""
        components = self._config.get('components', {})
        for component_name, component_config in components.items():
            if not isinstance(component_config, dict):
                self._validation_errors.append(f"Invalid component configuration for {component_name}")
            elif 'class_path' not in component_config:
                self._validation_errors.append(f"Missing class_path for component {component_name}")
            else:
                # Validate settings schema if defined
                settings = component_config.get('settings', {})
                if not isinstance(settings, dict):
                    self._validation_errors.append(f"Invalid settings for component {component_name}")

    def _validate_entity_config(self, entity_name: str, config: Dict[str, Any]) -> None:
        """Validate entity configuration."""
        # Check required entity sections
        required_sections = ['key_fields', 'field_mappings']
        for section in required_sections:
            if section not in config:
                self._validation_errors.append(f"Missing {section} in entity {entity_name}")

        # Validate field mappings
        field_mappings = config.get('field_mappings', {})
        if not isinstance(field_mappings, dict):
            self._validation_errors.append(f"Invalid field_mappings for entity {entity_name}")
        else:
            # Validate mapping types
            valid_mapping_types = {'direct', 'multi_source', 'object', 'reference'}
            for mapping_type in field_mappings:
                if mapping_type not in valid_mapping_types:
                    self._validation_errors.append(
                        f"Invalid mapping type '{mapping_type}' for entity {entity_name}"
                    )

        # Validate key fields
        key_fields = config.get('key_fields', [])
        if not isinstance(key_fields, list):
            self._validation_errors.append(f"key_fields must be a list for entity {entity_name}")

    def validate_component_dependencies(self) -> bool:
        """Validate component dependency relationships."""
        try:
            self._component_dependencies.clear()
            
            # Build dependency graph
            for component_name in self._component_configs:
                deps = self.get_component_dependencies(component_name)
                self._component_dependencies[component_name] = deps
            
            temp_visited: Set[str] = set()
            visited: Set[str] = set()

            def check_circular(component: str) -> bool:
                if component in temp_visited:
                    self._validation_errors.append(
                        f"Circular dependency detected involving component {component}"
                    )
                    return False
                if component in visited:
                    return True

                temp_visited.add(component)
                for dep in self._component_dependencies.get(component, set()):
                    if not check_circular(dep):
                        temp_visited.remove(component)
                        return False

                temp_visited.remove(component)
                visited.add(component)
                return True

            # Run circular dependency check for all components
            for component in self._component_configs:
                if not check_circular(component):
                    return False

            return True

        except Exception as e:
            logger.error(f"Error validating component dependencies: {str(e)}")
            self._validation_errors.append(f"Dependency validation error: {str(e)}")
            return False

    def get_component_dependencies(self, component_name: str) -> Set[str]:
        """Get direct dependencies for a component."""
        component_config = self._component_configs.get(component_name)
        if not component_config:
            return set()

        deps = set()
        settings = component_config.settings
        
        # Check for explicit dependencies
        if 'dependencies' in settings:
            deps.update(settings['dependencies'])

        # Look for implicit dependencies in settings
        for value in settings.values():
            if isinstance(value, dict) and 'component' in value:
                deps.add(value['component'])

        return deps

    def get_validation_errors(self) -> List[str]:
        """Get validation error messages."""
        return self._validation_errors.copy()

    @lru_cache(maxsize=100)
    def get_entity_config(self, entity_type: str) -> Optional[Dict[str, Any]]:
        """Get entity configuration with caching."""
        entities = self._config.get('entities', {})
        entity_config = entities.get(entity_type)
        if entity_config is not None and not isinstance(entity_config, dict):
            return None
        return entity_config

    def clear_entity_config_cache(self) -> None:
        """Clear the entity configuration cache."""
        self.get_entity_config.cache_clear()