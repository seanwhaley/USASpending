"""Base validation functionality for field validation."""
from typing import Dict, Any, List, Optional, Set
from .interfaces import IFieldValidator
from .exceptions import ValidationError
from .logging_config import get_logger

logger = get_logger(__name__)

class BaseValidator(IFieldValidator):
    """Base validator implementation that can be used by both EntityMapper and ValidationService."""
    
    def __init__(self):
        """Initialize validator."""
        self.errors: List[str] = []
        self.validation_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        self._adapters: Dict[str, Any] = {}
        self._validated_fields: Set[str] = set()

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
        # Check cache first
        cache_key = self._get_cache_key(field_name, value, validation_context)
        cached_result = self.validation_cache.get(cache_key)
        if cached_result is not None:
            self._cache_hits += 1
            self.errors.extend(cached_result.get('errors', []))
            return cached_result.get('valid', False)

        self._cache_misses += 1
        is_valid = self._validate_field_value(field_name, value, validation_context)
        
        # Cache result
        self.validation_cache[cache_key] = {
            'valid': is_valid,
            'errors': self.errors.copy(),
            'timestamp': validation_context.get('timestamp') if validation_context else None
        }
        
        self._validated_fields.add(field_name)
        return is_valid

    def get_validation_errors(self) -> List[str]:
        """Get validation error messages.
        
        Returns:
            List of validation error messages
        """
        return self.errors.copy()

    def _validate_field_value(self, field_name: str, value: Any,
                            validation_context: Optional[Dict[str, Any]] = None) -> bool:
        """Override this method in subclasses to implement specific validation logic.
        
        Args:
            field_name: Name of field to validate
            value: Value to validate
            validation_context: Optional validation context
            
        Returns:
            True if valid, False otherwise
        """
        return True  # Base implementation assumes valid

    def _get_cache_key(self, field_name: str, value: Any,
                       validation_context: Optional[Dict[str, Any]] = None) -> str:
        """Generate cache key for field validation.
        
        Args:
            field_name: Name of field
            value: Field value
            validation_context: Optional validation context
            
        Returns:
            Cache key string
        """
        context_str = str(sorted(validation_context.items())) if validation_context else ''
        return f"{field_name}:{str(value)}:{context_str}"

    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics.
        
        Returns:
            Dictionary of validation statistics
        """
        return {
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'validated_fields': len(self._validated_fields),
            'error_count': len(self.errors),
            'cache_size': len(self.validation_cache)
        }

    def register_adapter(self, field_pattern: str, adapter: Any) -> None:
        """Register a schema adapter for field validation.
        
        Args:
            field_pattern: Pattern to match field names
            adapter: Schema adapter instance
        """
        self._adapters[field_pattern] = adapter

    def clear_cache(self) -> None:
        """Clear validation cache."""
        self.validation_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        
    def _get_adapter(self, field_name: str) -> Optional[Any]:
        """Get appropriate adapter for field.
        
        Args:
            field_name: Field name to get adapter for
            
        Returns:
            Schema adapter instance or None if not found
        """
        # Direct field match
        if field_name in self._adapters:
            return self._adapters[field_name]
            
        # Pattern matching
        for pattern, adapter in self._adapters.items():
            if '*' in pattern:
                import fnmatch
                if fnmatch.fnmatch(field_name, pattern):
                    return adapter
                    
        return None

# Default implementation
Validator = BaseValidator  # Use BaseValidator as the default implementation