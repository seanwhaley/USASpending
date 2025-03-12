"""USASpending data processing package."""

# Import core elements through the core package
from .core import (
    # Core exceptions
    ConfigurationError,
    StorageError, 
    EntityError,
    MappingError,
    ValidationError,
    TransformationError,
    
    # Core types
    EntityData,
    EntityKey,
    ValidationResult,
    ValidationRule,
    TransformationRule,
    FieldType,
    
    # Core interfaces
    IEntityFactory,
    IEntityStore,
    IEntityMapper,
    IStorageStrategy,
    IConfigurable,
    IValidationMediator,
    
    # Core base classes
    BaseEntityFactory,
    BaseEntityStore,
    BaseEntityMapper,
    BaseValidator,
    
    # Core components
    ValidationService,
    RuleSet
)

# Import implementation components
from .entity_factory import EntityFactory
from .entity_store import EntityStore
from .entity_mapper import EntityMapper
from .entity_mediator import USASpendingEntityMediator
from .dictionary import Dictionary

# Define version
__version__ = '0.1.0'

__all__ = [
    # Core types
    'EntityData',
    'EntityKey',
    'ValidationResult',
    'ValidationRule',
    'TransformationRule',
    'FieldType',
    
    # Core interfaces
    'IEntityFactory',
    'IEntityStore',
    'IEntityMapper',
    'IStorageStrategy',
    'IConfigurable',
    'IValidationMediator',
    
    # Core base classes
    'BaseEntityFactory',
    'BaseEntityStore',
    'BaseEntityMapper',
    'BaseValidator',
    
    # Core components
    'ValidationService',
    'RuleSet',
    
    # Implementations
    'EntityFactory',
    'EntityStore',
    'EntityMapper',
    'USASpendingEntityMediator',
    'Dictionary',
    
    # Exceptions
    'ConfigurationError',
    'EntityError',
    'StorageError',
    'MappingError',
    'ValidationError',
    'TransformationError'
]