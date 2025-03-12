"""Core functionality for USASpending package."""

# Import and re-export core interfaces
from .interfaces import (
    IValidator, IValidationService, IEntityFactory, 
    IEntityStore, IEntityMapper, IProcessor, ICache, ITransformer, 
    IRelationshipManager, IValidationMediator
)

# Import and re-export configuration components
from .config import (
    IConfigurable, IConfigurationProvider, BaseConfigProvider, ComponentConfig, ConfigRegistry
)

# Import and re-export exception types
from .exceptions import (
    USASpendingError, ConfigurationError, StorageError, 
    EntityError, ValidationError, MappingError, TransformationError
)

# Import and re-export core types
from .types import (
    EntityData, EntityKey, ValidationResult, ValidationRule,
    TransformationRule, FieldType, EntityType, RuleSet, DataclassProtocol
)

# Import and re-export base implementations
from .entity_base import (
    BaseEntityFactory, BaseEntityStore, BaseCache,
    BaseEntityMapper, BaseEntityMediator
)

from .validation import (
    BaseValidator, ValidationService
)

from .storage import IStorageStrategy

from .entity_serializer import EntitySerializer

__all__ = [
    # Interfaces
    'IConfigurable', 'IValidator', 'IValidationService', 'IEntityFactory',
    'IEntityStore', 'IEntityMapper', 'IProcessor', 'ICache', 'ITransformer',
    'IRelationshipManager', 'IValidationMediator', 'IConfigurationProvider',
    
    # Exceptions
    'USASpendingError', 'ConfigurationError', 'StorageError', 
    'EntityError', 'ValidationError', 'MappingError', 'TransformationError',
    
    # Types
    'EntityData', 'EntityKey', 'ValidationResult', 'ValidationRule',
    'TransformationRule', 'FieldType', 'EntityType', 'ComponentConfig',
    'RuleSet', 'DataclassProtocol',
    
    # Base implementations
    'BaseEntityFactory', 'BaseEntityStore', 'BaseCache',
    'BaseEntityMapper', 'BaseEntityMediator', 'EntitySerializer',
    'BaseValidator', 'ValidationService',
    
    # Configuration
    'BaseConfigProvider', 'ConfigRegistry',
    
    #Storage
    'IStorageStrategy'
]
