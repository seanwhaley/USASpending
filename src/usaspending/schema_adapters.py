"""Schema adapter interfaces and base implementations for field validation and transformation."""
from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, Optional, TypeVar, Union, List, Set
from datetime import date, datetime
from decimal import Decimal
import re
from collections import defaultdict
import uuid

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
        """Initialize transformation pipeline."""
        self.transformations: List[Dict[str, Any]] = []
        self.composed_transforms: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.dependencies: Dict[str, Set[str]] = defaultdict(set)
        self.metadata: Dict[str, Any] = {}
        
    def add_transformation(self, transform_fn: callable, config: Optional[Dict[str, Any]] = None,
                         depends_on: Optional[List[str]] = None,
                         provides: Optional[str] = None) -> None:
        """Add a transformation to the pipeline.
        
        Args:
            transform_fn: The transformation function to add
            config: Optional configuration for the transformation
            depends_on: Optional list of outputs this transform depends on
            provides: Optional name of the output this transform provides
        """
        transform_config = {
            'function': transform_fn,
            'config': config or {},
            'id': str(uuid.uuid4()),
        }
        
        if depends_on:
            for dep in depends_on:
                self.dependencies[transform_config['id']].add(dep)
                
        if provides:
            transform_config['provides'] = provides
            # Add to composed transforms if it has dependencies
            if depends_on:
                self.composed_transforms[provides].append(transform_config)
            
        self.transformations.append(transform_config)
        
    def execute(self, value: Any) -> TransformationResult[T, U]:
        """Execute all transformations in sequence with dependency handling."""
        current_value = value
        result = TransformationResult(True, current_value)
        transform_outputs: Dict[str, Any] = {}
        
        try:
            # First run independent transforms
            for transform in self.transformations:
                if not self.dependencies[transform['id']]:
                    current_value = self._execute_transform(transform, current_value)
                    if 'provides' in transform:
                        transform_outputs[transform['provides']] = current_value
            
            # Then run dependent transforms in order
            for output_name, transforms in self.composed_transforms.items():
                for transform in transforms:
                    # Check if dependencies are met
                    deps = self.dependencies[transform['id']]
                    if all(dep in transform_outputs for dep in deps):
                        # Update config with dependency outputs
                        config = transform['config'].copy()
                        for dep in deps:
                            config[f"dep_{dep}"] = transform_outputs[dep]
                            
                        current_value = transform['function'](current_value, **config)
                        transform_outputs[output_name] = current_value
                        
            result = TransformationResult(True, current_value)
            result.metadata['transform_outputs'] = transform_outputs
            
        except Exception as e:
            result = TransformationResult(False, str(e))
            
        return result
    
    def _execute_transform(self, transform: Dict[str, Any], value: Any) -> Any:
        """Execute a single transformation."""
        return transform['function'](value, **transform['config'])
        
    def _topological_sort(self) -> List[Dict[str, Any]]:
        """Sort transformations by dependencies."""
        in_degree = defaultdict(int)
        graph = defaultdict(list)
        
        # Build dependency graph
        for transform in self.transformations:
            transform_id = transform['id']
            for dep in self.dependencies[transform_id]:
                in_degree[transform_id] += 1
                for t in self.transformations:
                    if t.get('provides') == dep:
                        graph[t['id']].append(transform_id)
                        
        # Find roots (nodes with no dependencies)
        queue = [t['id'] for t in self.transformations if in_degree[t['id']] == 0]
        sorted_ids = []
        
        while queue:
            node = queue.pop(0)
            sorted_ids.append(node)
            
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
                    
        if len(sorted_ids) != len(self.transformations):
            raise ValueError("Circular dependency detected in transformations")
            
        # Map back to transform configs
        id_to_transform = {t['id']: t for t in self.transformations}
        return [id_to_transform[id_] for id_ in sorted_ids]

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
                           yearfirst: bool = False,
                           fuzzy: bool = False) -> str:
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
                dt = parser.parse(value, dayfirst=dayfirst, yearfirst=yearfirst, fuzzy=fuzzy)
        else:
            dt = parser.parse(value, dayfirst=dayfirst, yearfirst=yearfirst, fuzzy=fuzzy)
        return dt.strftime(output_format)
    except Exception as e:
        raise ValueError(f"Invalid date format: {str(e)}")

@AdapterTransform.register('derive_fiscal_year')
def transform_derive_fiscal_year(value: str, fiscal_year_start_month: int = 10,
                               input_format: Optional[str] = None) -> int:
    """Derive fiscal year from date string."""
    try:
        if input_format:
            dt = datetime.strptime(value, input_format)
        else:
            dt = parser.parse(value)
        
        if dt.month >= fiscal_year_start_month:
            return dt.year + 1
        return dt.year
    except Exception as e:
        raise ValueError(f"Invalid date for fiscal year calculation: {str(e)}")

