"""Core interface definitions."""
from typing import Dict, Any, List, Optional, Protocol, Generator, Type, Callable, Union, Sequence, Generic, TypeVar
from abc import ABC, abstractmethod
from .types import (
    EntityKey, EntityData, ValidationResult, ComponentConfig, 
    EntityType, RelationType, Cardinality, EntityRelationship,
    ValidationRule, RuleSet, RuleType, DataclassProtocol
)

# Type variable for entity objects
EntityT = TypeVar('EntityT', bound=DataclassProtocol)

class IConfigurable(Protocol):
    """Interface for configurable components."""
    @abstractmethod
    def configure(self, config: ComponentConfig) -> None:
        """Configure the component with structured configuration."""
        pass

class IValidator(Protocol):
    """Interface for validation components."""
    @abstractmethod
    def validate(self, entity_type: str, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate entity data."""
        pass
        
    @abstractmethod
    def get_validation_errors(self) -> List[str]:
        """Get validation errors."""
        pass
        
    @abstractmethod
    def add_validation_rule(self, rule: ValidationRule) -> None:
        """Add a validation rule."""
        pass
        
    @abstractmethod
    def remove_validation_rule(self, field_name: str, rule_type: RuleType) -> bool:
        """Remove a validation rule."""
        pass

class IValidationService(IValidator, Protocol):
    """Interface for validation service."""
    @abstractmethod
    def validate_field(self, entity_type: str, field_name: str, value: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate a single field."""
        pass
        
    @abstractmethod
    def validate_fields(self, entity_type: str, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate multiple fields."""
        pass
        
    @abstractmethod
    def register_custom_validator(self, name: str, validator: Callable[[Any, Dict[str, Any]], bool]) -> None:
        """Register a custom validator function."""
        pass

class IEntityFactory(Protocol):
    """Interface for entity creation."""
    @abstractmethod
    def create_entity(self, entity_type: EntityType, data: EntityData) -> Optional[EntityData]:
        """Create an entity instance."""
        pass
        
    @abstractmethod
    def register_entity(self, entity_type: EntityType, config: Dict[str, Any]) -> None:
        """Register an entity type configuration."""
        pass
        
    @abstractmethod
    def register_type(self, type_name: str, type_class: Type) -> None:
        """Register a custom type for validation."""
        pass
        
    @abstractmethod
    def get_entity_types(self) -> List[EntityType]:
        """Get list of registered entity types."""
        pass

class IEntityStore(Protocol):
    """Interface for entity storage."""
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

class IEntityMapper(Protocol):
    """Interface for entity mapping."""
    @abstractmethod
    def map_entity(self, entity_type: EntityType, data: Dict[str, Any]) -> Dict[str, Any]:
        """Map source data to entity format."""
        pass
        
    @abstractmethod
    def register_calculation_function(self, name: str, func: Callable) -> None:
        """Register a custom calculation function."""
        pass
        
    @abstractmethod
    def validate(self, entity_type: str, data: Dict[str, Any]) -> bool:
        """Validate data before mapping."""
        pass
        
    @abstractmethod
    def get_errors(self) -> List[str]:
        """Get mapping and validation errors."""
        pass

class IProcessor(Protocol):
    """Interface for data processing."""
    @abstractmethod
    def process_record(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single record."""
        pass
        
    @abstractmethod
    def process_batch(self, records: List[Dict[str, Any]], batch_size: Optional[int] = None) -> List[Dict[str, Any]]:
        """Process a batch of records."""
        pass
        
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        pass

class ICache(Protocol):
    """Interface for caching."""
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache."""
        pass
        
    @abstractmethod
    def put(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Add item to cache with optional TTL in seconds."""
        pass
        
    @abstractmethod
    def remove(self, key: str) -> bool:
        """Remove item from cache."""
        pass
        
    @abstractmethod
    def clear(self) -> None:
        """Clear cache."""
        pass

class ITransformer(Protocol):
    """Interface for data transformation."""
    @abstractmethod
    def transform(self, value: Any, parameters: Optional[Dict[str, Any]] = None) -> Any:
        """Transform a value."""
        pass
        
    @abstractmethod
    def validate(self, value: Any) -> bool:
        """Validate if value can be transformed."""
        pass
        
    @abstractmethod
    def get_supported_types(self) -> List[Type]:
        """Get supported input types."""
        pass

class IRelationshipManager(Protocol):
    """Interface for relationship management."""
    @abstractmethod
    def add_relationship(self, relationship: EntityRelationship) -> None:
        """Add a relationship definition."""
        pass
        
    @abstractmethod
    def get_relationships(self, entity_type: EntityType) -> Dict[str, EntityRelationship]:
        """Get relationships for entity type."""
        pass
        
    @abstractmethod
    def validate_relationships(self, entity_type: EntityType, data: EntityData) -> bool:
        """Validate entity relationships."""
        pass
        
    @abstractmethod
    def get_related_entities(self, entity_type: EntityType, entity_id: str, relation_type: Optional[RelationType] = None) -> Dict[str, List[EntityData]]:
        """Get related entities."""
        pass

class IValidationMediator(Protocol):
    """Interface for validation mediation."""
    @abstractmethod
    def validate(self, entity_type: Union[EntityType, str], data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate entity data against all registered rules and validators."""
        pass

    @abstractmethod
    def validate_entity(self, entity_type: str, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate complete entity data. Alias for validate()."""
        pass

    @abstractmethod
    def validate_field(self, field_name: str, value: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate a single field value."""
        pass
    
    @abstractmethod
    def get_validation_errors(self) -> List[str]:
        """Get validation error messages."""
        pass
        
    @abstractmethod
    def register_validator(self, entity_type: Union[EntityType, str], validator: IValidator) -> None:
        """Register a validator for an entity type."""
        pass

    @abstractmethod
    def register_rules(self, field_name: str, rules: Sequence[ValidationRule]) -> None:
        """Register validation rules for a field."""
        pass

    @abstractmethod
    def clear_errors(self) -> None:
        """Clear all validation errors."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, int]:
        """Get validation statistics."""
        pass

class IEntitySerializer(Generic[EntityT], ABC):
    """Interface for entity serialization."""
    
    @abstractmethod
    def __init__(self, entity_class: Type[EntityT]) -> None:
        """Initialize with entity type."""
        pass
    
    @property
    @abstractmethod
    def entity_type(self) -> str:
        """Get the entity type name."""
        pass
    
    @abstractmethod
    def to_dict(self, entity: EntityT) -> Dict[str, Any]:
        """Convert entity to dictionary."""
        pass
    
    @abstractmethod
    def from_dict(self, data: Dict[str, Any]) -> EntityT:
        """Create entity from dictionary."""
        pass

__all__ = [
    'IConfigurable',
    'IValidator',
    'IValidationService',
    'IEntityFactory',
    'IEntityStore', 
    'IEntityMapper',
    'IProcessor',
    'ICache',
    'ITransformer',
    'IRelationshipManager',
    'IValidationMediator',
    'IEntitySerializer'
]
