"""Core type adaptation functionality."""
from abc import ABC, abstractmethod
from datetime import datetime, date
import re
from typing import Dict, Any, Type, Optional, List, Set, Callable, Union, Generic, TypeVar, cast, ClassVar
from decimal import Decimal, DecimalException

from .types import AdapterResult, FieldType
from .exceptions import AdapterError, TransformationError

T = TypeVar('T')

class BaseAdapter(ABC, Generic[T]):
    """Base type adapter."""

    def __init__(self) -> None:
        """Initialize adapter with empty error list."""
        self.errors: List[str] = []

    @abstractmethod
    def transform_field(self, value: Any) -> Optional[T]:
        """Transform a value to the target type."""
        pass

    @abstractmethod
    def validate_field(self, value: Any) -> bool:
        """Validate if a value can be transformed."""
        pass

    def clear_cache(self) -> None:
        """Clear validation errors and any cached data."""
        self.errors = []

    def add_error(self, message: str) -> None:
        """Add validation error message."""
        self.errors.append(message)


class StringAdapter(BaseAdapter[str]):
    """String type adapter."""

    def __init__(self, min_length: Optional[int] = None, max_length: Optional[int] = None, 
                 pattern: Optional[str] = None, strip: bool = True, **kwargs: Any) -> None:
        super().__init__()
        self.min_length = min_length
        self.max_length = max_length
        self.pattern = re.compile(pattern) if pattern else None
        self.strip = strip

    def transform_field(self, value: Any) -> Optional[str]:
        """Convert value to string."""
        if value is None:
            return None
        result = str(value)
        if self.strip:
            result = result.strip()
        return result

    def validate_field(self, value: Any) -> bool:
        """Validate string value."""
        self.clear_cache()
        if value is None:
            return True

        string_value = str(value)
        
        if self.min_length is not None and len(string_value) < self.min_length:
            self.add_error(f"String length {len(string_value)} is below minimum length {self.min_length}")
            return False
            
        if self.max_length is not None and len(string_value) > self.max_length:
            self.add_error(f"String length {len(string_value)} exceeds maximum length {self.max_length}")
            return False
            
        if self.pattern and not self.pattern.match(string_value):
            self.add_error(f"Value '{string_value}' does not match pattern {self.pattern.pattern}")
            return False
            
        return True


class NumericAdapter(BaseAdapter[Union[int, float, Decimal]]):
    """Numeric type adapter."""

    def __init__(self, min_value: Optional[float] = None, max_value: Optional[float] = None,
                 precision: Optional[int] = None, is_integer: bool = False, decimal: bool = False, **kwargs: Any) -> None:
        super().__init__()
        self.min_value = min_value
        self.max_value = max_value
        self.precision = precision
        self.is_integer = is_integer
        self.decimal = decimal

    def transform_field(self, value: Any) -> Optional[Union[int, float, Decimal]]:
        """Convert value to number."""
        if value is None:
            return None

        try:
            if isinstance(value, (int, float, Decimal)):
                num_value = value
            else:
                num_value = float(str(value).strip())

            if self.precision is not None:
                format_str = f"{{:.{self.precision}f}}"
                num_value = float(format_str.format(num_value))

            if self.decimal:
                return Decimal(str(num_value))
            if self.is_integer:
                return int(num_value)
            return num_value

        except (ValueError, TypeError, DecimalException):
            return None

    def validate_field(self, value: Any) -> bool:
        """Validate numeric value."""
        self.clear_cache()
        if value is None:
            return True

        try:
            num_value = float(str(value))

            if self.min_value is not None and num_value < self.min_value:
                self.add_error(f"Value {num_value} is less than minimum {self.min_value}")
                return False

            if self.max_value is not None and num_value > self.max_value:
                self.add_error(f"Value {num_value} exceeds maximum {self.max_value}")
                return False

            if self.precision is not None:
                str_value = str(num_value)
                if '.' in str_value:
                    decimal_places = len(str_value.split('.')[1])
                    if decimal_places > self.precision:
                        self.add_error(f"Value {num_value} exceeds precision of {self.precision} decimal places")
                        return False

            return True
        except (ValueError, TypeError):
            self.add_error(f"Invalid numeric value: {value}")
            return False


