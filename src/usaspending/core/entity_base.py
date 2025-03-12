"""Core entity functionality and base implementations."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, TypeVar, Generic, Type, Union, Generator, Callable
from dataclasses import dataclass

from .types import (
    EntityData, EntityType, EntityRelationship, EntityConfig, 
    MappingResult, ComponentConfig, ValidationResult
)
from .interfaces import (
    IEntityFactory, IEntityStore, IEntityMapper,
    IValidationMediator
)
from .exceptions import EntityError

T = TypeVar('T')

@dataclass
class EntityMediatorConfig:
    """Entity mediator configuration."""
    enable_caching: bool = True
    enable_validation: bool = True
    strict_mode: bool = False
    batch_size: int = 1000

class BaseEntityMediator(ABC):
    """Base implementation for entity mediator."""
    
    def __init__(self) -> None:
        """Initialize base mediator."""
        self._errors: List[str] = []
        self._stats: Dict[str, int] = {
            "created": 0,
            "stored": 0,
            "retrieved": 0,
            "validated": 0,
            "errors": 0
        }
        self._initialized = False
        self._strict_mode = False

    def validate_entity(self, entity_type: str, data: Dict[str, Any]) -> bool:
        """Validate an entity."""
        if not self._initialized:
            self._errors.append("Mediator not initialized")
            return False

        try:
            return self._validate_entity_data(entity_type, data)
        except Exception as e:
            self._errors.append(f"Validation failed: {str(e)}")
            if self._strict_mode:
                raise
            return False

    @abstractmethod
    def _validate_entity_data(self, entity_type: str, data: Dict[str, Any]) -> bool:
        """Implementation of entity validation."""
        pass

    def validate_field(self, field_name: str, value: Any, entity_type: Optional[str] = None) -> bool:
        """Validate a single field."""
        if not self._initialized:
            self._errors.append("Mediator not initialized")
            return False

        try:
            return self._validate_field_value(field_name, value, entity_type)
        except Exception as e:
            self._errors.append(f"Field validation failed: {str(e)}")
            if self._strict_mode:
                raise
            return False

    @abstractmethod
    def _validate_field_value(self, field_name: str, value: Any, entity_type: Optional[str] = None) -> bool:
        """Implementation of field validation."""
        pass

    def get_validation_errors(self) -> List[str]:
        """Get validation errors."""
        return self._errors.copy()

    def get_stats(self) -> Dict[str, int]:
        """Get operation statistics."""
        return self._stats.copy()

    def clear_errors(self) -> None:
        """Clear error state."""
        self._errors.clear()

    @abstractmethod
    def process_entity(self, entity_type: EntityType, data: Dict[str, Any]) -> Optional[str]:
        """Process an entity."""
        pass

class BaseEntityFactory(IEntityFactory):
    """Base implementation of entity factory."""
    
    def __init__(self) -> None:
        """Initialize base factory."""
        self._entity_configs: Dict[str, EntityConfig] = {}
        self._errors: List[str] = []
        self._type_registry: Dict[str, Type] = {}
        
    @abstractmethod
    def create_entity(self, entity_type: EntityType, data: Dict[str, Any]) -> Optional[EntityData]:
        """Create an entity instance."""
        pass
        
    def register_entity_type(self, entity_type: EntityType, config: Dict[str, Any]) -> None:
        """Register an entity type configuration."""
        if not entity_type:
            raise EntityError("Entity type is required")
        if not config:
            raise EntityError("Entity configuration is required")
        self._entity_configs[str(entity_type)] = EntityConfig(**config)

    def register_type(self, type_name: str, type_class: Type) -> None:
        """Register a type for validation."""
        if not type_name:
            raise EntityError("Type name is required")
        if not type_class:
            raise EntityError("Type class is required")
        self._type_registry[type_name] = type_class
        
    def get_entity_config(self, entity_type: EntityType) -> Optional[EntityConfig]:
        """Get configuration for entity type."""
        return self._entity_configs.get(str(entity_type))
        
    def get_entity_types(self) -> List[EntityType]:
        """Get list of registered entity types."""
        return [EntityType(key) for key in self._entity_configs.keys()]
        
    def get_errors(self) -> List[str]:
        """Get error messages."""
        return self._errors.copy()
        
    def clear_errors(self) -> None:
        """Clear error state."""
        self._errors.clear()

class BaseEntityStore(IEntityStore, ABC):
    """Base implementation of entity storage."""
    
    def __init__(self) -> None:
        """Initialize base store."""
        self._errors: List[str] = []
        self._initialized = False
        
    def _check_initialized(self) -> None:
        """Check if store is initialized."""
        if not self._initialized:
            raise EntityError("Entity store is not initialized")

    @abstractmethod
    def save_entity(self, entity_type: EntityType, entity: EntityData) -> str:
        """Save an entity and return its ID."""
        pass

    @abstractmethod
    def get_entity(self, entity_type: EntityType, entity_id: str) -> Optional[EntityData]:
        """Get an entity by ID."""
        pass

    @abstractmethod
    def delete_entity(self, entity_type: EntityType, entity_id: str) -> bool:
        """Delete an entity."""
        pass

    @abstractmethod
    def list_entities(self, entity_type: EntityType) -> Generator[EntityData, None, None]:
        """Stream entities of a type."""
        pass

    @abstractmethod
    def count_entities(self, entity_type: EntityType) -> int:
        """Count entities of a type."""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Clean up resources."""
        pass
        
    def get_errors(self) -> List[str]:
        """Get error messages."""
        return self._errors.copy()
        
    def clear_errors(self) -> None:
        """Clear error state."""
        self._errors.clear()

