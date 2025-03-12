"""Core exception classes."""

class USASpendingError(Exception):
    """Base exception for all USASpending errors."""
    pass

class ConfigError(USASpendingError):
    """Configuration related errors."""
    pass

class ValidationError(USASpendingError):
    """Validation related errors."""
    pass

class EntityError(USASpendingError):
    """Entity related errors."""
    pass

class AdapterError(USASpendingError):
    """Type adapter related errors."""
    pass

class FileOperationError(USASpendingError):
    """File operation related errors."""
    pass

class ProcessingError(USASpendingError):
    """Data processing related errors."""
    pass

class RelationshipError(USASpendingError):
    """Entity relationship related errors."""
    pass

class DependencyError(USASpendingError):
    """Field dependency related errors."""
    pass

class CacheError(USASpendingError):
    """Caching related errors."""
    pass 

class ComponentError(USASpendingError):
    """Component initialization/configuration errors."""
    pass

class TransformationError(USASpendingError):
    """Data transformation related errors."""
    pass

class MappingError(USASpendingError):
    """Exception raised when entity mapping operations fail."""
    pass

class StorageError(USASpendingError):
    """Exception raised when storage operations fail."""
    pass

class SerializationError(USASpendingError):
    """Exception raised when serialization operations fail."""
    pass

# Add alias for backward compatibility
ConfigurationError = ConfigError

__all__ = [
    'USASpendingError',
    'ConfigError',
    'ConfigurationError',  # Add to __all__
    'ValidationError',
    'EntityError',
    'AdapterError',
    'FileOperationError',
    'ProcessingError',
    'RelationshipError',
    'DependencyError',
    'CacheError',
    'ComponentError',
    'TransformationError',
    'MappingError',
    'StorageError',
    'SerializationError'
]