class DateAdapter(BaseAdapter[Union[date, str]]):
    """Date type adapter."""

    def __init__(self, min_date: Optional[date] = None, max_date: Optional[date] = None, 
                 formats: Optional[List[str]] = None, **kwargs: Any) -> None:
        super().__init__()
        self._format = kwargs.get('format', '%Y-%m-%d')
        self._allow_string = kwargs.get('allow_string', True)
        self.min_date = min_date
        self.max_date = max_date
        self.formats = formats or [self._format]

    def transform_field(self, value: Any) -> Optional[Union[date, str]]:
        """Transform value to date."""
        if value is None:
            return None

        if isinstance(value, date):
            return value if not self._allow_string else value.strftime(self._format)

        if isinstance(value, str):
            date_value = self._parse_date(value)
            if date_value is None:
                self.add_error(f"Could not parse date '{value}' with any configured format")
                return None
            return date_value if not self._allow_string else value

        self.add_error(f"Cannot convert {type(value)} to date")
        return None

    def validate_field(self, value: Any) -> bool:
        """Validate date value."""
        self.clear_cache()
        if value is None:
            return True

        try:
            date_value: Optional[date] = None
            if isinstance(value, (date, datetime)):
                date_value = value.date() if isinstance(value, datetime) else value
            else:
                date_value = self._parse_date(str(value))

            if date_value is None:
                self.add_error(f"Could not parse date: {value}")
                return False

            if self.min_date is not None and date_value < self.min_date:
                self.add_error(f"Date {date_value} is before minimum date {self.min_date}")
                return False

            if self.max_date is not None and date_value > self.max_date:
                self.add_error(f"Date {date_value} is after maximum date {self.max_date}")
                return False

            return True

        except (ValueError, TypeError) as e:
            self.add_error(f"Invalid date value: {str(e)}")
            return False

    def _parse_date(self, value: str) -> Optional[date]:
        """Try parsing date string with configured formats."""
        for format_str in self.formats:
            try:
                return datetime.strptime(value, format_str).date()
            except ValueError:
                continue
        return None


class BooleanAdapter(BaseAdapter[bool]):
    """Boolean type adapter."""

    TRUE_VALUES: ClassVar[Set[str]] = {"true", "1", "yes", "y", "t"}
    FALSE_VALUES: ClassVar[Set[str]] = {"false", "0", "no", "n", "f"}

    def __init__(self, case_sensitive: bool = False, **kwargs: Any) -> None:
        super().__init__()
        self.case_sensitive = case_sensitive

    def transform_field(self, value: Any) -> Optional[bool]:
        """Convert value to boolean."""
        if value is None:
            return None
        if isinstance(value, bool):
            return value

        check_value = str(value)
        if not self.case_sensitive:
            check_value = check_value.lower()

        if check_value in self.TRUE_VALUES:
            return True
        if check_value in self.FALSE_VALUES:
            return False
        return None

    def validate_field(self, value: Any) -> bool:
        """Validate boolean value."""
        self.clear_cache()
        if value is None:
            return True
        if isinstance(value, bool):
            return True

        check_value = str(value)
        if not self.case_sensitive:
            check_value = check_value.lower()

        if check_value not in self.TRUE_VALUES | self.FALSE_VALUES:
            self.add_error(f"Invalid boolean value: {value}")
            return False
        return True


class EnumAdapter(BaseAdapter[str]):
    """Enum type adapter."""

    def __init__(self, valid_values: Set[str], case_sensitive: bool = False, **kwargs: Any) -> None:
        super().__init__()
        self.case_sensitive = case_sensitive
        self.valid_values = valid_values if case_sensitive else {v.lower() for v in valid_values if v is not None}

    def transform_field(self, value: Any) -> Optional[str]:
        """Convert value to enum value."""
        if value is None:
            return None

        check_value = str(value)
        if not self.case_sensitive:
            check_value = check_value.lower()

        if check_value in self.valid_values:
            return str(value)
        return None

    def validate_field(self, value: Any) -> bool:
        """Validate enum value."""
        self.clear_cache()
        if value is None:
            return True

        check_value = str(value)
        if not self.case_sensitive:
            check_value = check_value.lower()

        if check_value not in self.valid_values:
            self.add_error(f"Invalid enum value: {value}")
            return False
        return True


