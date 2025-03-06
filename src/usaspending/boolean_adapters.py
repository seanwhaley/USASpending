"""Boolean field adapters for USASpending data validation."""
from typing import Dict, Any, List, Optional, Set, Union, Mapping

from .interfaces import ISchemaAdapter

class BooleanFieldAdapter(ISchemaAdapter):
    """Adapter for boolean field validation and transformation."""
    
    # Standard values representing True and False
    TRUE_VALUES = {'true', 'yes', '1', 'y', 't'}
    FALSE_VALUES = {'false', 'no', '0', 'n', 'f'}
    
    def __init__(self, true_values: Optional[Set[str]] = None,
                 false_values: Optional[Set[str]] = None):
        """Initialize boolean field adapter.
        
        Args:
            true_values: Set of values representing True
            false_values: Set of values representing False
        """
        self.true_values = true_values or self.TRUE_VALUES
        self.false_values = false_values or self.FALSE_VALUES
        self.errors: List[str] = []
    
    def validate(self, value: Any, field_name: str) -> bool:
        """Validate value as a boolean.
        
        Args:
            value: Value to validate
            field_name: Field name for error messages
            
        Returns:
            True if value is a valid boolean representation, False otherwise
        """
        self.errors = []
        
        if value is None:
            return True
            
        if isinstance(value, bool):
            return True
            
        if isinstance(value, (int, float)):
            # Accept numeric 0 and 1 as valid boolean values
            if value == 0 or value == 1:
                return True
        
        # Convert to lowercase string for string-based boolean values
        if isinstance(value, str):
            str_value = value.lower()
            if str_value in self.true_values or str_value in self.false_values:
                return True
                
        self.errors.append(
            f"{field_name}: Value '{value}' is not a valid boolean"
        )
        return False
    
    def transform(self, value: Any, field_name: str) -> Optional[bool]:
        """Transform value to a boolean.
        
        Args:
            value: Value to transform
            field_name: Field name (not used in this implementation)
            
        Returns:
            Boolean value if valid, None otherwise
        """
        if value is None:
            return None
            
        if isinstance(value, bool):
            return value
            
        if isinstance(value, (int, float)):
            if value == 1:
                return True
            elif value == 0:
                return False
            
        if isinstance(value, str):
            str_value = value.lower()
            if str_value in self.true_values:
                return True
            elif str_value in self.false_values:
                return False
                
        return None
    
    def get_validation_errors(self) -> List[str]:
        """Get validation error messages.
        
        Returns:
            List of validation error messages
        """
        return self.errors.copy()

class FormattedBooleanAdapter(BooleanFieldAdapter):
    """Adapter that formats boolean output in a specific way."""
    
    def __init__(self, true_format: str = 'Yes',
                 false_format: str = 'No',
                 **kwargs):
        """Initialize formatted boolean adapter.
        
        Args:
            true_format: String to output for True values
            false_format: String to output for False values
            **kwargs: Additional arguments for BooleanFieldAdapter
        """
        super().__init__(**kwargs)
        self.true_format = true_format
        self.false_format = false_format
    
    def transform(self, value: Any, field_name: str) -> Any:
        """Transform to formatted boolean string.
        
        Args:
            value: Value to transform
            field_name: Field name (not used in this implementation)
            
        Returns:
            Formatted string representation or None
        """
        bool_value = super().transform(value, field_name)
        
        if bool_value is None:
            return None
            
        return self.true_format if bool_value else self.false_format