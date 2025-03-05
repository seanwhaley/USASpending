"""Schema adapters for validating and transforming different data types."""
from typing import Dict, Any, List, Optional, Type, Callable, TypeVar, Generic
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
import re

from .interfaces import ISchemaAdapter
from .logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar('T')
R = TypeVar('R')

class AdapterTransform(Generic[T, R]):
    """Utility class for transforming data from one type to another."""
    
    def __init__(self, transform_func: Callable[[T], R], 
                 input_type: Type[T] = None, 
                 output_type: Type[R] = None):
        """Initialize transform function.
        
        Args:
            transform_func: Function to transform data
            input_type: Expected input type (optional)
            output_type: Expected output type (optional)
        """
        self.transform_func = transform_func
        self.input_type = input_type
        self.output_type = output_type
    
    def __call__(self, value: T) -> R:
        """Apply transformation to value.
        
        Args:
            value: Value to transform
            
        Returns:
            Transformed value
        """
        if value is None:
            return None
            
        if self.input_type and not isinstance(value, self.input_type):
            logger.warning(f"Value {value} is not of expected input type {self.input_type}")
            
        result = self.transform_func(value)
        
        if self.output_type and result is not None and not isinstance(result, self.output_type):
            logger.warning(f"Result {result} is not of expected output type {self.output_type}")
            
        return result

class BaseSchemaAdapter(ISchemaAdapter):
    """Base class for schema adapters."""
    
    def __init__(self):
        """Initialize adapter."""
        self.errors: List[str] = []
        
    def get_validation_errors(self) -> List[str]:
        """Get validation error messages."""
        return self.errors.copy()
        
    def _add_error(self, field_name: str, message: str) -> None:
        """Add validation error."""
        self.errors.append(f"{field_name}: {message}")

class StringAdapter(BaseSchemaAdapter):
    """Adapter for string fields."""
    
    def __init__(self, min_length: Optional[int] = None,
                 max_length: Optional[int] = None,
                 pattern: Optional[str] = None,
                 strip: bool = True):
        """Initialize string adapter."""
        super().__init__()
        self.min_length = min_length
        self.max_length = max_length
        self.pattern = pattern
        self.strip = strip
        self._pattern_regex = re.compile(pattern) if pattern else None
        
    def validate(self, value: Any, field_name: str) -> bool:
        """Validate string value."""
        self.errors.clear()
        
        if value is None:
            return True
            
        if not isinstance(value, str):
            self._add_error(field_name, f"Expected string, got {type(value)}")
            return False
            
        str_value = str(value).strip() if self.strip else str(value)
        
        if self.min_length is not None and len(str_value) < self.min_length:
            self._add_error(
                field_name,
                f"String length {len(str_value)} is less than minimum {self.min_length}"
            )
            return False
            
        if self.max_length is not None and len(str_value) > self.max_length:
            self._add_error(
                field_name,
                f"String length {len(str_value)} exceeds maximum {self.max_length}"
            )
            return False
            
        if self._pattern_regex and not self._pattern_regex.match(str_value):
            self._add_error(
                field_name,
                f"String does not match pattern: {self.pattern}"
            )
            return False
            
        return True
        
    def transform(self, value: Any, field_name: str) -> Any:
        """Transform to string format."""
        if value is None:
            return None
            
        str_value = str(value)
        return str_value.strip() if self.strip else str_value