class MoneyAdapter(NumericAdapter):
    """Adapter for monetary values."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('precision', 2)
        kwargs.setdefault('decimal', True)
        super().__init__(**kwargs)
        self.currency_symbol = kwargs.get("currency_symbol", "$")

    def transform_field(self, value: Any) -> Optional[Decimal]:
        """Convert value to decimal."""
        if value is None:
            return None

        try:
            # Clean the value if it's a string
            process_value = value.replace(self.currency_symbol, '').replace(',', '') if isinstance(value, str) else value
            result = super().transform_field(process_value)
            return Decimal(str(result)) if result is not None else None
        except Exception:
            return None

    def validate_field(self, value: Any) -> bool:
        """Validate monetary value."""
        if value is None:
            return True

        try:
            clean_value = value
            if isinstance(value, str):
                clean_value = value.replace(self.currency_symbol, '').replace(',', '')
            return super().validate_field(clean_value)
        except Exception as e:
            self.add_error(f"Invalid monetary value: {str(e)}")
            return False


class ListAdapter(BaseAdapter[List[T]]):
    """List type adapter."""

    def __init__(self, item_adapter: BaseAdapter[T], min_items: Optional[int] = None,
                 max_items: Optional[int] = None, **kwargs: Any) -> None:
        super().__init__()
        self.item_adapter = item_adapter
        self.min_items = min_items
        self.max_items = max_items

    def transform_field(self, value: Any) -> Optional[List[T]]:
        """Transform list and its items."""
        if value is None:
            return None
        if not isinstance(value, (list, tuple)):
            return None

        result: List[T] = []
        for item in value:
            transformed = self.item_adapter.transform_field(item)
            if transformed is not None:  # Skip None results
                result.append(transformed)
        return result

    def validate_field(self, value: Any) -> bool:
        """Validate list and its items."""
        self.clear_cache()
        if value is None:
            return True
        if not isinstance(value, (list, tuple)):
            self.add_error("Expected list value")
            return False

        if self.min_items is not None and len(value) < self.min_items:
            self.add_error(f"List has fewer than {self.min_items} items")
            return False

        if self.max_items is not None and len(value) > self.max_items:
            self.add_error(f"List has more than {self.max_items} items")
            return False

        # Validate each item
        for item in value:
            if not self.item_adapter.validate_field(item):
                self.errors.extend(self.item_adapter.errors)
                return False

        return True


class CompositeFieldAdapter(BaseAdapter[Any]):
    """Adapter that chains multiple transformations."""

    def __init__(self, field_name: str, transformations: List[Callable[[Any], Any]], required: bool = False, **kwargs: Any) -> None:
        super().__init__()
        self.field_name = field_name
        self.transformations = transformations
        self.required = required

    def transform_field(self, value: Any) -> Any:
        """Apply all transformations in sequence."""
        if value is None:
            return None

        result = value
        for transform in self.transformations:
            try:
                if result is None:
                    return None
                result = transform(result)
            except Exception as e:
                raise TransformationError(f"Error transforming {self.field_name}: {str(e)}") from e
        return result

    def validate_field(self, value: Any) -> bool:
        """Validate value can be transformed."""
        self.clear_cache()
        if value is None:
            if self.required:
                self.add_error(f"Required field {self.field_name} is missing")
                return False
            return True

        try:
            result = self.transform_field(value)
            return result is not None
        except TransformationError as e:
            self.add_error(str(e))
            return False
        except Exception as e:
            self.add_error(f"Unexpected error in transformation: {str(e)}")
            return False


class AdapterFactory:
    """Creates type adapters."""

    _adapters: ClassVar[Dict[FieldType, Union[Type[BaseAdapter[Any]], Callable[..., BaseAdapter[Any]]]]] = {
        FieldType.STRING: StringAdapter,
        FieldType.INTEGER: lambda **kwargs: NumericAdapter(is_integer=True, **kwargs),
        FieldType.FLOAT: NumericAdapter,
        FieldType.BOOLEAN: BooleanAdapter,
        FieldType.DATE: DateAdapter,
        FieldType.MONEY: MoneyAdapter,
        FieldType.ENUM: EnumAdapter
    }

    @classmethod
    def create_adapter(cls, field_type: FieldType, transformations: Optional[List[Dict[str, Any]]] = None, **kwargs: Any) -> BaseAdapter[Any]:
        """Create an adapter instance.
        
        Args:
            field_type: Type of the field
            transformations: List of transformation configurations
            **kwargs: Additional adapter configuration options
        """
        if transformations is None:
            transformations = []
            
        # Extract adapter config from transformations if present
        adapter_config = {}
        for transform in transformations:
            if transform.get("type") == "adapter_config":
                adapter_config = transform.get("parameters", {})
                break
                
        # Merge with provided kwargs
        adapter_config.update(kwargs)
        
        adapter_class_or_callable = cls._adapters.get(field_type)
        if not adapter_class_or_callable:
            raise AdapterError(f"No adapter found for type: {field_type}")

        # Create the appropriate adapter
        if callable(adapter_class_or_callable):
            adapter = cast(Callable[..., BaseAdapter[Any]], adapter_class_or_callable)(**adapter_config)
        else:
            adapter = adapter_class_or_callable(**adapter_config)
            
        # Apply transformations if it's a composite field
        if len(transformations) > 1:
            return CompositeFieldAdapter(
                field_name=kwargs.get("field_name", "unknown"),
                transformations=[adapter.transform_field],  # Start with the base adapter
                required=adapter_config.get("required", False)
            )
            
        return adapter


class IntegerAdapter(NumericAdapter):
    """Integer type adapter."""
    
    def __init__(self, **kwargs: Any) -> None:
        kwargs['is_integer'] = True
        super().__init__(**kwargs)
    
    def transform_field(self, value: Any) -> Optional[int]:
        """Convert value to integer."""
        result = super().transform_field(value)
        return int(result) if result is not None else None


__all__ = [
    'BaseAdapter',
    'StringAdapter',
    'NumericAdapter',
    'IntegerAdapter',
    'DateAdapter',
    'BooleanAdapter',
    'EnumAdapter',
    'MoneyAdapter',
    'ListAdapter',
    'CompositeFieldAdapter',
    'AdapterFactory'
]
