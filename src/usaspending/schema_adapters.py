"""Schema adapter interfaces and base implementations for field validation and transformation."""
from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, Optional, TypeVar, Union, List
from datetime import date, datetime
from decimal import Decimal

import pydantic
from marshmallow import Schema, fields
from dateutil import parser

T = TypeVar('T')
U = TypeVar('U')

class TransformationResult(Generic[T, U]):
    """Result of a transformation operation."""
    def __init__(self, success: bool, value: Union[U, str]):
        self.success = success
        self.value = value
        self.metadata: Dict[str, Any] = {}

    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to transformation result."""
        self.metadata[key] = value

class TransformationPipeline(Generic[T, U]):
    """Pipeline for chaining multiple transformations."""
    
    def __init__(self):
        self.transformations: List[Dict[str, Any]] = []
        
    def add_transformation(self, transform_fn: callable, config: Optional[Dict[str, Any]] = None) -> None:
        """Add a transformation to the pipeline."""
        self.transformations.append({
            'function': transform_fn,
            'config': config or {}
        })
        
    def execute(self, value: Any) -> TransformationResult[T, U]:
        """Execute all transformations in sequence."""
        current_value = value
        result = TransformationResult(True, current_value)
        
        for transform in self.transformations:
            try:
                if not result.success:
                    break
                current_value = transform['function'](current_value, **transform['config'])
                result = TransformationResult(True, current_value)
            except Exception as e:
                result = TransformationResult(False, str(e))
                break
                
        return result

class AdapterTransform:
    """Registry for adapter transformations."""
    
    _transforms: Dict[str, callable] = {}
    
    @classmethod
    def register(cls, name: str) -> callable:
        """Register a transformation function."""
        def decorator(fn: callable) -> callable:
            cls._transforms[name] = fn
            return fn
        return decorator
    
    @classmethod
    def get(cls, name: str) -> Optional[callable]:
        """Get a registered transformation function."""
        return cls._transforms.get(name)
        
# Built-in transformations
@AdapterTransform.register('uppercase')
def transform_uppercase(value: str) -> str:
    """Transform string to uppercase."""
    return str(value).upper()

@AdapterTransform.register('lowercase')
def transform_lowercase(value: str) -> str:
    """Transform string to lowercase."""
    return str(value).lower()

@AdapterTransform.register('trim')
def transform_trim(value: str) -> str:
    """Trim whitespace from string."""
    return str(value).strip()

@AdapterTransform.register('strip_characters')
def transform_strip_characters(value: str, characters: str = '') -> str:
    """Strip specific characters from string."""
    result = str(value)
    for char in characters:
        result = result.replace(char, '')
    return result

@AdapterTransform.register('pad_left')
def transform_pad_left(value: str, length: int = 0, character: str = '0') -> str:
    """Pad string on left with character to specified length."""
    return str(value).rjust(length, character)

@AdapterTransform.register('truncate')
def transform_truncate(value: str, max_length: int) -> str:
    """Truncate string to maximum length."""
    return str(value)[:max_length]

@AdapterTransform.register('convert_to_decimal')
def transform_convert_decimal(value: str, precision: Optional[int] = None) -> Decimal:
    """Convert string to decimal with optional precision."""
    try:
        # Strip currency symbols and grouping
        clean_value = str(value).strip().replace('$', '').replace(',', '')
        result = Decimal(clean_value)
        if precision is not None:
            return round(result, precision)
        return result
    except Exception as e:
        raise ValueError(f"Invalid decimal format: {str(e)}")

@AdapterTransform.register('convert_to_integer')
def transform_convert_integer(value: str) -> int:
    """Convert string to integer, handling decimal strings."""
    try:
        # Handle decimal strings by rounding
        float_val = float(str(value).strip().replace(',', ''))
        return round(float_val)
    except Exception as e:
        raise ValueError(f"Invalid integer format: {str(e)}")

@AdapterTransform.register('normalize_date')
def transform_normalize_date(value: str, input_formats: Optional[List[str]] = None, 
                           output_format: str = '%Y-%m-%d',
                           dayfirst: bool = False,
                           yearfirst: bool = False) -> str:
    """Normalize date string to consistent format."""
    try:
        if input_formats:
            for fmt in input_formats:
                try:
                    dt = datetime.strptime(value, fmt)
                    break
                except ValueError:
                    continue
            else:
                dt = parser.parse(value, dayfirst=dayfirst, yearfirst=yearfirst)
        else:
            dt = parser.parse(value, dayfirst=dayfirst, yearfirst=yearfirst)
        return dt.strftime(output_format)
    except Exception as e:
        raise ValueError(f"Invalid date format: {str(e)}")

class FieldAdapter(ABC, Generic[T, U]):
    """Base interface for field validation and transformation adapters."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize adapter with configuration."""
        self.config = config
        self.pipeline = TransformationPipeline[T, U]()
        self._setup_pipeline()
        self._validate_config()
    
    @abstractmethod
    def validate(self, value: Any) -> tuple[bool, Optional[str]]:
        """Validate a value according to field rules.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        pass
    
    @abstractmethod
    def transform(self, value: Any) -> tuple[bool, Union[U, str]]:
        """Transform a value according to field rules.
        
        Returns:
            Tuple of (success, transformed_value_or_error)
        """
        # Run pipeline transformations first
        if self.pipeline.transformations:
            result = self.pipeline.execute(value)
            if not result.success:
                return False, result.value
            value = result.value
            
        # Then run adapter-specific transformation
        return self._transform_value(value)
    
    @abstractmethod
    def _transform_value(self, value: Any) -> tuple[bool, Union[U, str]]:
        """Transform value using adapter-specific logic."""
        pass
    
    @abstractmethod
    def _validate_config(self) -> None:
        """Validate adapter configuration."""
        pass
        
    def _setup_pipeline(self) -> None:
        """Set up transformation pipeline from configuration."""
        if 'transformation' not in self.config:
            return
            
        transform_config = self.config['transformation']
        if 'operations' not in transform_config:
            return
            
        for operation in transform_config['operations']:
            if 'type' not in operation:
                continue
            transform_type = operation['type']
            # Remove type from config to avoid passing it to transform function
            operation_config = {k: v for k, v in operation.items() if k != 'type'}
            
            # Get transform function from registry
            transform_fn = self._get_transform_function(transform_type)
            if transform_fn:
                self.pipeline.add_transformation(transform_fn, operation_config)
    
    def _get_transform_function(self, transform_type: str) -> Optional[callable]:
        """Get transformation function from registry."""
        return AdapterTransform.get(transform_type)

class PydanticAdapter(FieldAdapter[T, U]):
    """Base adapter implementation using Pydantic models."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Pydantic adapter with model class and config."""
        super().__init__(config)
        self.model_class = self._create_model()
    
    @abstractmethod
    def _create_model(self) -> type[pydantic.BaseModel]:
        """Create Pydantic model for field validation/transformation."""
        pass
    
    def validate(self, value: Any) -> tuple[bool, Optional[str]]:
        """Validate value using Pydantic model."""
        try:
            # Run pre-validation transformations
            if self.pipeline.transformations:
                result = self.pipeline.execute(value)
                if not result.success:
                    return False, result.value
                value = result.value
            
            self.model_class(value=value)
            return True, None
        except pydantic.ValidationError as e:
            return False, str(e)
    
    def _transform_value(self, value: Any) -> tuple[bool, Union[U, str]]:
        """Transform value using Pydantic model."""
        try:
            # Model validation and transformation
            result = self.model_class(value=value)
            transformed = result.value
            
            # Check for post-transform operations
            post_transform = self.config.get('transformation', {}).get('post_transform')
            if post_transform:
                for operation in post_transform:
                    if 'type' not in operation:
                        continue
                    transform_fn = self._get_transform_function(operation['type'])
                    if transform_fn:
                        operation_config = {k: v for k, v in operation.items() if k != 'type'}
                        transformed = transform_fn(transformed, **operation_config)
            
            return True, transformed
        except Exception as e:
            return False, str(e)