class NumericAdapter(BaseSchemaAdapter):
    """Adapter for numeric fields."""
    
    def __init__(self, min_value: Optional[float] = None,
                 max_value: Optional[float] = None,
                 precision: Optional[int] = None,
                 decimal: bool = False):
        """Initialize numeric adapter."""
        super().__init__()
        self.min_value = min_value
        self.max_value = max_value
        self.precision = precision
        self.decimal = decimal
        
    def validate(self, value: Any, field_name: str) -> bool:
        """Validate numeric value."""
        self.errors.clear()
        
        if value is None:
            return True
            
        try:
            if self.decimal:
                num_value = Decimal(str(value))
            else:
                num_value = float(value)
                
            if self.min_value is not None and num_value < self.min_value:
                self._add_error(
                    field_name,
                    f"Value {num_value} is less than minimum {self.min_value}"
                )
                return False
                
            if self.max_value is not None and num_value > self.max_value:
                self._add_error(
                    field_name,
                    f"Value {num_value} exceeds maximum {self.max_value}"
                )
                return False
                
            if self.precision is not None and self.decimal:
                str_value = str(num_value)
                if '.' in str_value:
                    decimal_places = len(str_value.split('.')[1])
                    if decimal_places > self.precision:
                        self._add_error(
                            field_name,
                            f"Value has {decimal_places} decimal places, "
                            f"maximum is {self.precision}"
                        )
                        return False
                        
            return True
            
        except (ValueError, InvalidOperation):
            self._add_error(field_name, "Invalid numeric value")
            return False
            
    def transform(self, value: Any, field_name: str) -> Any:
        """Transform to numeric format."""
        if value is None:
            return None
            
        try:
            if self.decimal:
                num_value = Decimal(str(value))
                if self.precision is not None:
                    # Round to specified precision
                    num_value = round(num_value, self.precision)
                return num_value
            else:
                return float(value)
        except (ValueError, InvalidOperation):
            return None

class DateAdapter(BaseSchemaAdapter):
    """Adapter for date/datetime fields."""
    
    def __init__(self, formats: List[str], min_date: Optional[date] = None,
                 max_date: Optional[date] = None,
                 output_format: Optional[str] = None):
        """Initialize date adapter."""
        super().__init__()
        self.formats = formats
        self.min_date = min_date
        self.max_date = max_date
        self.output_format = output_format
        
    def validate(self, value: Any, field_name: str) -> bool:
        """Validate date value."""
        self.errors.clear()
        
        if value is None:
            return True
            
        if isinstance(value, (date, datetime)):
            date_value = value.date() if isinstance(value, datetime) else value
        else:
            try:
                date_value = self._parse_date(str(value))
                if not date_value:
                    self._add_error(
                        field_name,
                        f"Could not parse date from {value} using formats: {self.formats}"
                    )
                    return False
            except ValueError as e:
                self._add_error(field_name, str(e))
                return False
                
        if self.min_date and date_value < self.min_date:
            self._add_error(
                field_name,
                f"Date {date_value} is before minimum {self.min_date}"
            )
            return False
            
        if self.max_date and date_value > self.max_date:
            self._add_error(
                field_name,
                f"Date {date_value} is after maximum {self.max_date}"
            )
            return False
            
        return True
        
    def transform(self, value: Any, field_name: str) -> Any:
        """Transform to date format."""
        if value is None:
            return None
            
        if isinstance(value, (date, datetime)):
            date_value = value.date() if isinstance(value, datetime) else value
        else:
            date_value = self._parse_date(str(value))
            if not date_value:
                return None
                
        if self.output_format:
            return date_value.strftime(self.output_format)
        return date_value
        
    def _parse_date(self, value: str) -> Optional[date]:
        """Parse date string using configured formats."""
        for fmt in self.formats:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        return None

class BooleanAdapter(BaseSchemaAdapter):
    """Adapter for boolean fields."""
    
    TRUE_VALUES = {'true', 'yes', '1', 'y', 't'}
    FALSE_VALUES = {'false', 'no', '0', 'n', 'f'}
    
    def validate(self, value: Any, field_name: str) -> bool:
        """Validate boolean value."""
        self.errors.clear()
        
        if value is None:
            return True
            
        if isinstance(value, bool):
            return True
            
        str_value = str(value).lower()
        if str_value not in self.TRUE_VALUES and str_value not in self.FALSE_VALUES:
            self._add_error(
                field_name,
                f"Invalid boolean value: {value}"
            )
            return False
            
        return True
        
    def transform(self, value: Any, field_name: str) -> Any:
        """Transform to boolean."""
        if value is None:
            return None
            
        if isinstance(value, bool):
            return value
            
        str_value = str(value).lower()
        if str_value in self.TRUE_VALUES:
            return True
        if str_value in self.FALSE_VALUES:
            return False
        return None

