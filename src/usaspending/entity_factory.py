"""Entity factory for creating entity instances from data."""
from typing import Dict, Any, List, Optional, Type, Callable
from dataclasses import dataclass, field
import importlib
import inspect

from . import get_logger, ConfigurationError
from .interfaces import IEntityFactory
from .component_utils import implements

logger = get_logger(__name__)

# Current module to help with handling imports
__MODULE_PATH__ = __name__.rsplit('.', 1)[0]  # Gets 'usaspending' from 'usaspending.entity_factory'

@dataclass
class EntityConfig:
    """Configuration for entity creation."""
    entity_class: Type[Any]
    field_mapping: Dict[str, str] = field(default_factory=dict)
    required_fields: List[str] = field(default_factory=list)
    defaults: Dict[str, Any] = field(default_factory=dict)
    validators: Dict[str, Callable[[Any], bool]] = field(default_factory=dict)

@implements(IEntityFactory)
class EntityFactory(IEntityFactory):
    """Creates entity instances from data using configuration."""
    
    def __init__(self):
        """Initialize entity factory."""
        self.configs: Dict[str, EntityConfig] = {}
        self.creation_errors: List[str] = []
    
    def register_entity(self, entity_type: str, config: EntityConfig) -> None:
        """Register an entity configuration."""
        self.configs[entity_type] = config
    
    def create_entity(self, entity_type: str, data: Dict[str, Any]) -> Optional[Any]:
        """Create an entity instance from data."""
        self.creation_errors.clear()
        
        config = self.configs.get(entity_type)
        if not config:
            self.creation_errors.append(f"Unknown entity type: {entity_type}")
            return None
            
        # Validate required fields
        missing_fields = [field for field in config.required_fields if field not in data]
        if missing_fields:
            self.creation_errors.append(f"Missing required fields: {', '.join(missing_fields)}")
            return None
            
        # Prepare entity data
        entity_data = {}
        
        # Apply field mapping
        for target_field, source_field in config.field_mapping.items():
            if source_field in data:
                entity_data[target_field] = data[source_field]
            elif target_field in config.defaults:
                entity_data[target_field] = config.defaults[target_field]
                
        # Copy unmapped fields
        for field, value in data.items():
            if field not in config.field_mapping.values():
                entity_data[field] = value
                
        # Validate fields
        for field, validator in config.validators.items():
            if field not in entity_data:
                continue
                
            try:
                if not validator(entity_data[field]):
                    self.creation_errors.append(f"Validation failed for field: {field}")
                    return None
            except Exception as e:
                self.creation_errors.append(f"Validation error for field {field}: {str(e)}")
                return None
                
        # Create entity instance
        try:
            return config.entity_class(**entity_data)
        except Exception as e:
            self.creation_errors.append(f"Error creating entity: {str(e)}")
            return None
    
    def get_entity_types(self) -> List[str]:
        """Get available entity types."""
        return list(self.configs.keys())
        
    def get_creation_errors(self) -> List[str]:
        """Get entity creation error messages."""
        return self.creation_errors.copy()

class EntityFactoryBuilder:
    """Builder for creating configured EntityFactory instances."""
    
    def __init__(self):
        """Initialize builder."""
        self.factory = EntityFactory()
        
    def with_entity(self, entity_type: str, entity_class: Type[Any],
                   field_mapping: Optional[Dict[str, str]] = None,
                   required_fields: Optional[List[str]] = None,
                   defaults: Optional[Dict[str, Any]] = None,
                   validators: Optional[Dict[str, Callable[[Any], bool]]] = None) -> 'EntityFactoryBuilder':
        """Add entity configuration."""
        config = EntityConfig(
            entity_class=entity_class,
            field_mapping=field_mapping or {},
            required_fields=required_fields or [],
            defaults=defaults or {},
            validators=validators or {}
        )
        self.factory.register_entity(entity_type, config)
        return self
        
    def with_dataclass(self, entity_type: str, dataclass_path: str) -> 'EntityFactoryBuilder':
        """Add entity configuration from dataclass path."""
        try:
            # Support both absolute and relative imports
            if dataclass_path.startswith("usaspending."):
                # Handle case when config uses direct usaspending. imports
                module_path, class_name = dataclass_path.rsplit('.', 1)
                module = importlib.import_module(module_path)
            else:
                # Handle case when full path is provided
                module_path, class_name = dataclass_path.rsplit('.', 1)
                module = importlib.import_module(module_path)
            
            entity_class = getattr(module, class_name)
            
            # Get required fields from dataclass
            required_fields = []
            if hasattr(entity_class, '__dataclass_fields__'):
                required_fields = [
                    name for name, field in entity_class.__dataclass_fields__.items()
                    if field.default == field.default_factory == inspect.Parameter.empty
                ]
                
            return self.with_entity(
                entity_type=entity_type,
                entity_class=entity_class,
                required_fields=required_fields
            )
            
        except Exception as e:
            logger.error(f"Error loading dataclass {dataclass_path}: {e}")
            return self
        
    def build(self) -> EntityFactory:
        """Create EntityFactory instance."""
        return self.factory

# Factory method to create an instance from the configuration
def create_entity_factory_from_config(config: Dict[str, Any]) -> EntityFactory:
    """Create an EntityFactory instance from configuration."""
    builder = EntityFactoryBuilder()
    
    # Handle configuration from YAML system.entity_factory section
    if isinstance(config, dict) and "config" in config:
        config = config["config"]
    
    # Process entity configurations if available
    if "entities" in config:
        for entity_type, entity_config in config["entities"].items():
            class_path = entity_config.get("class")
            if class_path:
                builder.with_dataclass(entity_type, class_path)
    
    # Process type adapters if available
    if "type_adapters" in config:
        # Implementation for type adapters
        pass
    
    return builder.build()