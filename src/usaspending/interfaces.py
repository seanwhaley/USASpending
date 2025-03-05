"""Core interfaces for the USASpending data processing system."""
from typing import Dict, Any, List, Optional, TypeVar, Generic, Iterator
from abc import ABC, abstractmethod

T = TypeVar('T')

class IEntityFactory(ABC):
    """Interface for creating entity instances."""
    
    @abstractmethod
    def create_entity(self, entity_type: str, data: Dict[str, Any]) -> Optional[Any]:
        """Create entity instance from data."""
        pass
    
    @abstractmethod
    def get_entity_types(self) -> List[str]:
        """Get available entity types."""
        pass

class ISchemaAdapter(ABC):
    """Interface for schema validation and transformation."""
    
    @abstractmethod
    def validate(self, value: Any, field_name: str) -> bool:
        """Validate value against schema."""
        pass
    
    @abstractmethod
    def transform(self, value: Any, field_name: str) -> Any:
        """Transform value according to schema."""
        pass
    
    @abstractmethod
    def get_validation_errors(self) -> List[str]:
        """Get validation error messages."""
        pass

class IFieldSelector(ABC):
    """Interface for selecting fields from data."""
    
    @abstractmethod
    def select_fields(self, data: Dict[str, Any], field_names: List[str]) -> Dict[str, Any]:
        """Select specific fields from data."""
        pass
    
    @abstractmethod
    def get_available_fields(self) -> List[str]:
        """Get list of available fields."""
        pass