class EnumAdapter(BaseSchemaAdapter):
    """Adapter for enumerated value fields."""
    
    def __init__(self, valid_values: List[str],
                 case_sensitive: bool = False):
        """Initialize enum adapter."""
        super().__init__()
        self.valid_values = valid_values
        self.case_sensitive = case_sensitive
        
        if not case_sensitive:
            self.valid_values = [v.lower() for v in valid_values]
            
    def validate(self, value: Any, field_name: str) -> bool:
        """Validate enum value."""
        self.errors.clear()
        
        if value is None:
            return True
            
        check_value = str(value)
        if not self.case_sensitive:
            check_value = check_value.lower()
            
        if check_value not in self.valid_values:
            self._add_error(
                field_name,
                f"Value {value} not in valid values: {self.valid_values}"
            )
            return False
            
        return True
        
    def transform(self, value: Any, field_name: str) -> Any:
        """Transform enum value."""
        if value is None:
            return None
            
        check_value = str(value)
        if not self.case_sensitive:
            check_value = check_value.lower()
            
        if check_value in self.valid_values:
            return value
        return None

class ListAdapter(BaseSchemaAdapter):
    """Adapter for list fields."""
    
    def __init__(self, item_adapter: ISchemaAdapter,
                 min_items: Optional[int] = None,
                 max_items: Optional[int] = None):
        """Initialize list adapter."""
        super().__init__()
        self.item_adapter = item_adapter
        self.min_items = min_items
        self.max_items = max_items
        
    def validate(self, value: Any, field_name: str) -> bool:
        """Validate list value."""
        self.errors.clear()
        
        if value is None:
            return True
            
        if not isinstance(value, (list, tuple)):
            self._add_error(
                field_name,
                f"Expected list/tuple, got {type(value)}"
            )
            return False
            
        if self.min_items is not None and len(value) < self.min_items:
            self._add_error(
                field_name,
                f"List has {len(value)} items, minimum is {self.min_items}"
            )
            return False
            
        if self.max_items is not None and len(value) > self.max_items:
            self._add_error(
                field_name,
                f"List has {len(value)} items, maximum is {self.max_items}"
            )
            return False
            
        # Validate each item
        for i, item in enumerate(value):
            if not self.item_adapter.validate(item, f"{field_name}[{i}]"):
                self.errors.extend(self.item_adapter.get_validation_errors())
                return False
                
        return True
        
    def transform(self, value: Any, field_name: str) -> Any:
        """Transform list value."""
        if value is None:
            return None
            
        if not isinstance(value, (list, tuple)):
            return None
            
        return [
            self.item_adapter.transform(item, f"{field_name}[{i}]")
            for i, item in enumerate(value)
        ]

class DictAdapter(BaseSchemaAdapter):
    """Adapter for dictionary fields."""
    
    def __init__(self, field_adapters: Dict[str, ISchemaAdapter],
                 required_fields: Optional[List[str]] = None,
                 additional_fields: bool = True):
        """Initialize dictionary adapter."""
        super().__init__()
        self.field_adapters = field_adapters
        self.required_fields = required_fields or []
        self.additional_fields = additional_fields
        
    def validate(self, value: Any, field_name: str) -> bool:
        """Validate dictionary value."""
        self.errors.clear()
        
        if value is None:
            return True
            
        if not isinstance(value, dict):
            self._add_error(
                field_name,
                f"Expected dictionary, got {type(value)}"
            )
            return False
            
        # Check required fields
        missing_fields = [
            f for f in self.required_fields
            if f not in value
        ]
        if missing_fields:
            self._add_error(
                field_name,
                f"Missing required fields: {missing_fields}"
            )
            return False
            
        # Check additional fields
        if not self.additional_fields:
            extra_fields = [
                f for f in value.keys()
                if f not in self.field_adapters
            ]
            if extra_fields:
                self._add_error(
                    field_name,
                    f"Unknown fields not allowed: {extra_fields}"
                )
                return False
                
        # Validate each field
        for f_name, adapter in self.field_adapters.items():
            if f_name in value:
                if not adapter.validate(value[f_name], f"{field_name}.{f_name}"):
                    self.errors.extend(adapter.get_validation_errors())
                    return False
                    
        return True
        
    def transform(self, value: Any, field_name: str) -> Any:
        """Transform dictionary value."""
        if value is None:
            return None
            
        if not isinstance(value, dict):
            return None
            
        result = {}
        for f_name, adapter in self.field_adapters.items():
            if f_name in value:
                transformed = adapter.transform(
                    value[f_name],
                    f"{field_name}.{f_name}"
                )
                if transformed is not None:
                    result[f_name] = transformed
                    
        # Copy additional fields
        if self.additional_fields:
            for f_name, f_value in value.items():
                if f_name not in self.field_adapters:
                    result[f_name] = f_value
                    
        return result

