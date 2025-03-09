"""Core interfaces for the USASpending system."""
from typing import Dict, Any, List, Optional, TypeVar, Generic, Iterator, Protocol
from abc import ABC, abstractmethod
from datetime import datetime

class USASpendingError(Exception):
    """Base exception for all USASpending errors."""
    pass

class ValidationError(USASpendingError):
    """Raised when validation fails."""
    pass

class EntityError(USASpendingError):
    """Raised for entity-related errors."""
    pass

class ConfigurationError(USASpendingError):
    """Raised for configuration-related errors."""
    pass

class ProcessingError(USASpendingError):
    """Raised for data processing errors."""
    pass

T = TypeVar('T')

class IEntityFactory(ABC):
    """Interface for creating entity instances.
    
    This interface defines the contract for factories that create entity instances
    from raw data. Implementations should handle type conversion, validation,
    and proper initialization of different entity types.
    """
    
    @abstractmethod
    def create_entity(self, entity_type: str, data: Dict[str, Any]) -> Optional[Any]:
        """Create entity instance from data.
        
        Args:
            entity_type: Type identifier for the entity to create
            data: Raw data to use for entity creation
            
        Returns:
            Created entity instance if successful, None if creation fails
            
        Raises:
            ValueError: If entity_type is unknown or data is invalid
            TypeError: If data is not in the expected format
        """
        pass
    
    @abstractmethod
    def get_entity_types(self) -> List[str]:
        """Get available entity types.
        
        Returns:
            List of supported entity type identifiers
        """
        pass

class IFieldSelector(ABC):
    """Interface for selecting fields from data.
    
    This interface defines methods for extracting specific fields from data records.
    Implementations should handle field name resolution, type conversion, and 
    validation of field existence.
    """
    
    @abstractmethod
    def select_fields(self, data: Dict[str, Any], field_names: List[str]) -> Dict[str, Any]:
        """Select specific fields from data.
        
        Args:
            data: Source data dictionary to select fields from
            field_names: Names of fields to select
            
        Returns:
            Dictionary containing only the requested fields
            
        Raises:
            KeyError: If a requested field does not exist
            ValueError: If data format is invalid
        """
        pass
    
    @abstractmethod
    def get_available_fields(self) -> List[str]:
        """Get list of available fields.
        
        Returns:
            List of all field names that can be selected
        """
        pass

