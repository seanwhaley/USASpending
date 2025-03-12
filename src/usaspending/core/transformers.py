"""Core data transformation functionality."""
from typing import Dict, Any, List, Optional, Callable, Type, Literal, TypeVar, Generic, Protocol, cast
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
import re
from .types import TransformationRule, TransformerType
from .exceptions import TransformationError

@dataclass
class BaseTransformParams:
    """Base class for transformer parameters."""
    pass

@dataclass
class StringTransformParams(BaseTransformParams):
    """Parameters for string transformations."""
    trim: bool = True
    case: Optional[Literal["upper", "lower", "title"]] = None
    length: Optional[int] = None
    pad_side: Optional[Literal["left", "right"]] = None
    pad_char: str = " "
    pattern: Optional[str] = None

@dataclass
class NumericTransformParams(BaseTransformParams):
    """Parameters for numeric transformations."""
    round: Optional[int] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    integer: bool = False

@dataclass
class DateTransformParams(BaseTransformParams):
    """Parameters for date transformations."""
    input_format: str = "%Y-%m-%d"
    output_format: str = "%Y-%m-%d"
    offset_days: Optional[int] = None

@dataclass
class BooleanTransformParams(BaseTransformParams):
    """Parameters for boolean transformations."""
    true_values: Optional[List[str]] = None
    false_values: Optional[List[str]] = None

@dataclass
class EnumTransformParams(BaseTransformParams):
    """Parameters for enum transformations."""
    mappings: Dict[str, str]
    default: Optional[str] = None

P = TypeVar('P', bound=BaseTransformParams)

class ITransformer(Protocol):
    """Interface for transformers."""
    def transform(self, value: Any, parameters: BaseTransformParams) -> Any:
        ...

class BaseTransformer(Generic[P]):
    """Base transformer interface."""
    def transform(self, value: Any, parameters: BaseTransformParams) -> Any:
        """Transform a value using specific parameters."""
        if not isinstance(parameters, self._get_params_type()):
            raise TypeError(f"Expected {self._get_params_type().__name__} parameters")
        return self._transform(value, parameters)
        
    @abstractmethod
    def _transform(self, value: Any, parameters: P) -> Any:
        """Internal transform implementation."""
        pass
        
    @abstractmethod
    def _get_params_type(self) -> Type[P]:
        """Get the parameter type for this transformer."""
        pass

class StringTransformer(BaseTransformer[StringTransformParams]):
    """String transformations."""
    
    def _transform(self, value: Any, parameters: StringTransformParams) -> str:
        """Transform string value."""
        if value is None:
            return ""
            
        result = str(value)
        
        # Apply transformations in order
        if parameters.trim:
            result = result.strip()
            
        if parameters.case:
            if parameters.case == "upper":
                result = result.upper()
            elif parameters.case == "lower":
                result = result.lower()
            elif parameters.case == "title":
                result = result.title()
                
        if parameters.length:
            if parameters.pad_side == "left":
                result = result.rjust(parameters.length, parameters.pad_char)
            else:
                result = result.ljust(parameters.length, parameters.pad_char)
                
        if parameters.pattern:
            if not re.match(parameters.pattern, result):
                raise TransformationError(f"Value does not match pattern: {parameters.pattern}")
                
        return result
    
    def _get_params_type(self) -> Type[StringTransformParams]:
        return StringTransformParams

class NumericTransformer(BaseTransformer[NumericTransformParams]):
    """Numeric transformations."""
    
    def _transform(self, value: Any, parameters: NumericTransformParams) -> Optional[float]:
        """Transform numeric value."""
        if value is None:
            return None
            
        try:
            # Convert to float first
            result = float(str(value))
            
            # Apply transformations
            if parameters.round is not None:
                result = round(result, parameters.round)
                
            if parameters.min_value is not None and result < parameters.min_value:
                result = parameters.min_value
                
            if parameters.max_value is not None and result > parameters.max_value:
                result = parameters.max_value
                
            # Convert to integer if specified
            if parameters.integer:
                result = int(result)
                
            return result
            
        except (ValueError, TypeError) as e:
            raise TransformationError(f"Invalid numeric value: {str(e)}")
    
    def _get_params_type(self) -> Type[NumericTransformParams]:
        return NumericTransformParams

class DateTransformer(BaseTransformer[DateTransformParams]):
    """Date transformations."""
    
    def _transform(self, value: Any, parameters: DateTransformParams) -> Optional[str]:
        """Transform date value."""
        if value is None:
            return None
            
        try:
            # Parse input date
            if isinstance(value, datetime):
                date = value
            else:
                date = datetime.strptime(str(value), parameters.input_format)
                
            # Apply transformations
            if parameters.offset_days is not None:
                date += timedelta(days=parameters.offset_days)
                
            # Format output
            return date.strftime(parameters.output_format)
            
        except (ValueError, TypeError) as e:
            raise TransformationError(f"Invalid date value: {str(e)}")
    
    def _get_params_type(self) -> Type[DateTransformParams]:
        return DateTransformParams

