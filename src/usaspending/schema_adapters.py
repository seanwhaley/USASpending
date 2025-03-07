"""Schema adapter implementations for data type conversion."""
from typing import Dict, Any, List, Optional, Union, Type, TypeVar, Generic, Callable
from decimal import Decimal, InvalidOperation
from datetime import datetime, date
import re
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from . import get_logger
from .interfaces import ISchemaAdapter

logger = get_logger(__name__)

@dataclass
class AdapterTransform:
    """Configuration for field transformations."""
    type: str
    config: Dict[str, Any] = field(default_factory=dict)
    
    def __call__(self, value: Any) -> Any:
        """Apply the transformation to a value."""
        if value is None:
            return None
            
        transforms = {
            'uppercase': lambda x: x.upper() if isinstance(x, str) else x,
            'lowercase': lambda x: x.lower() if isinstance(x, str) else x,
            'trim': lambda x: x.strip() if isinstance(x, str) else x,
            'strip_characters': lambda x: ''.join(c for c in x if c not in self.config),
            'pad_left': lambda x: str(x).zfill(self.config.get('length', 5)),
            'truncate': lambda x: str(x)[:self.config.get('length', 3)],
            'normalize_whitespace': lambda x: ' '.join(str(x).split()),
            'split': lambda x: str(x).split(self.config),
            'get_index': lambda x: x[self.config] if isinstance(x, (list, tuple)) else None,
            'to_int': lambda x: int(x) if str(x).isdigit() else None,
            'to_isoformat': lambda x: x.isoformat() if hasattr(x, 'isoformat') else str(x)
        }
        
        transform_func = transforms.get(self.type)
        if not transform_func:
            raise ValueError(f"Unknown transformation type: {self.type}")
            
        try:
            return transform_func(value)
        except (ValueError, TypeError, IndexError) as e:
            logger.warning(f"Transform {self.type} failed for value {value}: {str(e)}")
            return None

class AdapterError(Exception):
    """Base class for adapter errors."""
    pass