class MarshmallowAdapter(FieldAdapter[T, U]):
    """Base adapter implementation using Marshmallow schemas."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Marshmallow adapter with schema class and config."""
        super().__init__(config)
        self.schema_class = self._create_schema()
        self.schema = self.schema_class()
    
    @abstractmethod
    def _create_schema(self) -> type[Schema]:
        """Create Marshmallow schema for field validation/transformation."""
        pass
    
    def validate(self, value: Any) -> tuple[bool, Optional[str]]:
        """Validate value using Marshmallow schema."""
        errors = self.schema.validate({"value": value})
        if errors:
            return False, str(errors)
        return True, None
    
    def _transform_value(self, value: Any) -> tuple[bool, Union[U, str]]:
        """Transform value using Marshmallow schema."""
        try:
            result = self.schema.load({"value": value})
            return True, result["value"]
        except Exception as e:
            return False, str(e)

# Common field adapters using Pydantic
class DateFieldAdapter(PydanticAdapter[str, date]):
    """Date field adapter using Pydantic."""
    
    def _create_model(self) -> type[pydantic.BaseModel]:
        """Create Pydantic model for date validation/transformation."""
        class DateModel(pydantic.BaseModel):
            value: date
            format: str = self.config.get('format', '%Y-%m-%d')
            
            @pydantic.validator('value', pre=True)
            def parse_date(cls, v):
                if isinstance(v, str):
                    try:
                        return parser.parse(v).date()
                    except Exception as e:
                        raise ValueError(f"Invalid date format: {str(e)}")
                return v
        
        return DateModel
    
    def _validate_config(self) -> None:
        """Validate date adapter configuration."""
        if 'format' in self.config and not isinstance(self.config['format'], str):
            raise ValueError("'format' must be a string")