class BooleanTransformer(BaseTransformer[BooleanTransformParams]):
    """Boolean transformations."""
    
    TRUE_VALUES = {"true", "1", "yes", "y", "t"}
    FALSE_VALUES = {"false", "0", "no", "n", "f"}
    
    def _transform(self, value: Any, parameters: BooleanTransformParams) -> Optional[bool]:
        """Transform boolean value."""
        if value is None:
            return None
            
        if isinstance(value, bool):
            return value
            
        string_value = str(value).lower()
        
        # Use custom mappings if provided
        true_values = set(parameters.true_values or []) | self.TRUE_VALUES
        false_values = set(parameters.false_values or []) | self.FALSE_VALUES
        
        if string_value in true_values:
            return True
        if string_value in false_values:
            return False
            
        raise TransformationError(f"Invalid boolean value: {value}")
    
    def _get_params_type(self) -> Type[BooleanTransformParams]:
        return BooleanTransformParams

class EnumTransformer(BaseTransformer[EnumTransformParams]):
    """Enum transformations."""
    
    def _transform(self, value: Any, parameters: EnumTransformParams) -> Optional[str]:
        """Transform enum value."""
        if value is None:
            return None
            
        string_value = str(value).upper()
        
        # Try direct mapping
        if string_value in parameters.mappings:
            return parameters.mappings[string_value]
            
        # Try case-insensitive mapping
        for k, v in parameters.mappings.items():
            if k.upper() == string_value:
                return v
                
        # Use default or raise error
        if parameters.default is not None:
            return parameters.default
            
        raise TransformationError(f"Invalid enum value: {value}")
    
    def _get_params_type(self) -> Type[EnumTransformParams]:
        return EnumTransformParams

@dataclass
class TransformerConfig:
    """Configuration for transformer factory."""
    type: TransformerType
    parameters: Dict[str, Any]

class TransformerFactory:
    """Factory for creating data transformers."""
    
    _transformers: Dict[TransformerType, Type[BaseTransformer[Any]]] = {
        "string": StringTransformer,
        "numeric": NumericTransformer,
        "date": DateTransformer,
        "boolean": BooleanTransformer,
        "enum": EnumTransformer
    }
    
    _params: Dict[TransformerType, Type[BaseTransformParams]] = {
        "string": StringTransformParams,
        "numeric": NumericTransformParams,
        "date": DateTransformParams,
        "boolean": BooleanTransformParams,
        "enum": EnumTransformParams
    }
    
    @classmethod
    def create_transformer(cls, transform_type: TransformerType, parameters: Optional[Dict[str, Any]] = None) -> BaseTransformer[Any]:
        """Create a transformer instance."""
        if transform_type not in cls._transformers:
            raise ValueError(f"Unknown transformer type: {transform_type}")
            
        transformer_class = cls._transformers[transform_type]
        params_class = cls._params[transform_type]
        
        if parameters is None:
            parameters = {}
            
        params = params_class(**parameters)
        return transformer_class()

class TransformationEngine:
    """Coordinates data transformations."""
    
    def __init__(self) -> None:
        """Initialize transformation engine."""
        self.factory = TransformerFactory()
        
    def transform_value(self, value: Any, rule: TransformationRule) -> Any:
        """Transform a value using a rule."""
        transformer = self.factory.create_transformer(rule.transform_type)
        params_class = self._get_params_class(rule.transform_type)
        params = params_class(**rule.parameters)
        return transformer.transform(value, params)
        
    def transform_data(self, data: Dict[str, Any], rules: List[TransformationRule]) -> Dict[str, Any]:
        """Transform data using multiple rules."""
        result = data.copy()
        
        for rule in rules:
            if rule.field_name in result:
                try:
                    result[rule.field_name] = self.transform_value(
                        result[rule.field_name], rule)
                except TransformationError as e:
                    # Add field context to error
                    raise TransformationError(
                        f"Error transforming field {rule.field_name}: {str(e)}")
                        
        return result
    
    def _get_params_class(self, transform_type: TransformerType) -> Type[BaseTransformParams]:
        """Get the parameter class for a transformer type."""
        params_map: Dict[TransformerType, Type[BaseTransformParams]] = {
            "string": StringTransformParams,
            "numeric": NumericTransformParams,
            "date": DateTransformParams,
            "boolean": BooleanTransformParams,
            "enum": EnumTransformParams
        }
        return params_map.get(transform_type, BaseTransformParams)

__all__ = [
    # Base Classes
    'BaseTransformer',
    'BaseTransformParams',
    
    # Transformer Classes
    'StringTransformer',
    'NumericTransformer',
    'DateTransformer',
    'BooleanTransformer',
    'EnumTransformer',
    
    # Parameter Classes
    'StringTransformParams',
    'NumericTransformParams',
    'DateTransformParams',  
    'BooleanTransformParams',
    'EnumTransformParams',
    
    # Factory and Engine
    'TransformerFactory',
    'TransformationEngine'
]