class BaseSchemaAdapter(ISchemaAdapter):
    """Base class for schema adapters."""
    
    def __init__(self):
        """Initialize adapter."""
        self.errors: List[str] = []
        
    def validate(self, value: Any, rules: Dict[str, Any],
                validation_context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate a value against schema rules."""
        return self.validate_field(value)
        
    def transform(self, value: Any) -> Any:
        """Transform a value according to schema rules."""
        return self.transform_field(value)
        
    def get_errors(self) -> List[str]:
        """Get validation/transformation errors."""
        return self.errors.copy()

    def validate_field(self, value: Any, field_name: str = "") -> bool:
        """Validate field value."""
        raise NotImplementedError
        
    def transform_field(self, value: Any, field_name: str = "") -> Any:
        """Transform field value."""
        raise NotImplementedError
        
    def clear_cache(self) -> None:
        """Clear any cached data."""
        self.errors.clear()

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
        
    def validate_field(self, value: Any, field_name: str = "") -> bool:
        """Validate string value."""
        self.errors.clear()
        
        if value is None:
            return True
            
        if not isinstance(value, str):
            self.errors.append(f"Expected string, got {type(value)}")
            return False
            
        str_value = str(value).strip() if self.strip else str(value)
        
        if self.min_length is not None and len(str_value) < self.min_length:
            self.errors.append(
                f"String length {len(str_value)} is less than minimum {self.min_length}"
            )
            return False
            
        if self.max_length is not None and len(str_value) > self.max_length:
            self.errors.append(
                f"String length {len(str_value)} exceeds maximum {self.max_length}"
            )
            return False
            
        if self._pattern_regex and not self._pattern_regex.match(str_value):
            self.errors.append(
                f"String does not match pattern: {self.pattern}"
            )
            return False
            
        return True
        
    def transform_field(self, value: Any, field_name: str = "") -> Any:
        """Transform to string format."""
        if value is None:
            return None
            
        str_value = str(value)
        return str_value.strip() if self.strip else str_value
        
    def get_validation_errors(self) -> List[str]:
        """Get validation error messages."""
        return self.errors.copy()

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
        
    def validate_field(self, value: Any, field_name: str = "") -> bool:
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
                self.errors.append(f"Value {num_value} is less than minimum {self.min_value}")
                return False
                
            if self.max_value is not None and num_value > self.max_value:
                self.errors.append(f"Value {num_value} exceeds maximum {self.max_value}")
                return False
                
            if self.precision is not None and self.decimal:
                str_value = str(num_value)
                if '.' in str_value:
                    decimal_places = len(str_value.split('.')[1])
                    if decimal_places > self.precision:
                        self.errors.append(f"Decimal places {decimal_places} exceeds precision {self.precision}")
                        return False
                        
            return True
            
        except (ValueError, InvalidOperation):
            self.errors.append(f"Invalid numeric value: {value}")
            return False
            
    def transform_field(self, value: Any, field_name: str = "") -> Any:
        """Transform to numeric format."""
        if value is None:
            return None
            
        try:
            if self.decimal:
                num_value = Decimal(str(value))
                if self.precision is not None:
                    return round(num_value, self.precision)
                return num_value
            else:
                return float(value)
        except (ValueError, InvalidOperation):
            return None
            
    def get_validation_errors(self) -> List[str]:
        """Get validation error messages."""
        return self.errors.copy()

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
        
    def validate_field(self, value: Any, field_name: str = "") -> bool:
        """Validate date value."""
        self.errors.clear()
        
        if value is None:
            return True
            
        try:
            # Handle datetime objects
            if isinstance(value, datetime):
                date_value = value.date()
            elif isinstance(value, date):
                date_value = value
            else:
                date_value = self._parse_date(str(value))
                
            if not date_value:
                self.errors.append(f"Could not parse date from {value} using formats: {self.formats}")
                return False
                
            if self.min_date and date_value < self.min_date:
                self.errors.append(
                    f"Date {date_value} is before minimum {self.min_date}"
                )
                return False
                
            if self.max_date and date_value > self.max_date:
                self.errors.append(
                    f"Date {date_value} is after maximum {self.max_date}"
                )
                return False
                
            return True
            
        except ValueError as e:
            self.errors.append(str(e))
            return False
        
    def transform_field(self, value: Any, field_name: str = "") -> Any:
        """Transform to date format."""
        if value is None:
            return None
            
        if isinstance(value, datetime):
            date_value = value.date()
        elif isinstance(value, date):
            date_value = value
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
    
    def validate_field(self, value: Any, field_name: str = "") -> bool:
        """Validate boolean value."""
        self.errors.clear()
        
        if value is None:
            return True
            
        if isinstance(value, bool):
            return True
            
        str_value = str(value).lower()
        if str_value not in self.TRUE_VALUES and str_value not in self.FALSE_VALUES:
            self.errors.append(
                f"Invalid boolean value: {value}"
            )
            return False
            
        return True
        
    def transform_field(self, value: Any, field_name: str = "") -> Any:
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
    """Adapter for enum fields."""
    
    def __init__(self, field_name: str, enum_class: Type,
                 required: bool = False, case_sensitive: bool = False):
        """Initialize enum adapter."""
        super().__init__()
        self.field_name = field_name
        self.enum_class = enum_class
        self.required = required
        self.case_sensitive = case_sensitive
        
        # Build lookup sets
        self._values = {e.value for e in enum_class}
        if not case_sensitive:
            self._values = {str(v).lower() for v in self._values}
            
    def validate_field(self, value: Any, field_name: str = "") -> bool:
        """Validate enum value."""
        self.errors.clear()
        if value is None:
            if self.required:
                self.errors.append(f"Field '{field_name or self.field_name}' is required")
                return False
            return True
            
        check_value = str(value)
        if not self.case_sensitive:
            check_value = check_value.lower()
            
        if check_value not in self._values:
            self.errors.append(
                f"Value '{value}' not in valid values: {sorted(self._values)}"
            )
            return False
            
        return True
        
    def transform_field(self, value: Any, field_name: str = "") -> Any:
        """Transform to enum value."""
        if value is None:
            return None
            
        check_value = str(value)
        if not self.case_sensitive:
            check_value = check_value.lower()
            
        if check_value in self._values:
            # Find matching enum member
            for member in self.enum_class:
                member_value = str(member.value)
                if not self.case_sensitive:
                    member_value = member_value.lower()
                if member_value == check_value:
                    return member
                    
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
        
    def validate_field(self, value: Any, field_name: str = "") -> bool:
        """Validate list value."""
        self.errors.clear()
        
        if value is None:
            return True
            
        if not isinstance(value, (list, tuple)):
            self.errors.append(
                f"Expected list/tuple, got {type(value)}"
            )
            return False
            
        if self.min_items is not None and len(value) < self.min_items:
            self.errors.append(
                f"List has {len(value)} items, minimum is {self.min_items}"
            )
            return False
            
        if self.max_items is not None and len(value) > self.max_items:
            self.errors.append(
                f"List has {len(value)} items, maximum is {self.max_items}"
            )
            return False
            
        # Validate each item
        valid = True
        for i, item in enumerate(value):
            if not self.item_adapter.validate_field(item, f"{field_name}[{i}]"):
                valid = False
                self.errors.extend(self.item_adapter.get_errors())
                
        return valid
        
    def transform_field(self, value: Any, field_name: str = "") -> Any:
        """Transform list value."""
        if value is None:
            return None
            
        if not isinstance(value, (list, tuple)):
            return None
            
        return [
            self.item_adapter.transform_field(item, f"{field_name}[{i}]")
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
        
    def validate_field(self, value: Any, field_name: str = "") -> bool:
        """Validate dictionary value."""
        self.errors.clear()
        
        if value is None:
            return True
            
        if not isinstance(value, dict):
            self.errors.append(
                f"Expected dictionary, got {type(value)}"
            )
            return False
            
        # Check required fields
        missing_fields = [
            f for f in self.required_fields
            if f not in value
        ]
        if missing_fields:
            self.errors.append(
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
                self.errors.append(
                    f"Unknown fields not allowed: {extra_fields}"
                )
                return False
                
        # Validate each field
        valid = True
        for f_name, adapter in self.field_adapters.items():
            if f_name in value:
                if not adapter.validate_field(value[f_name], f"{field_name}.{f_name}"):
                    valid = False
                    self.errors.extend(adapter.get_errors())
                    
        return valid
        
    def transform_field(self, value: Any, field_name: str = "") -> Any:
        """Transform dictionary value."""
        if value is None:
            return None
            
        if not isinstance(value, dict):
            return None
            
        result = {}
        for f_name, adapter in self.field_adapters.items():
            if f_name in value:
                transformed = adapter.transform_field(
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
    
    def __init__(self, field_name: str, transformations: List[Any],
                required: bool = False):
        """Initialize composite adapter."""
        super().__init__()
        self.field_name = field_name
        self.transformations = transformations
        self.required = required
        
    def validate_field(self, value: Any, field_name: str = "") -> bool:
        """Validate by running through transformations."""
        self.errors.clear()
        
        if value is None:
            if self.required:
                self.errors.append(f"Field '{field_name or self.field_name}' is required")
                return False
            return True
            
        # First validate using any adapter transformations
        for transform in self.transformations:
            # If the transform is a transform_field method from an adapter
            if hasattr(transform, '__self__') and isinstance(transform.__self__, BaseSchemaAdapter):
                adapter = transform.__self__
                if not adapter.validate_field(value, field_name):
                    self.errors.extend(adapter.get_errors())
                    return False
            # If the transform is an adapter instance
            elif isinstance(transform, BaseSchemaAdapter):
                if not transform.validate_field(value, field_name):
                    self.errors.extend(transform.get_errors())
                    return False
            
        # Then try the transformation chain
        try:
            result = value
            for transform in self.transformations:
                if hasattr(transform, 'transform_field'):
                    result = transform.transform_field(result)
                else:
                    result = transform(result)
                if result is None:
                    self.errors.append(
                        f"Transformation {getattr(transform, '__name__', str(transform))} failed for value {value}"
                    )
                    return False
                    
            return True
            
        except Exception as e:
            self.errors.append(str(e))
            return False
            
    def transform_field(self, value: Any, field_name: str = "") -> Any:
        """Apply transformations in sequence."""
        if value is None:
            return None
            
        try:
            result = value
            for transform in self.transformations:
                if hasattr(transform, 'transform_field'):
                    result = transform.transform_field(result)
                else:
                    result = transform(result)
                if result is None:
                    return None
            return result
        except Exception:
            return None

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
            self.model_class.model_validate(data[self.field_name])
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
            model = self.model_class.model_validate(data[self.field_name])
            return model.model_dump()
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

class DateFieldAdapter(BaseSchemaAdapter):
    """Adapter for date fields."""
    
    def __init__(self, field_name: str, formats: List[str], 
                 required: bool = False, min_date: Optional[date] = None,
                 max_date: Optional[date] = None):
        """Initialize date field adapter."""
        super().__init__()
        self.field_name = field_name
        self.formats = formats
        self.required = required
        self.min_date = min_date
        self.max_date = max_date
        
    def validate_field(self, value: Any, field_name: str = "") -> bool:
        """Validate date field."""
        self.errors.clear()
        if value is None:
            if self.required:
                self.errors.append(f"Field '{field_name or self.field_name}' is required")
                return False
            return True
        
        try:
            date_val = self._parse_date(str(value))
            if not date_val:
                self.errors.append(
                    f"Could not parse date '{value}' using formats: {self.formats}"
                )
                return False
                
            if self.min_date and date_val < self.min_date:
                self.errors.append(
                    f"Date {date_val} is before minimum {self.min_date}"
                )
                return False
                
            if self.max_date and date_val > self.max_date:
                self.errors.append(
                    f"Date {date_val} is after maximum {self.max_date}"
                )
                return False
                
            return True
            
        except (ValueError, TypeError) as e:
            self.errors.append(str(e))
            return False
            
    def transform_field(self, value: Any, field_name: str = "") -> Any:
        """Transform to date format."""
        if value is None:
            return None
            
        try:
            return self._parse_date(str(value))
        except (ValueError, TypeError):
            return None
            
    def _parse_date(self, value: str) -> Optional[date]:
        """Parse date string using configured formats."""
        for fmt in self.formats:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        return None

class DecimalFieldAdapter(BaseSchemaAdapter):
    """Adapter for decimal fields."""
    
    def __init__(self, field_name: str, required: bool = False,
                 min_value: Optional[Decimal] = None,
                 max_value: Optional[Decimal] = None,
                 precision: Optional[int] = None):
        """Initialize decimal field adapter."""
        super().__init__()
        self.field_name = field_name
        self.required = required
        self.min_value = min_value
        self.max_value = max_value
        self.precision = precision
        
    def validate_field(self, value: Any, field_name: str = "") -> bool:
        """Validate decimal field."""
        self.errors.clear()
        if value is None:
            if self.required:
                self.errors.append(f"Field '{field_name or self.field_name}' is required")
                return False
            return True
            
        try:
            decimal_value = Decimal(str(value))
            
            if self.min_value is not None and decimal_value < self.min_value:
                self.errors.append(
                    f"Value {decimal_value} is less than minimum {self.min_value}"
                )
                return False
                
            if self.max_value is not None and decimal_value > self.max_value:
                self.errors.append(
                    f"Value {decimal_value} exceeds maximum {self.max_value}"
                )
                return False
                
            if self.precision is not None:
                str_value = str(decimal_value)
                if '.' in str_value:
                    decimal_places = len(str_value.split('.')[1])
                    if decimal_places > self.precision:
                        self.errors.append(
                            f"Value has {decimal_places} decimal places, "
                            f"maximum is {self.precision}"
                        )
                        return False
                        
            return True
            
        except (ValueError, InvalidOperation) as e:
            self.errors.append(str(e))
            return False
            
    def transform_field(self, value: Any, field_name: str = "") -> Any:
        """Transform to decimal format."""
        if value is None:
            return None
            
        try:
            decimal_value = Decimal(str(value))
            if self.precision is not None:
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
    'CompositeFieldAdapter'
]