class IEntityMapper(ABC):
    """Interface for mapping data to entities."""
    
    @abstractmethod
    def map_entity(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Map data to entity format."""
        pass
    
    @abstractmethod
    def get_mapping_errors(self) -> List[str]:
        """Get mapping error messages."""
        pass

class ITransformerFactory(ABC):
    """Interface for creating field transformers."""
    
    @abstractmethod
    def create_transformer(self, transform_type: str, config: Dict[str, Any]) -> Any:
        """Create transformer instance."""
        pass
    
    @abstractmethod
    def get_available_transforms(self) -> List[str]:
        """Get available transformation types."""
        pass

class IValidationService(ABC):
    """Interface for data validation."""
    
    @abstractmethod
    def validate_field(self, field_name: str, value: Any) -> List[str]:
        """Validate a single field value."""
        pass
    
    @abstractmethod
    def validate_record(self, record: Dict[str, Any]) -> List[str]:
        """Validate an entire record."""
        pass
    
    @abstractmethod
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        pass

class IDependencyManager(ABC):
    """Interface for managing field dependencies."""
    
    @abstractmethod
    def add_dependency(self, field_name: str, target_field: str,
                      dependency_type: str, validation_rule: Dict[str, Any]) -> None:
        """Add field dependency."""
        pass
    
    @abstractmethod
    def get_validation_order(self) -> List[str]:
        """Get ordered list of fields for validation."""
        pass
    
    @abstractmethod
    def validate_dependencies(self, record: Dict[str, Any],
                          adapters: Dict[str, ISchemaAdapter]) -> List[str]:
        """Validate field dependencies."""
        pass

class IDataProcessor(ABC):
    """Interface for data processing coordination."""
    
    @abstractmethod
    def process_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single data record."""
        pass
    
    @abstractmethod
    def process_batch(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process a batch of records."""
        pass
    
    @abstractmethod
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        pass

class IEntitySerializer(ABC, Generic[T]):
    """Interface for entity serialization."""
    
    @abstractmethod
    def to_dict(self, entity: T) -> Dict[str, Any]:
        """Convert entity to dictionary."""
        pass
    
    @abstractmethod
    def from_dict(self, data: Dict[str, Any]) -> T:
        """Create entity from dictionary."""
        pass
    
    @abstractmethod
    def to_json(self, entity: T) -> str:
        """Convert entity to JSON string."""
        pass
    
    @abstractmethod
    def from_json(self, json_str: str) -> T:
        """Create entity from JSON string."""
        pass
    
    @abstractmethod
    def to_csv_row(self, entity: T) -> List[str]:
        """Convert entity to CSV row."""
        pass
    
    @abstractmethod
    def from_csv_row(self, row: List[str], headers: List[str]) -> T:
        """Create entity from CSV row."""
        pass

class IEntityStore(ABC, Generic[T]):
    """Interface for entity storage."""
    
    @abstractmethod
    def save(self, entity_type: str, entity: T) -> str:
        """Save entity and return its ID."""
        pass
    
    @abstractmethod
    def get(self, entity_type: str, entity_id: str) -> Optional[T]:
        """Get entity by ID."""
        pass
    
    @abstractmethod
    def delete(self, entity_type: str, entity_id: str) -> bool:
        """Delete entity by ID."""
        pass
    
    @abstractmethod 
    def list(self, entity_type: str) -> Iterator[T]:
        """List all entities of a type."""
        pass
    
    @abstractmethod
    def count(self, entity_type: str) -> int:
        """Count entities of a type.
        
        Args:
            entity_type: Type of entities to count
            
        Returns:
            Number of entities of the specified type
        """
        pass

class IEntityCache(ABC, Generic[T]):
    """Interface for entity caching."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[T]:
        """Get entity from cache.
        
        Args:
            key: Cache key to lookup

        Returns:
            Cached entity or None if not found
        """
        pass
    
    @abstractmethod
    def put(self, key: str, entity: T) -> None:
        """Put entity in cache.
        
        Args:
            key: Cache key
            entity: Entity to cache
        """
        pass
    
    @abstractmethod
    def remove(self, key: str) -> None:
        """Remove entity from cache.
        
        Args:
            key: Cache key to remove
        """
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all entities from cache."""
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary of cache statistics
        """
        pass

class IChunkedWriter(ABC, Generic[T]):
    """Interface for chunked writing operations."""
    
    @abstractmethod
    def write_chunk(self, entities: List[T]) -> bool:
        """Write a chunk of entities.
        
        Args:
            entities: List of entities to write
            
        Returns:
            True if write successful, False otherwise
        """
        pass
    
    @abstractmethod
    def flush(self) -> None:
        """Flush any buffered entities."""
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get writing statistics.
        
        Returns:
            Dictionary of write operation statistics
        """
        pass

class IFieldValidator(ABC):
    """Interface for field validation operations."""
    
    @abstractmethod
    def validate_field(self, field_name: str, value: Any, 
                      validation_context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate a single field value.
        
        Args:
            field_name: Name of field to validate
            value: Value to validate
            validation_context: Optional validation context
            
        Returns:
            True if valid, False otherwise
        """
        pass

    @abstractmethod 
    def get_validation_errors(self) -> List[str]:
        """Get validation error messages.
        
        Returns:
            List of validation error messages
        """
        pass

class IValidator(ABC):
    """Interface for validators with caching support."""
    
    @abstractmethod
    def validate_field(self, field_name: str, value: Any,
                      validation_context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate a field value.
        
        Args:
            field_name: Name of field to validate
            value: Value to validate
            validation_context: Optional validation context
            
        Returns:
            True if valid, False otherwise
        """
        pass
    
    @abstractmethod
    def get_validation_errors(self) -> List[str]:
        """Get validation error messages.
        
        Returns:
            List of error messages
        """
        pass
        
    @abstractmethod
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics.
        
        Returns:
            Dictionary of validation statistics
        """
        pass
        
    @abstractmethod
    def clear_cache(self) -> None:
        """Clear validation cache."""
        pass

class IDataProcessor(ABC):
    """Interface for data processors."""
    
    @abstractmethod
    def process_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single data record.
        
        Args:
            record: Raw data record
            
        Returns:
            Processed record
        """
        pass
        
    @abstractmethod
    def process_batch(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process a batch of records.
        
        Args:
            records: List of raw data records
            
        Returns:
            List of processed records
        """
        pass
        
    @abstractmethod
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics.
        
        Returns:
            Dictionary of processing statistics
        """
        pass

class ISchemaAdapter(ABC):
    """Interface for schema adapters."""
    
    @abstractmethod
    def validate(self, value: Any, rules: Dict[str, Any],
                validation_context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate a value against schema rules.
        
        Args:
            value: Value to validate
            rules: Validation rules
            validation_context: Optional validation context
            
        Returns:
            True if valid, False otherwise
        """
        pass
        
    @abstractmethod
    def transform(self, value: Any) -> Any:
        """Transform a value according to schema rules.
        
        Args:
            value: Value to transform
            
        Returns:
            Transformed value
        """
        pass
        
    @abstractmethod
    def get_errors(self) -> List[str]:
        """Get validation/transformation errors.
        
        Returns:
            List of error messages
        """
        pass

class IEntityCache(Generic[T]):
    """Interface for entity caching."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[T]:
        """Get cached entity.
        
        Args:
            key: Cache key
            
        Returns:
            Cached entity or None if not found
        """
        pass
        
    @abstractmethod
    def put(self, key: str, entity: T) -> None:
        """Cache entity instance.
        
        Args:
            key: Cache key
            entity: Entity to cache
        """
        pass
        
    @abstractmethod
    def remove(self, key: str) -> None:
        """Remove entity from cache.
        
        Args:
            key: Cache key to remove
        """
        pass
        
    @abstractmethod
    def clear(self) -> None:
        """Clear all cached entities."""
        pass
        
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary of cache statistics
        """
        pass

class IEntitySerializer(Generic[T]):
    """Interface for entity serialization."""
    
    @abstractmethod
    def to_json(self, entity: T) -> str:
        """Serialize entity to JSON string.
        
        Args:
            entity: Entity to serialize
            
        Returns:
            JSON string representation
        """
        pass
        
    @abstractmethod
    def from_json(self, json_str: str) -> T:
        """Deserialize entity from JSON string.
        
        Args:
            json_str: JSON string to deserialize
            
        Returns:
            Deserialized entity
        """
        pass