class ISchemaAdapter(ABC):
    """Interface for schema adapters.
    
    Schema adapters handle validation and transformation of data values according to 
    schema rules. They enforce type constraints, format requirements, and other
    validation rules defined in the configuration.
    """
    
    @abstractmethod
    def validate(self, value: Any, rules: Dict[str, Any],
                validation_context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate a value against schema rules.
        
        Args:
            value: Value to validate
            rules: Dictionary of validation rules to apply
            validation_context: Optional context for complex validations
            
        Returns:
            bool: True if validation passed, False if failed
        """
        pass
        
    @abstractmethod
    def transform(self, value: Any) -> Any:
        """Transform a value according to schema rules.
        
        Args:
            value: Value to transform
            
        Returns:
            Transformed value according to schema rules
            
        Raises:
            ValueError: If value cannot be transformed
            TypeError: If value is not of expected type
        """
        pass
        
    @abstractmethod
    def get_errors(self) -> List[str]:
        """Get validation/transformation errors.
        
        Returns:
            List of error messages from validation/transformation attempts
        """
        pass

class IEntityMapper(ABC):
    """Interface for mapping data to entities.
    
    Entity mappers handle the transformation of raw data into entity objects.
    They manage field mapping, type conversion, and relationship resolution
    between different entity types.
    """
    
    @abstractmethod
    def map_entity(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Map data to entity format.
        
        Args:
            data: Raw data dictionary to map into entity format
            
        Returns:
            Dictionary containing mapped entity data
            
        Raises:
            ValueError: If required fields are missing
            TypeError: If field types are invalid
        """
        pass
    
    @abstractmethod
    def get_mapping_errors(self) -> List[str]:
        """Get mapping error messages.
        
        Returns:
            List of error messages from mapping operations
        """
        pass

class ITransformerFactory(ABC):
    """Interface for creating field transformers.
    
    This interface defines methods for creating and managing field value transformers.
    Transformers handle data type conversions, formatting, and other value 
    transformations according to configuration rules.
    """
    
    @abstractmethod
    def create_transformer(self, transform_type: str, config: Dict[str, Any]) -> Any:
        """Create transformer instance.
        
        Args:
            transform_type: Type identifier for the transformer to create
            config: Configuration dictionary for transformer initialization
            
        Returns:
            Initialized transformer instance
            
        Raises:
            ValueError: If transform_type is unknown
            ConfigurationError: If config is invalid
        """
        pass
    
    @abstractmethod
    def get_available_transforms(self) -> List[str]:
        """Get available transformation types.
        
        Returns:
            List of supported transformer type identifiers
        """
        pass

class IDependencyManager(ABC):
    """Interface for managing field dependencies.
    
    This interface defines methods for managing validation dependencies between fields.
    It handles dependency resolution order and validation of dependent field values.
    """
    
    @abstractmethod
    def add_dependency(self, field_name: str, target_field: str,
                      dependency_type: str, validation_rule: Dict[str, Any]) -> None:
        """Add field dependency.
        
        Args:
            field_name: Name of the dependent field
            target_field: Name of the field being depended on
            dependency_type: Type of dependency relationship
            validation_rule: Rules for validating the dependency
            
        Raises:
            ValueError: If field names are invalid
            ConfigurationError: If validation rule is invalid
        """ 
        pass
    
    @abstractmethod
    def get_validation_order(self) -> List[str]:
        """Get ordered list of fields for validation.
        
        Returns:
            List of field names in dependency-aware validation order
            
        Raises:
            ValueError: If circular dependencies are detected
        """ 
        pass
    
    @abstractmethod
    def validate_dependencies(self, record: Dict[str, Any],
                          adapters: Dict[str, ISchemaAdapter]) -> List[str]:
        """Validate field dependencies.
        
        Args:
            record: Record data containing fields to validate
            adapters: Dictionary of schema adapters for field validation
            
        Returns:
            List of validation error messages, empty if validation passed
            
        Raises:
            ValidationError: If dependency validation fails
            KeyError: If required fields are missing
        """ 
        pass

class IDataProcessor(ABC):
    """Interface for data processors.""" 
    
    @abstractmethod
    def process_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single data record.
        
        Args:
            record: Input record to process
            
        Returns:
            Processed record as dictionary, empty dict if skipped/failed
        """
        pass
        
    @abstractmethod
    def process_batch(self, records: List[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
        """Process a batch of records.
        
        Args:
            records: List of records to process
            
        Returns:
            Iterator yielding processed records, skipping failures
        """
        pass
        
    @abstractmethod
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics.
        
        Returns:
            Dictionary containing:
            - processed_records: Total records processed
            - failed_records: Number of failed records
            - skipped_records: Number of skipped records
            - entity_counts: Counter of entities by type
            - errors_by_type: Counter of errors by exception type
            - processing_rate: Records processed per second
            - batch_stats: Statistics about batch processing
            - mapping: Entity mapping statistics
            - error_samples: Sample of recent errors (if any)
            - current_batch: Info about current batch (if active)
        """
        pass

class IEntitySerializer(ABC, Generic[T]):
    """Interface for entity serialization.
    
    This interface defines methods for converting entities between different formats.
    Implementations should handle proper serialization/deserialization of all entity
    fields while maintaining data integrity and type safety.
    """
    
    @abstractmethod
    def to_dict(self, entity: T) -> Dict[str, Any]:
        """Convert entity to dictionary.
        
        Args:
            entity: Entity instance to convert
            
        Returns:
            Dictionary representation of the entity
            
        Raises:
            TypeError: If entity is not of expected type
            ValueError: If entity contains invalid data
        """
        pass
    
    @abstractmethod
    def from_dict(self, data: Dict[str, Any]) -> T:
        """Create entity from dictionary.
        
        Args:
            data: Dictionary containing entity data
            
        Returns:
            Created entity instance
            
        Raises:
            KeyError: If required fields are missing
            ValueError: If data values are invalid
            EntityError: If entity creation fails
        """
        pass
    
    @abstractmethod
    def to_json(self, entity: T) -> str:
        """Serialize entity to JSON string.
        
        Args:
            entity: Entity instance to serialize
            
        Returns:
            JSON string representation
            
        Raises:
            TypeError: If entity has non-serializable fields
            ValueError: If entity state is invalid
        """
        pass
    
    @abstractmethod
    def from_json(self, json_str: str) -> T:
        """Deserialize entity from JSON string.
        
        Args:
            json_str: JSON string to deserialize
            
        Returns:
            Created entity instance
            
        Raises:
            ValueError: If JSON is malformed
            EntityError: If entity creation fails
        """
        pass
    
    @abstractmethod
    def to_csv_row(self, entity: T) -> List[str]:
        """Convert entity to CSV row.
        
        Args:
            entity: Entity instance to convert
            
        Returns:
            List of field values in CSV column order
            
        Raises:
            TypeError: If entity has incompatible field types
            ValueError: If entity state is invalid
        """
        pass
    
    @abstractmethod
    def from_csv_row(self, row: List[str], headers: List[str]) -> T:
        """Create entity from CSV row.
        
        Args:
            row: List of field values
            headers: List of column names
            
        Returns:
            Created entity instance
            
        Raises:
            ValueError: If row data is invalid
            KeyError: If required headers are missing
            EntityError: If entity creation fails
        """
        pass

class IEntityStore(ABC, Generic[T]):
    """Interface for entity storage.
    
    This interface defines methods for persistent storage and retrieval of entities.
    Implementations should handle proper storage, indexing, and lifecycle management
    of entity instances.
    """
    
    @abstractmethod
    def save(self, entity_type: str, entity: T) -> str:
        """Save entity and return its ID.
        
        Args:
            entity_type: Type identifier for the entity
            entity: Entity instance to save
            
        Returns:
            Unique identifier for the saved entity
            
        Raises:
            ValueError: If entity_type is unknown
            EntityError: If save operation fails
            TypeError: If entity is not of expected type
        """
        pass
    
    @abstractmethod
    def get(self, entity_type: str, entity_id: str) -> Optional[T]:
        """Get entity by ID.
        
        Args:
            entity_type: Type identifier for the entity
            entity_id: Unique identifier of entity to retrieve
            
        Returns:
            Retrieved entity instance if found, None otherwise
            
        Raises:
            ValueError: If entity_type is unknown
            EntityError: If retrieval fails
        """
        pass
    
    @abstractmethod
    def delete(self, entity_type: str, entity_id: str) -> bool:
        """Delete entity by ID.
        
        Args:
            entity_type: Type identifier for the entity
            entity_id: Unique identifier of entity to delete
            
        Returns:
            True if entity was deleted, False if not found
            
        Raises:
            ValueError: If entity_type is unknown
            EntityError: If deletion fails
        """
        pass
    
    @abstractmethod 
    def list(self, entity_type: str) -> Iterator[T]:
        """List all entities of a type.
        
        Args:
            entity_type: Type identifier for entities to list
            
        Returns:
            Iterator yielding entity instances
            
        Raises:
            ValueError: If entity_type is unknown
            EntityError: If listing fails
        """
        pass
    
    @abstractmethod
    def count(self, entity_type: str) -> int:
        """Count entities of a type.
        
        Args:
            entity_type: Type identifier for entities to count
            
        Returns:
            Number of entities of specified type
            
        Raises:
            ValueError: If entity_type is unknown
            EntityError: If counting fails
        """
        pass

class IEntityCache(ABC, Generic[T]):
    """Interface for entity caching.
    
    This interface defines methods for temporary storage and retrieval of entities.
    Implementations should handle efficient caching strategies, memory management,
    and cache invalidation policies.
    """
    
    @abstractmethod
    def get(self, key: str) -> Optional[T]:
        """Get cached entity.
        
        Args:
            key: Cache key for the entity
            
        Returns:
            Cached entity if found, None otherwise
            
        Raises:
            ValueError: If key format is invalid
            EntityError: If cache access fails
        """
        pass
    
    @abstractmethod
    def put(self, key: str, entity: T) -> None:
        """Cache entity instance.
        
        Args:
            key: Cache key for the entity
            entity: Entity instance to cache
            
        Raises:
            ValueError: If key format is invalid
            TypeError: If entity is not of expected type
            EntityError: If cache operation fails
        """
        pass
    
    @abstractmethod
    def remove(self, key: str) -> None:
        """Remove entity from cache.
        
        Args:
            key: Cache key of entity to remove
            
        Raises:
            ValueError: If key format is invalid
            EntityError: If removal fails
        """
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all cached entities.
        
        Raises:
            EntityError: If cache clear operation fails
        """
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary containing:
            - size: Current number of cached entities
            - hits: Number of cache hits
            - misses: Number of cache misses
            - hit_rate: Cache hit rate percentage
            - memory_usage: Estimated memory usage
            - evictions: Number of cache evictions
            
        Raises:
            EntityError: If stats collection fails
        """
        pass

class IChunkedWriter(ABC, Generic[T]):
    """Interface for chunked writing operations.
    
    This interface defines methods for efficiently writing large collections of
    entities in chunks. Implementations should handle buffering, batch processing,
    and resource management for optimal performance.
    """
    
    @abstractmethod
    def write_chunk(self, entities: List[T]) -> bool:
        """Write a chunk of entities.
        
        Args:
            entities: List of entities to write
            
        Returns:
            True if chunk was written successfully, False otherwise
            
        Raises:
            ValueError: If chunk size exceeds limits
            TypeError: If entities are not of expected type
            ProcessingError: If write operation fails
        """
        pass
    
    @abstractmethod
    def flush(self) -> None:
        """Flush any buffered entities.
        
        Ensures all pending writes are completed and resources are properly released.
        
        Raises:
            ProcessingError: If flush operation fails
        """
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get writing statistics.
        
        Returns:
            Dictionary containing:
            - total_chunks: Number of chunks written
            - total_entities: Total entities written
            - failed_chunks: Number of failed chunk writes
            - avg_chunk_size: Average entities per chunk
            - write_rate: Entities written per second
            - buffer_size: Current buffer utilization
            
        Raises:
            ProcessingError: If stats collection fails
        """
        pass

class IFieldValidator(Protocol):
    """Interface for field validation.
    
    This interface defines methods for validating individual field values.
    Implementations should handle type-specific validation rules and maintain
    context-aware validation state.
    """
    
    @abstractmethod
    def validate_field(self, field_name: str, value: Any,
                      validation_context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate a single field value.
        
        Args:
            field_name: Name of the field to validate
            value: Value to validate
            validation_context: Optional context data for validation
            
        Returns:
            True if validation passed, False otherwise
            
        Raises:
            ValidationError: If validation fails due to rule violation
            ValueError: If field name is unknown
        """
        ...

    @abstractmethod
    def get_validation_errors(self) -> List[str]:
        """Get validation error messages.
        
        Returns:
            List of validation error messages from last validation attempt
        """
        ...

class IValidatable(Protocol):
    """Interface for validatable entities.
    
    This interface defines methods that must be implemented by any entity
    that supports validation. It provides a standard way to validate entity
    state and access validation results.
    """
    
    @abstractmethod
    def validate(self) -> bool:
        """Validate the entity.
        
        Performs validation of the entity's current state according to
        configured validation rules.
        
        Returns:
            True if validation passed, False otherwise
            
        Raises:
            ValidationError: If validation fails due to rule violation
        """
        ...

    @abstractmethod
    def get_validation_errors(self) -> List[str]:
        """Get validation errors.
        
        Returns:
            List of validation error messages from last validation
        """
        ...

class IValidationMediator(Protocol):
    """Interface for validation mediation.
    
    This interface defines methods for coordinating validation operations
    across different components. It handles validation routing, aggregation
    of validation results, and validation context management.
    """
    
    @abstractmethod
    def validate_entity(self, entity_type: str, data: Dict[str, Any]) -> bool:
        """Validate an entity.
        
        Args:
            entity_type: Type identifier for the entity
            data: Entity data to validate
            
        Returns:
            True if validation passed, False otherwise
            
        Raises:
            ValidationError: If validation fails
            ValueError: If entity_type is unknown
        """
        ...
        
    @abstractmethod
    def validate_field(self, field_name: str, value: Any, entity_type: Optional[str] = None) -> bool:
        """Validate a field value.
        
        Args:
            field_name: Name of field to validate
            value: Value to validate
            entity_type: Optional entity type for context
            
        Returns:
            True if validation passed, False otherwise
            
        Raises:
            ValidationError: If validation fails
            ValueError: If field name is unknown
        """
        ...
        
    @abstractmethod
    def get_validation_errors(self) -> List[str]:
        """Get validation errors.
        
        Returns:
            List of validation error messages from last validation
        """
        ...

class IEntityMediator(Protocol):
    """Interface for entity system mediation.
    
    This interface defines methods for coordinating operations between
    different parts of the entity system. It handles entity lifecycle
    management, routing of entity operations, and system-wide entity state.
    """
    
    @abstractmethod
    def create_entity(self, entity_type: str, data: Dict[str, Any]) -> Any:
        """Create an entity instance.
        
        Args:
            entity_type: Type identifier for entity to create
            data: Data to initialize entity with
            
        Returns:
            Created entity instance
            
        Raises:
            EntityError: If entity creation fails
            ValueError: If entity_type is unknown
            TypeError: If data is invalid
        """
        ...
        
    @abstractmethod
    def store_entity(self, entity: Any) -> str:
        """Store an entity.
        
        Args:
            entity: Entity instance to store
            
        Returns:
            Unique identifier for stored entity
            
        Raises:
            EntityError: If storage fails
            TypeError: If entity is invalid
        """
        ...
        
    @abstractmethod
    def get_entity(self, entity_type: str, entity_id: str) -> Optional[Any]:
        """Retrieve an entity.
        
        Args:
            entity_type: Type identifier for entity
            entity_id: Unique identifier of entity
            
        Returns:
            Retrieved entity if found, None otherwise
            
        Raises:
            EntityError: If retrieval fails
            ValueError: If entity_type is unknown
        """
        ...

class IConfigurationProvider(Protocol):
    """Interface for configuration management.
    
    This interface defines methods for accessing and validating system configuration.
    Implementations should handle configuration loading, validation, and provide
    typed access to configuration values.
    """
    
    @abstractmethod
    def get_config(self, section: Optional[str] = None) -> Dict[str, Any]:
        """Get configuration data.
        
        Args:
            section: Optional section name to retrieve specific config subset
            
        Returns:
            Dictionary containing configuration data
            
        Raises:
            ConfigurationError: If configuration is invalid or cannot be loaded
            ValueError: If section name is invalid
        """
        ...
        
    @abstractmethod
    def validate_config(self) -> bool:
        """Validate configuration.
        
        Performs validation of all configuration values against defined rules
        and constraints.
        
        Returns:
            True if configuration is valid, False otherwise
            
        Raises:
            ConfigurationError: If validation process fails
        """
        ...
        
    @abstractmethod
    def get_validation_errors(self) -> List[str]:
        """Get configuration validation errors.
        
        Returns:
            List of validation error messages from last validation
        """
        ...

class IProcessingSession(Protocol):
    """Interface for managing data processing sessions.
    
    This interface defines methods for controlling and monitoring data processing
    sessions. It handles session lifecycle, statistics collection, and resource
    management across processing operations.
    """
    
    @abstractmethod
    def start_session(self) -> None:
        """Start a processing session.
        
        Initializes a new processing session and prepares resources.
        
        Raises:
            ProcessingError: If session cannot be started or resources unavailable
        """
        ...
        
    @abstractmethod
    def end_session(self) -> None:
        """End a processing session.
        
        Cleanly terminates the session and releases resources.
        
        Raises:
            ProcessingError: If session cannot be ended properly
        """
        ...
        
    @abstractmethod
    def is_active(self) -> bool:
        """Check if session is active.
        
        Returns:
            True if session is currently active, False otherwise
        """
        ...
        
    @abstractmethod
    def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics.
        
        Returns:
            Dictionary containing:
            - start_time: Session start timestamp 
            - end_time: Session end timestamp
            - duration_seconds: Session duration
            - processing_rate: Records/second
            - batch_stats: Batch processing statistics
            - memory_usage: Session memory utilization
            - resource_stats: Resource utilization metrics
            
        Raises:
            ProcessingError: If stats collection fails
        """
        ...

class IBatchProcessor(Protocol):
    """Interface for batch processing operations.
    
    This interface defines methods for processing data in batches. Implementations
    should handle batch initialization, processing, error handling, and provide
    detailed statistics about batch operations.
    """
    
    @abstractmethod
    def initialize_batch(self) -> None:
        """Initialize a new batch processing operation.
        
        Prepares resources and state for processing a new batch of records.
        
        Raises:
            ProcessingError: If batch initialization fails
            ResourceError: If required resources are unavailable
        """
        ...
        
    @abstractmethod
    def process_batch(self, records: List[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
        """Process a batch of records.
        
        Args:
            records: List of records to process
            
        Returns:
            Iterator yielding processed records
            
        Raises:
            ProcessingError: If batch processing fails
            ValidationError: If records fail validation
        """
        ...
        
    @abstractmethod
    def get_batch_stats(self) -> Dict[str, Any]:
        """Get batch processing statistics.
        
        Returns:
            Dictionary containing:
            - total_batches: Total number of batches processed
            - failed_batches: Number of failed batches
            - avg_batch_time: Average processing time per batch
            - current_batch: Current batch information if active
            - success_rate: Percentage of successful batches
            - throughput: Records processed per second
            
        Raises:
            ProcessingError: If stats collection fails
        """
        ...
        
    @abstractmethod
    def get_batch_errors(self) -> List[Dict[str, Any]]:
        """Get batch processing errors.
        
        Returns:
            List of error details including:
            - batch_number: Batch where error occurred
            - error: Error message
            - error_type: Type of error
            - timestamp: When error occurred
            - affected_records: Number of records affected
            - stack_trace: Optional stack trace for debugging
            
        Raises:
            ProcessingError: If error retrieval fails
        """
        ...

class IValidator(ABC):
    """Interface for validation components.""" 
    
    @abstractmethod
    def validate_record(self, record: Dict[str, Any]) -> bool:
        """Validate a record against configured rules.
        
        Args:
            record: Record data to validate
            
        Returns:
            bool: True if validation passed, False otherwise
        """
        pass
        
    @abstractmethod
    def get_validation_errors(self) -> List[str]:
        """Get validation error messages.
        
        Returns:
            List[str]: List of validation error messages
        """
        pass
        
    @abstractmethod
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics.
        
        Returns:
            Dict containing:
            - total_validations: Number of validations performed
            - failed_validations: Number of failed validations
            - success_rate: Percentage of successful validations
            - average_duration_ms: Average validation duration
            - cache_stats: Cache hit/miss statistics
        """
        pass