class CompositeFieldAdapter(BaseSchemaAdapter):
    """Adapter that chains multiple transformations together."""
    
    def __init__(self, transformations: List[AdapterTransform]):
        """Initialize composite adapter.
        
        Args:
            transformations: List of transformations to apply in sequence
        """
        super().__init__()
        self.transformations = transformations
        
    def validate(self, value: Any, field_name: str) -> bool:
        """Validate by running through transformations.
        
        Args:
            value: Value to validate
            field_name: Field name for error messages
            
        Returns:
            True if all transformations succeed, False otherwise
        """
        self.errors.clear()
        try:
            result = value
            for transform in self.transformations:
                result = transform(result)
                if result is None:
                    self._add_error(field_name, f"Transformation {transform.__class__.__name__} failed")
                    return False
            return True
        except Exception as e:
            self._add_error(field_name, str(e))
            return False
            
    def transform(self, value: Any, field_name: str) -> Any:
        """Apply transformations in sequence.
        
        Args:
            value: Value to transform
            field_name: Field name (used for error messages)
            
        Returns:
            Result of applying all transformations in sequence
        """
        result = value
        for transform in self.transformations:
            result = transform(result)
            if result is None:
                return None
        return result

class SchemaAdapterFactory:
    """Factory class for creating schema adapters."""
    def create_adapter(self, adapter_type: str, **kwargs) -> BaseSchemaAdapter:
        """Create and return an adapter based on the adapter type."""
        if adapter_type == 'string':
            return StringAdapter(**kwargs)
        elif adapter_type == 'numeric':
            return NumericAdapter(**kwargs)
        elif adapter_type == 'date':
            return DateAdapter(**kwargs)
        elif adapter_type == 'boolean':
            return BooleanAdapter(**kwargs)
        elif adapter_type == 'enum':
            return EnumAdapter(**kwargs)
        elif adapter_type == 'list':
            return ListAdapter(**kwargs)
        elif adapter_type == 'dict':
            return DictAdapter(**kwargs)
        else:
            raise ValueError(f"Unknown adapter type: {adapter_type}")

class FieldAdapter:
    """Base class for field-specific adapters."""
    
    def __init__(self, field_name: str, required: bool = False, default: Any = None):
        """Initialize field adapter.
        
        Args:
            field_name: Name of the field
            required: Whether the field is required
            default: Default value if field is missing
        """
        self.field_name = field_name
        self.required = required
        self.default = default
        
    def validate(self, data: Dict[str, Any]) -> List[str]:
        """Validate field in data dictionary.
        
        Args:
            data: Dictionary containing field data
            
        Returns:
            List of validation error messages
        """
        errors = []
        
        # Check if required field is present
        if self.required and self.field_name not in data:
            errors.append(f"Required field '{self.field_name}' is missing")
            
        return errors
        
    def transform(self, data: Dict[str, Any]) -> Any:
        """Transform field value.
        
        Args:
            data: Dictionary containing field data
            
        Returns:
            Transformed value
        """
        if self.field_name not in data and self.default is not None:
            return self.default
            
        return data.get(self.field_name)