@AdapterTransform.register('derive_date_components')
def transform_derive_date_components(value: str, 
                                   components: List[str],
                                   fiscal_year_start_month: int = 10,
                                   input_format: Optional[str] = None) -> Dict[str, Any]:
    """Extract date components like year, month, quarter, etc."""
    try:
        if input_format:
            dt = datetime.strptime(value, input_format)
        else:
            dt = parser.parse(value)
        
        result = {}
        for component in components:
            if component == 'year':
                result['year'] = dt.year
            elif component == 'month':
                result['month'] = dt.month
            elif component == 'day':
                result['day'] = dt.day
            elif component == 'quarter':
                result['quarter'] = (dt.month - 1) // 3 + 1
            elif component == 'fiscal_year':
                result['fiscal_year'] = dt.year + 1 if dt.month >= fiscal_year_start_month else dt.year
            elif component == 'fiscal_quarter':
                adjusted_month = (dt.month - fiscal_year_start_month) % 12 + 1
                result['fiscal_quarter'] = (adjusted_month - 1) // 3 + 1
            elif component == 'day_of_year':
                result['day_of_year'] = dt.timetuple().tm_yday
            elif component == 'week_of_year':
                result['week_of_year'] = dt.isocalendar()[1]
            elif component == 'day_of_week':
                result['day_of_week'] = dt.isoweekday()
            elif component == 'is_weekend':
                result['is_weekend'] = dt.isoweekday() in (6, 7)
        return result
    except Exception as e:
        raise ValueError(f"Invalid date for component extraction: {str(e)}")

@AdapterTransform.register('round_number')
def transform_round_number(value: Union[int, float, Decimal, str], places: int = 0) -> Union[int, float]:
    """Round a number to specified decimal places."""
    try:
        if isinstance(value, str):
            value = float(value.strip().replace(',', ''))
        return round(float(value), places)
    except Exception as e:
        raise ValueError(f"Invalid number for rounding: {str(e)}")

@AdapterTransform.register('format_number')
def transform_format_number(value: Union[int, float, Decimal, str], 
                          precision: int = 2,
                          currency: bool = False,
                          grouping: bool = False) -> str:
    """Format a number with specified options."""
    try:
        if isinstance(value, str):
            value = float(value.strip().replace(',', ''))
            
        # Format with specified precision
        formatted = f"{float(value):,.{precision}f}" if grouping else f"{float(value):.{precision}f}"
        
        # Add currency symbol if requested
        if currency:
            formatted = f"${formatted}"
            
        return formatted
    except Exception as e:
        raise ValueError(f"Invalid number for formatting: {str(e)}")

@AdapterTransform.register('map_values')
def transform_map_values(value: str, mapping: Dict[str, Any], 
                        case_sensitive: bool = True,
                        default: Optional[Any] = None) -> Any:
    """Map input values to output values using a mapping dictionary."""
    str_value = str(value)
    
    # Direct mapping check
    if case_sensitive:
        if str_value in mapping:
            return mapping[str_value]
    else:
        # Case-insensitive mapping check
        upper_value = str_value.upper()
        for k, v in mapping.items():
            if str(k).upper() == upper_value:
                return v
    
    # Return default if specified, otherwise original value
    return default if default is not None else value

@AdapterTransform.register('normalize_enum')
def transform_normalize_enum(value: str, valid_values: Set[str], 
                           case_sensitive: bool = True,
                           default: Optional[str] = None) -> str:
    """Normalize enum value against a set of valid values."""
    if case_sensitive:
        if value in valid_values:
            return value
    else:
        # Case-insensitive check
        upper_value = value.upper()
        for v in valid_values:
            if v.upper() == upper_value:
                return v
    
    # Return default if specified, otherwise original value
    return default if default is not None else value

@AdapterTransform.register('normalize_whitespace')
def transform_normalize_whitespace(value: str) -> str:
    """Normalize whitespace in string."""
    return ' '.join(str(value).split())

@AdapterTransform.register('replace_chars')
def transform_replace_chars(value: str, replacements: Dict[str, str]) -> str:
    """Replace characters in string according to mapping."""
    result = str(value)
    for old, new in replacements.items():
        result = result.replace(old, new)
    return result

