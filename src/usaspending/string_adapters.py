"""String field adapters for USASpending data validation."""
from typing import Dict, Any, List, Optional, Pattern
import re

from .schema_adapters import PydanticAdapter, SchemaAdapterFactory, AdapterTransform
from .interfaces import ISchemaAdapter

class StringFieldAdapter(ISchemaAdapter):
    """Adapter for string field validation and transformation.
    
    Provides extended functionality for string fields beyond basic validation.
    """
    
    def __init__(self, min_length: Optional[int] = None,
                 max_length: Optional[int] = None,
                 pattern: Optional[str] = None,
                 strip: bool = True,
                 case_sensitive: bool = True,
                 trim_whitespace: bool = True):
        """Initialize string field adapter.
        
        Args:
            min_length: Minimum string length
            max_length: Maximum string length
            pattern: Regex pattern to validate against
            strip: Whether to strip whitespace
            case_sensitive: Whether validation is case sensitive
            trim_whitespace: Whether to trim whitespace during transform
        """
        self.min_length = min_length
        self.max_length = max_length
        self.pattern = pattern
        self._pattern_regex = re.compile(pattern) if pattern else None
        self.strip = strip
        self.case_sensitive = case_sensitive
        self.trim_whitespace = trim_whitespace
        self.errors: List[str] = []
    
    def validate(self, value: Any, field_name: str) -> bool:
        """Validate string value against configured rules.
        
        Args:
            value: String value to validate
            field_name: Name of the field for error messages
            
        Returns:
            Boolean indicating validation success
        """
        self.errors = []
        
        if value is None:
            return True
            
        # Convert to string if needed
        if not isinstance(value, str):
            value = str(value)
        
        # Apply case transformation for validation if needed
        check_value = value
        if not self.case_sensitive:
            check_value = value.lower()
        
        # Strip whitespace if configured
        if self.strip:
            check_value = check_value.strip()
        
        # Check length constraints
        if self.min_length is not None and len(check_value) < self.min_length:
            self.errors.append(
                f"{field_name}: String length {len(check_value)} is less than minimum {self.min_length}"
            )
            return False
            
        if self.max_length is not None and len(check_value) > self.max_length:
            self.errors.append(
                f"{field_name}: String length {len(check_value)} exceeds maximum {self.max_length}"
            )
            return False
            
        # Check pattern match
        if self._pattern_regex and not self._pattern_regex.match(check_value):
            self.errors.append(
                f"{field_name}: Value '{value}' does not match pattern: {self.pattern}"
            )
            return False
            
        return True
    
    def transform(self, value: Any, field_name: str) -> Optional[str]:
        """Transform value to appropriate string format.
        
        Args:
            value: Value to transform
            field_name: Name of the field (not used in this implementation)
            
        Returns:
            Transformed string or None
        """
        if value is None:
            return None
            
        result = str(value)
        
        if self.trim_whitespace:
            result = result.strip()
            
        return result
    
    def get_validation_errors(self) -> List[str]:
        """Get validation error messages.
        
        Returns:
            List of validation error messages
        """
        return self.errors.copy()