class PydanticAdapter(FieldAdapter):
    """Adapter for Pydantic model fields."""
    
    def __init__(self, field_name: str, model_class: Type, required: bool = False):
        """Initialize Pydantic adapter.
        
        Args:
            field_name: Name of the field
            model_class: Pydantic model class
            required: Whether the field is required
        """
        super().__init__(field_name, required)
        self.model_class = model_class
        
    def validate(self, data: Dict[str, Any]) -> List[str]:
        """Validate field using Pydantic model.
        
        Args:
            data: Dictionary containing field data
            
        Returns:
            List of validation error messages
        """
        errors = super().validate(data)
        
        if errors or self.field_name not in data:
            return errors
            
        try:
            self.model_class.parse_obj(data[self.field_name])
        except Exception as e:
            errors.append(f"Field '{self.field_name}' validation error: {str(e)}")
            
        return errors
        
    def transform(self, data: Dict[str, Any]) -> Any:
        """Transform field value using Pydantic model.
        
        Args:
            data: Dictionary containing field data
            
        Returns:
            Transformed value or None if invalid
        """
        if self.field_name not in data:
            return None
            
        try:
            model = self.model_class.parse_obj(data[self.field_name])
            return model.dict()
        except Exception:
            return None

class MarshmallowAdapter(FieldAdapter):
    """Adapter for Marshmallow schema fields."""
    
    def __init__(self, field_name: str, schema_class: Type, required: bool = False):
        """Initialize Marshmallow adapter.
        
        Args:
            field_name: Name of the field
            schema_class: Marshmallow schema class
            required: Whether the field is required
        """
        super().__init__(field_name, required)
        self.schema_class = schema_class
        self.schema = schema_class()
        
    def validate(self, data: Dict[str, Any]) -> List[str]:
        """Validate field using Marshmallow schema.
        
        Args:
            data: Dictionary containing field data
            
        Returns:
            List of validation error messages
        """
        errors = super().validate(data)
        
        if errors or self.field_name not in data:
            return errors
            
        validation_errors = self.schema.validate(data[self.field_name])
        if validation_errors:
            for field, field_errors in validation_errors.items():
                if isinstance(field_errors, list):
                    for error in field_errors:
                        errors.append(f"Field '{self.field_name}.{field}': {error}")
                else:
                    errors.append(f"Field '{self.field_name}.{field}': {field_errors}")
                    
        return errors
        
    def transform(self, data: Dict[str, Any]) -> Any:
        """Transform field value using Marshmallow schema.
        
        Args:
            data: Dictionary containing field data
            
        Returns:
            Transformed value or None if invalid
        """
        if self.field_name not in data:
            return None
            
        try:
            return self.schema.dump(data[self.field_name])
        except Exception:
            return None

class DateFieldAdapter(FieldAdapter):
    """Adapter for date fields."""
    
    def __init__(self, field_name: str, formats: List[str], 
                 required: bool = False, min_date: Optional[date] = None,
                 max_date: Optional[date] = None):
        """Initialize date field adapter.
        
        Args:
            field_name: Name of the field
            formats: List of date format strings
            required: Whether the field is required
            min_date: Minimum allowed date
            max_date: Maximum allowed date
        """
        super().__init__(field_name, required)
        self.formats = formats
        self.min_date = min_date
        self.max_date = max_date
        
    def validate(self, data: Dict[str, Any]) -> List[str]:
        """Validate date field.
        
        Args:
            data: Dictionary containing field data
            
        Returns:
            List of validation error messages
        """
        errors = super().validate(data)
        
        if errors or self.field_name not in data:
            return errors
            
        value = data[self.field_name]
        if value is None:
            return errors
            
        date_value = None
        
        if isinstance(value, (date, datetime)):
            date_value = value.date() if isinstance(value, datetime) else value
        else:
            # Try to parse using provided formats
            for fmt in self.formats:
                try:
                    date_value = datetime.strptime(str(value), fmt).date()
                    break
                except ValueError:
                    continue
                    
            if date_value is None:
                errors.append(
                    f"Field '{self.field_name}': Could not parse date '{value}'"
                )
                return errors
                
        if self.min_date and date_value < self.min_date:
            errors.append(
                f"Field '{self.field_name}': Date {date_value} is before minimum {self.min_date}"
            )
            
        if self.max_date and date_value > self.max_date:
            errors.append(
                f"Field '{self.field_name}': Date {date_value} is after maximum {self.max_date}"
            )
            
        return errors
        
    def transform(self, data: Dict[str, Any]) -> Any:
        """Transform date field value.
        
        Args:
            data: Dictionary containing field data
            
        Returns:
            Date object or None if invalid
        """
        if self.field_name not in data:
            return None
            
        value = data[self.field_name]
        if value is None:
            return None
            
        if isinstance(value, (date, datetime)):
            return value.date() if isinstance(value, datetime) else value
            
        # Try to parse using provided formats
        for fmt in self.formats:
            try:
                return datetime.strptime(str(value), fmt).date()
            except ValueError:
                continue
                
        return None

