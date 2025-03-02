"""Exception classes for USASpending data processing."""

class USASpendingError(Exception):
    """Base exception class for USASpending errors."""
    pass

class ConfigurationError(USASpendingError):
    """Error in configuration validation or processing."""
    pass

class ValidationError(USASpendingError):
    """Error in data validation."""
    pass

class ProcessingError(USASpendingError):
    """Error in data processing."""
    pass

class EntityError(USASpendingError):
    """Error in entity processing."""
    pass

class ChunkingError(USASpendingError):
    """Error in chunk processing."""
    pass

class FileOperationError(USASpendingError):
    """Error in file operations."""
    pass

class EntityMappingError(EntityError):
    """Base class for entity mapping errors."""
    pass

class FieldMappingError(EntityMappingError):
    """Error in field mapping operations."""
    pass

class TransformationError(EntityMappingError):
    """Error in field value transformation."""
    pass

class TemplateError(EntityMappingError):
    """Error in template-based field mapping."""
    pass

class ReferenceError(EntityMappingError):
    """Error in entity reference mapping."""
    pass

class KeyGenerationError(EntityMappingError):
    """Error generating entity keys."""
    pass