@AdapterTransform.register('extract_pattern')
def transform_extract_pattern(value: str, pattern: str) -> str:
    """Extract first match of pattern from string."""
    match = re.search(pattern, str(value))
    return match.group(0) if match else value

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
    
    def transform(self, value: Any) -> tuple[bool, Union[U, str]]:
        """Transform a value according to field rules."""
        # Run pipeline transformations first
        if self.pipeline.transformations:
            result = self.pipeline.execute(value)
            if not result.success:
                return False, result.value
            value = result.value
            
        # Then run adapter-specific transformation
        return self._transform_value(value)
    
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
    
    def transform(self, value: Any) -> tuple[bool, Union[U, str]]:
        """Transform a value according to field rules."""
        # Run pipeline transformations first
        if self.pipeline.transformations:
            result = self.pipeline.execute(value)
            if not result.success:
                return False, result.value
            value = result.value
            
        # Then run adapter-specific transformation
        return self._transform_value(value)
    
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
        class DateValueModel(pydantic.BaseModel):
            model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)
            value: date = pydantic.Field(default=...)

            @pydantic.field_validator('value', mode='before')
            @classmethod
            def parse_date(cls, v: Any) -> date:
                if isinstance(v, str):
                    try:
                        return parser.parse(v, dayfirst=False).date()
                    except Exception as e:
                        raise ValueError(f"Invalid date format: {str(e)}")
                elif isinstance(v, datetime):
                    return v.date()
                elif isinstance(v, date):
                    return v
                raise ValueError(f"Cannot convert {type(v)} to date")

        return DateValueModel

    def _validate_config(self) -> None:
        """Validate date adapter configuration."""
        if 'format' in self.config and not isinstance(self.config['format'], str):
            raise ValueError("'format' must be a string")
    
    def transform(self, value: Any) -> tuple[bool, Union[date, str]]:
        """Transform a value according to field rules."""
        try:
            # First parse the date
            if isinstance(value, str):
                try:
                    # Always parse with yearfirst=False to maintain consistency
                    parsed_date = parser.parse(value, dayfirst=False).date()
                except Exception as e:
                    return False, f"Invalid date format: {str(e)}"
            elif isinstance(value, datetime):
                parsed_date = value.date()
            elif isinstance(value, date):
                parsed_date = value
            else:
                return False, f"Cannot convert {type(value)} to date"

            # Run pipeline transformations if any
            if self.pipeline.transformations:
                # Check if we need to apply any date-specific transformations
                date_transform = next((t for t in self.pipeline.transformations 
                                    if t['function'].__name__ in ('transform_normalize_date', 'transform_derive_fiscal_year')), None)
                
                if date_transform:
                    # Use ISO format for string-based transformations
                    date_str = parsed_date.isoformat()
                    result = self.pipeline.execute(date_str)
                    
                    if not result.success:
                        return False, result.value
                    
                    # If it's a fiscal year transformation, return the integer result
                    if date_transform['function'].__name__ == 'transform_derive_fiscal_year':
                        return True, result.value
                    
                    # Otherwise try to parse the result back to a date
                    try:
                        return True, parser.parse(result.value).date() if isinstance(result.value, str) else result.value
                    except Exception:
                        return True, result.value
            
            # If no transformations, validate through model and return
            return self._transform_value(parsed_date)
            
        except Exception as e:
            return False, str(e)
    
    def _transform_value(self, value: Any) -> tuple[bool, Union[date, str]]:
        """Transform value using Pydantic model."""
        try:
            result = self.model_class(value=value)
            return True, result.value
        except Exception as e:
            return False, str(e)

class DecimalFieldAdapter(PydanticAdapter[Union[str, float], Decimal]):
    """Decimal field adapter using Pydantic."""
    
    def _create_model(self) -> type[pydantic.BaseModel]:
        """Create Pydantic model for decimal validation/transformation."""
        class DecimalModel(pydantic.BaseModel):
            model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)
            value: Decimal = pydantic.Field(
                validation_alias='value',
                decimal_places=self.config.get('precision', 2),
                ge=self.config.get('min_value'),
                le=self.config.get('max_value')
            )
            
            @pydantic.field_validator('value', mode='before')
            @classmethod
            def parse_decimal(cls, v):
                if isinstance(v, str):
                    # Strip currency symbols and grouping
                    v = v.strip().replace('$', '').replace(',', '')
                try:
                    return Decimal(str(v))
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
    
    def _transform_value(self, value: Any) -> tuple[bool, Union[Decimal, str]]:
        """Transform value to a decimal."""
        try:
            # Model validation and transformation
            result = self.model_class(value=value)
            transformed = result.value
            
            # Apply any post-transform operations
            post_transform = self.config.get('transformation', {}).get('post_transform', [])
            for operation in post_transform:
                if 'type' not in operation:
                    continue
                transform_fn = self._get_transform_function(operation['type'])
                if transform_fn:
                    operation_config = {k: v for k, v in operation.items() if k != 'type'}
                    transformed = transform_fn(transformed, **operation_config)
            
            # Handle formatting transformation in chain
            for transform in self.pipeline.transformations:
                if transform['function'].__name__ == 'transform_format_number':
                    transformed = transform['function'](transformed, **transform['config'])
            
            return True, transformed
        except Exception as e:
            return False, str(e)