class BaseCache(ABC):
    """Base implementation for cache."""
    
    def __init__(self, max_size: int = 10000, ttl_seconds: int = 3600) -> None:
        """Initialize cache."""
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._hits = 0
        self._misses = 0

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache."""
        pass

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Set item in cache."""
        pass

    @abstractmethod
    def remove(self, key: str) -> bool:
        """Remove item from cache."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all items from cache."""
        pass

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0
        
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "size": self._max_size,
            "ttl": self._ttl_seconds
        }

class BaseEntityMapper(IEntityMapper, ABC):
    """Base implementation for entity mapping."""
    
    def __init__(self) -> None:
        """Initialize entity mapper."""
        self._errors: List[str] = []
        self._calc_functions: Dict[str, Callable] = {}
        self._initialized = False
        
    @abstractmethod
    def map_entity(self, entity_type: EntityType, data: Dict[str, Any]) -> Dict[str, Any]:
        """Map source data to entity format."""
        pass
        
    def register_calculation_function(self, name: str, func: Callable) -> None:
        """Register a custom calculation function."""
        if not name:
            raise EntityError("Function name is required")
        if not callable(func):
            raise EntityError("Function must be callable")
        self._calc_functions[name] = func
        
    @abstractmethod
    def validate(self, entity_type: str, data: Dict[str, Any]) -> bool:
        """Validate data before mapping."""
        pass
        
    def get_errors(self) -> List[str]:
        """Get mapping and validation errors."""
        return self._errors.copy()
        
    def clear_errors(self) -> None:
        """Clear error state."""
        self._errors.clear()

@dataclass
class EntityMapping:
    """Entity field mapping configuration."""
    source_field: str
    target_field: str
    transforms: Optional[List[Dict[str, Any]]] = None
    required: bool = False
    default_value: Any = None

@dataclass
class EntityTransform:
    """Entity data transformation configuration."""
    transform_type: str
    parameters: Dict[str, Any]

@dataclass
class EntityValidation:
    """Entity validation configuration."""
    field: str
    rules: List[Dict[str, Any]]
    message: Optional[str] = None
    severity: str = "error"

__all__ = [
    'BaseEntityFactory',
    'BaseEntityStore', 
    'BaseCache',
    'BaseEntityMediator',
    'BaseEntityMapper',
    'EntityMediatorConfig',
    'EntityMapping',
    'EntityTransform',
    'EntityValidation'
]