class DecimalFieldAdapter(PydanticAdapter[Union[str, float], Decimal]):
    """Decimal field adapter using Pydantic."""
    
    def _create_model(self) -> type[pydantic.BaseModel]:
        """Create Pydantic model for decimal validation/transformation."""
        class DecimalModel(pydantic.BaseModel):
            value: Decimal = pydantic.Field(
                decimal_places=self.config.get('precision', 2),
                ge=self.config.get('min_value'),
                le=self.config.get('max_value')
            )
            
            @pydantic.validator('value', pre=True)
            def parse_decimal(cls, v):
                if isinstance(v, str):
                    # Strip currency symbols and grouping
                    v = v.strip().replace('$', '').replace(',', '')
                try:
                    return Decimal(v)
                except Exception as e:
                    raise ValueError(f"Invalid decimal format: {str(e)}")
        
        return DecimalModel
    
    def _validate_config(self) -> None:
        """Validate decimal adapter configuration."""
        if 'precision' in self.config:
            if not isinstance(self.config['precision'], int):
                raise ValueError("'precision' must be an integer")
            if self.config['precision'] < 0:
                raise ValueError("'precision' must be non-negative")

class SchemaAdapterFactory:
    """Factory for creating field adapters."""
    
    # Registry of base adapter types
    _adapters: Dict[str, type[FieldAdapter]] = {}
    
    @classmethod
    def register(cls, type_name: str, adapter_class: type[FieldAdapter]) -> None:
        """Register a new adapter class."""
        cls._adapters[type_name] = adapter_class
    
    @classmethod
    def create(cls, type_name: str, config: Dict[str, Any]) -> Optional[FieldAdapter]:
        """Create an adapter instance for the given type."""
        adapter_class = cls._adapters.get(type_name)
        if adapter_class:
            try:
                return adapter_class(config)
            except Exception as e:
                raise ValueError(f"Failed to create adapter for type '{type_name}': {str(e)}")
        return None

    @classmethod
    def get_available_types(cls) -> list[str]:
        """Get list of available adapter types."""
        return list(cls._adapters.keys())

# Register core adapter types
SchemaAdapterFactory.register('date', DateFieldAdapter)
SchemaAdapterFactory.register('decimal', DecimalFieldAdapter)