"""Exceptions for the USASpending package."""

class USASpendingException(Exception):
    """Base exception for all USASpending exceptions."""
    pass

class ConfigurationError(USASpendingException):
    """Exception raised for configuration errors."""
    pass

class ValidationError(USASpendingException):
    """Exception raised for validation errors."""
    pass

class EntityMappingError(USASpendingException):
    """Exception raised for entity mapping errors."""
    pass

class TransformationError(USASpendingException):
    """Exception raised for data transformation errors."""
    pass

class ProcessingError(USASpendingException):
    """Exception raised for data processing errors."""
    pass

class EntityStoreError(USASpendingException):
    """Exception raised for entity storage errors."""
    pass

class SerializationError(USASpendingException):
    """Exception raised for serialization errors."""
    pass

class CacheError(USASpendingException):
    """Exception raised for caching errors."""
    pass

class DependencyError(USASpendingException):
    """Exception raised for dependency resolution errors."""
    pass

__all__ = [
    'USASpendingException',
    'ConfigurationError',
    'ValidationError', 
    'EntityMappingError',
    'TransformationError',
    'ProcessingError',
    'EntityStoreError',
    'SerializationError',
    'CacheError',
    'DependencyError'
]