class EnumFieldAdapter(PydanticAdapter[str, str]):
    """Enum field adapter using Pydantic."""
    
    def _create_model(self) -> type[pydantic.BaseModel]:
        """Create Pydantic model for enum validation/transformation."""
        values = self.config.get('values', set())
        case_sensitive = self.config.get('case_sensitive', True)
        
        class EnumModel(pydantic.BaseModel):
            value: str
            
            @pydantic.field_validator('value')
            @classmethod
            def validate_enum(cls, v):
                check_value = v if case_sensitive else v.upper()
                valid_values = values if case_sensitive else {val.upper() for val in values}
                if check_value not in valid_values:
                    raise ValueError(f"Value must be one of: {', '.join(values)}")
                return v
        
        return EnumModel
    
    def _validate_config(self) -> None:
        """Validate enum adapter configuration."""
        if 'values' not in self.config or not isinstance(self.config['values'], (list, set)):
            raise ValueError("'values' must be a list or set of valid enum values")
        self.config['values'] = set(self.config['values'])
    
    def transform(self, value: Any) -> tuple[bool, Union[str, str]]:
        """Transform value to a normalized enum value."""
        return super().transform(value)

class CompositeFieldAdapter(PydanticAdapter[Dict[str, Any], Dict[str, Any]]):
    """Adapter for fields that produce multiple output values."""
    
    def _create_model(self) -> type[pydantic.BaseModel]:
        """Create Pydantic model for composite field validation."""
        components = self.config.get('components', [])
        validators = self.config.get('validators', {})
        
        class CompositeModel(pydantic.BaseModel):
            model_config = pydantic.ConfigDict(extra='allow')
            value: Dict[str, Any]
            
            @pydantic.field_validator('value')
            @classmethod
            def validate_components(cls, v):
                if not isinstance(v, dict):
                    raise ValueError("Value must be a dictionary")
                
                # Check required components
                for comp in components:
                    if comp not in v:
                        raise ValueError(f"Missing required component: {comp}")
                
                # Apply component validators
                for comp, validator in validators.items():
                    if comp in v:
                        try:
                            v[comp] = validator(v[comp])
                        except Exception as e:
                            raise ValueError(f"Invalid value for {comp}: {str(e)}")
                
                return v
        
        return CompositeModel
    
    def _validate_config(self) -> None:
        """Validate composite adapter configuration."""
        if 'components' not in self.config or not isinstance(self.config['components'], list):
            raise ValueError("'components' must be a list of required component names")
    
    def transform(self, value: Any) -> tuple[bool, Union[Dict[str, Any], str]]:
        """Transform value to a component dictionary."""
        return super().transform(value)

class MappedEnumAdapter(PydanticAdapter[str, str]):
    """Adapter for enums with value mapping."""
    
    def _create_model(self) -> type[pydantic.BaseModel]:
        """Create Pydantic model for mapped enum validation."""
        mapping = self.config.get('mapping', {})
        case_sensitive = self.config.get('case_sensitive', True)
        default = self.config.get('default')
        
        class MappedEnumModel(pydantic.BaseModel):
            value: str
            
            @pydantic.field_validator('value')
            @classmethod
            def map_value(cls, v):
                if case_sensitive:
                    mapped = mapping.get(v, default)
                else:
                    upper_v = v.upper()
                    for k, val in mapping.items():
                        if str(k).upper() == upper_v:
                            return val
                    mapped = default
                
                if mapped is None and default is None:
                    raise ValueError(f"Invalid value: {v}")
                return mapped if mapped is not None else v
        
        return MappedEnumModel
    
    def _validate_config(self) -> None:
        """Validate mapped enum adapter configuration."""
        if 'mapping' not in self.config or not isinstance(self.config['mapping'], dict):
            raise ValueError("'mapping' must be a dictionary")
    
    def transform(self, value: Any) -> tuple[bool, Union[str, str]]:
        """Transform value using enum mapping."""
        return super().transform(value)

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
SchemaAdapterFactory.register('enum', EnumFieldAdapter)
SchemaAdapterFactory.register('mapped_enum', MappedEnumAdapter)
SchemaAdapterFactory.register('composite', CompositeFieldAdapter)