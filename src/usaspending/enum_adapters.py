"""Enumerated value adapters for USASpending data validation."""
from typing import Dict, Any, List, Optional, Set, Union, Mapping
import enum

from .interfaces import ISchemaAdapter

class EnumFieldAdapter(ISchemaAdapter):
    """Adapter for enum field validation and transformation."""
    
    def __init__(self, valid_values: List[str], case_sensitive: bool = False):
        """Initialize enum field adapter.
        
        Args:
            valid_values: List of valid values
            case_sensitive: Whether comparison is case sensitive
        """
        self.case_sensitive = case_sensitive
        self.errors: List[str] = []
        
        # Store valid values with appropriate case handling
        if case_sensitive:
            self.valid_values: Set[str] = set(valid_values)
        else:
            self.valid_values: Set[str] = {v.lower() for v in valid_values if v is not None}
    
    def validate(self, value: Any, rules: Dict[str, Any],
                validation_context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate value against allowed enum values.
        
        Args:
            value: Value to validate
            rules: Validation rules
            validation_context: Optional validation context
            
        Returns:
            True if value is valid, False otherwise
        """
        self.errors = []
        
        if value is None:
            return True
            
        check_value = str(value)
        if not self.case_sensitive:
            check_value = check_value.lower()
            
        if check_value not in self.valid_values:
            self.errors.append(
                f"Value '{value}' not in valid values: {sorted(self.valid_values)}"
            )
            return False
            
        return True
    
    def transform(self, value: Any) -> Any:
        """Transform value to standardized enum value if possible.
        
        Args:
            value: Value to transform
            
        Returns:
            The standardized value if valid, None otherwise
        """
        if value is None:
            return None
            
        check_value = str(value)
        if not self.case_sensitive:
            check_value = check_value.lower()
            
        if check_value in self.valid_values:
            return value
            
        return None
    
    def get_errors(self) -> List[str]:
        """Get validation error messages.
        
        Returns:
            List of validation error messages
        """
        return self.errors.copy()

class MappedEnumFieldAdapter(EnumFieldAdapter):
    """Adapter for enum fields with value mapping."""
    
    def __init__(self, value_mapping: Dict[str, Any], case_sensitive: bool = False):
        """Initialize mapped enum field adapter.
        
        Args:
            value_mapping: Dictionary mapping input values to output values
            case_sensitive: Whether comparison is case sensitive
        """
        super().__init__(list(value_mapping.keys()), case_sensitive)
        self.value_mapping = value_mapping
        
        # Create case-insensitive mapping if needed
        if not case_sensitive:
            self.mapping = {k.lower(): v for k, v in value_mapping.items()}
        else:
            self.mapping = value_mapping
    
    def transform(self, value: Any, field_name: str) -> Any:
        """Transform value using the value mapping.
        
        Args:
            value: Value to transform
            field_name: Field name (not used in this implementation)
            
        Returns:
            Mapped value if input is valid, None otherwise
        """
        if value is None:
            return None
            
        check_value = str(value)
        if not self.case_sensitive:
            check_value = check_value.lower()
            
        return self.mapping.get(check_value)