class DecimalFieldAdapter(FieldAdapter):
    """Adapter for decimal fields."""
    
    def __init__(self, field_name: str, required: bool = False,
                 min_value: Optional[Decimal] = None,
                 max_value: Optional[Decimal] = None,
                 precision: Optional[int] = None):
        """Initialize decimal field adapter.
        
        Args:
            field_name: Name of the field
            required: Whether the field is required
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            precision: Decimal precision
        """
        super().__init__(field_name, required)
        self.min_value = min_value
        self.max_value = max_value
        self.precision = precision
        
    def validate(self, data: Dict[str, Any]) -> List[str]:
        """Validate decimal field.
        
        Args:
            data: Dictionary containing field data
            
        Returns:
            List of validation error messages
        """
        errors = super().validate(data)
        
        if errors or self.field_name not in data:
            return errors
            
        value = data[self.field_name]
        if value is None:
            return errors
            
        try:
            decimal_value = Decimal(str(value))
            
            if self.min_value is not None and decimal_value < self.min_value:
                errors.append(
                    f"Field '{self.field_name}': Value {decimal_value} is less than minimum {self.min_value}"
                )
                
            if self.max_value is not None and decimal_value > self.max_value:
                errors.append(
                    f"Field '{self.field_name}': Value {decimal_value} exceeds maximum {self.max_value}"
                )
                
            if self.precision is not None:
                # Check precision
                str_value = str(decimal_value)
                if '.' in str_value:
                    decimal_places = len(str_value.split('.')[1])
                    if decimal_places > self.precision:
                        errors.append(
                            f"Field '{self.field_name}': Value has {decimal_places} decimal places, "
                            f"maximum is {self.precision}"
                        )
                
        except (ValueError, InvalidOperation):
            errors.append(f"Field '{self.field_name}': Invalid decimal value '{value}'")
            
        return errors
        
    def transform(self, data: Dict[str, Any]) -> Any:
        """Transform decimal field value.
        
        Args:
            data: Dictionary containing field data
            
        Returns:
            Decimal object or None if invalid
        """
        if self.field_name not in data:
            return None
            
        value = data[self.field_name]
        if value is None:
            return None
            
        try:
            decimal_value = Decimal(str(value))
            
            if self.precision is not None:
                # Round to specified precision
                decimal_value = round(decimal_value, self.precision)
                
            return decimal_value
        except (ValueError, InvalidOperation):
            return None

__all__ = [
    'SchemaAdapterFactory',
    'FieldAdapter',
    'PydanticAdapter',
    'MarshmallowAdapter',
    'DateFieldAdapter',
    'DecimalFieldAdapter',
    'BaseSchemaAdapter',
    'StringAdapter',
    'NumericAdapter',
    'DateAdapter',
    'BooleanAdapter',
    'EnumAdapter',
    'ListAdapter',
    'DictAdapter',
    'AdapterTransform',  # Add this to __all__
    'CompositeFieldAdapter'  # Add this to __all__
]