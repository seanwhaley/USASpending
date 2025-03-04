"""Field transformation system for USASpending data processing."""
from typing import Dict, Any, List, Optional, Union, Tuple, TypeVar, Generic, Set, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from collections import defaultdict
import re
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

# Add dateutil imports with graceful error handling
try:
    from dateutil import parser
    from dateutil.parser import ParserError
    DATEUTIL_AVAILABLE = True
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("python-dateutil package not found. Date transformers will have limited functionality.")
    DATEUTIL_AVAILABLE = False
    # Define minimal versions for type checking
    class ParserError(Exception):
        pass

from .logging_config import get_logger

logger = get_logger(__name__)

# Type variable for input/output value types
T = TypeVar('T')
U = TypeVar('U')

@dataclass
class TransformationResult(Generic[T, U]):
    """Result of a field transformation operation."""
    transformed: bool
    original_value: T
    value: U
    messages: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def success(self) -> bool:
        """Whether the transformation was successful (transformed with no errors)."""
        return self.transformed and not self.errors
    
    @property
    def has_errors(self) -> bool:
        """Whether the transformation encountered any errors."""
        return bool(self.errors)
    
    def add_message(self, message: str) -> None:
        """Add an informational message to the transformation result."""
        self.messages.append(message)
    
    def add_error(self, error: str) -> None:
        """Add an error message to the transformation result."""
        self.errors.append(error)
        
    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to the transformation result."""
        self.metadata[key] = value
        
    @classmethod
    def success_result(cls, original_value: T, value: U) -> 'TransformationResult[T, U]':
        """Create a successful transformation result."""
        return cls(transformed=True, original_value=original_value, value=value)
    
    @classmethod
    def unchanged(cls, value: T) -> 'TransformationResult[T, T]':
        """Create a result for unchanged value."""
        return cls(transformed=False, original_value=value, value=value)
    
    @classmethod
    def failure(cls, original_value: T, error: str) -> 'TransformationResult[T, T]':
        """Create a failed transformation result."""
        result = cls(transformed=False, original_value=original_value, value=original_value)
        result.add_error(error)
        return result


class Transformer(ABC, Generic[T, U]):
    """Base class for all field transformers."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the transformer with configuration parameters."""
        self.config = config
        self.stats: Dict[str, int] = defaultdict(int)
        self.transformation_errors: List[str] = []
        self._validate_config()
    
    @abstractmethod
    def transform(self, value: T, field_name: Optional[str] = None) -> TransformationResult[T, U]:
        """Transform a single value according to transformer rules."""
        pass
    
    def transform_batch(self, values: List[T], field_name: Optional[str] = None) -> List[TransformationResult[T, U]]:
        """Transform a batch of values (with optional optimization)."""
        results = []
        for value in values:
            results.append(self.transform(value, field_name))
        return results
    
    @abstractmethod
    def _validate_config(self) -> None:
        """Validate transformer configuration."""
        pass
    
    def can_handle_type(self, value: Any) -> bool:
        """Check if this transformer can handle the given value type."""
        return True  # Default implementation accepts any type
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about transformations performed."""
        return dict(self.stats)
    
    def log_stats(self) -> None:
        """Log transformation statistics."""
        stats = self.get_stats()
        total = stats.get('total', 0)
        if total > 0:
            success = stats.get('success', 0)
            failure = stats.get('failure', 0)
            unchanged = stats.get('unchanged', 0)
            success_rate = (success / total) * 100 if total > 0 else 0
            
            logger.info(f"Transformation stats for {self.__class__.__name__}:")
            logger.info(f"  Total: {total:,d}")
            logger.info(f"  Success: {success:,d} ({success_rate:.1f}%)")
            logger.info(f"  Failure: {failure:,d}")
            logger.info(f"  Unchanged: {unchanged:,d}")
            
            if stats.get('errors', 0) > 0:
                logger.info(f"  Errors: {stats.get('errors', 0):,d}")


class TransformerFactory:
    """Factory for creating transformers based on configuration."""
    
    # Registry of transformer types
    _transformers: Dict[str, type] = {}
    
    @classmethod
    def register(cls, transformer_type: str) -> Callable[[type], type]:
        """Decorator to register a transformer class."""
        def decorator(transformer_class: type) -> type:
            cls._transformers[transformer_type] = transformer_class
            return transformer_class
        return decorator
    
    @classmethod
    def create(cls, transformer_type: str, config: Dict[str, Any]) -> Optional[Transformer]:
        """Create a transformer instance based on type and configuration."""
        transformer_class = cls._transformers.get(transformer_type)
        if not transformer_class:
            logger.warning(f"Unknown transformer type: {transformer_type}")
            return None
        try:
            return transformer_class(config)
        except Exception as e:
            logger.error(f"Error creating transformer {transformer_type}: {e}")
            return None
    
    @classmethod
    def get_available_transformers(cls) -> List[str]:
        """Get list of all registered transformer types."""
        return list(cls._transformers.keys())


class TransformationOperation:
    """Represents a single transformation operation with configuration."""
    
    def __init__(self, operation_type: str, config: Dict[str, Any]):
        """Initialize transformation operation."""
        self.operation_type = operation_type
        self.config = config
        self.transformer: Optional[Transformer] = None
        
    def initialize(self) -> bool:
        """Initialize the transformer for this operation."""
        self.transformer = TransformerFactory.create(self.operation_type, self.config)
        return self.transformer is not None
    
    def apply(self, value: Any, field_name: Optional[str] = None) -> TransformationResult:
        """Apply the transformation operation to a value."""
        if not self.transformer:
            if not self.initialize():
                return TransformationResult.failure(value, f"Failed to initialize transformer: {self.operation_type}")
        
        return self.transformer.transform(value, field_name)


class TransformationPipeline:
    """Pipeline for applying multiple transformations in sequence."""
    
    def __init__(self, operations: List[Dict[str, Any]]):
        """Initialize transformation pipeline with operations config."""
        self.operations: List[TransformationOperation] = []
        self.stats: Dict[str, int] = defaultdict(int)
        
        # Create operations from config
        for op_config in operations:
            op_type = op_config.get('type')
            if not op_type:
                logger.warning("Transformation operation missing 'type' field")
                continue
            
            operation = TransformationOperation(op_type, op_config)
            if operation.initialize():
                self.operations.append(operation)
            else:
                logger.warning(f"Failed to initialize transformer: {op_type}")
    
    def transform(self, value: Any, field_name: Optional[str] = None) -> TransformationResult:
        """Apply all transformation operations in sequence."""
        self.stats['total'] += 1
        
        if not self.operations:
            self.stats['unchanged'] += 1
            return TransformationResult.unchanged(value)
        
        current_value = value
        intermediate_results = []
        
        # Apply transformations in sequence
        for operation in self.operations:
            result = operation.apply(current_value, field_name)
            intermediate_results.append(result)
            
            if result.has_errors:
                # Stop pipeline on error
                self.stats['failure'] += 1
                self.stats['errors'] += len(result.errors)
                break
            
            if result.transformed:
                # Use transformed value for next operation
                current_value = result.value
        
        # Determine final result
        if not intermediate_results:
            self.stats['unchanged'] += 1
            return TransformationResult.unchanged(value)
        
        final_result = intermediate_results[-1]
        
        # Update stats
        if final_result.success:
            self.stats['success'] += 1
        elif final_result.has_errors:
            self.stats['failure'] += 1
            self.stats['errors'] += len(final_result.errors)
        elif not final_result.transformed:
            self.stats['unchanged'] += 1
        
        return final_result
    
    def get_stats(self) -> Dict[str, int]:
        """Get transformation pipeline statistics."""
        return dict(self.stats)
    
    def log_stats(self) -> None:
        """Log transformation pipeline statistics."""
        stats = self.get_stats()
        total = stats.get('total', 0)
        if total > 0:
            success = stats.get('success', 0)
            failure = stats.get('failure', 0)
            unchanged = stats.get('unchanged', 0)
            success_rate = (success / total) * 100 if total > 0 else 0
            
            logger.info("Transformation Pipeline Statistics:")
            logger.info(f"  Operations: {len(self.operations)}")
            logger.info(f"  Total processed: {total:,d}")
            logger.info(f"  Success: {success:,d} ({success_rate:.1f}%)")
            logger.info(f"  Failure: {failure:,d}")
            logger.info(f"  Unchanged: {unchanged:,d}")
            
            if stats.get('errors', 0) > 0:
                logger.info(f"  Total errors: {stats.get('errors', 0):,d}")


#==============================================================================
# Standard Transformer Implementations - String Transformers
#==============================================================================

@TransformerFactory.register("trim")
class TrimTransformer(Transformer[str, str]):
    """Transformer that trims whitespace from strings."""
    
    def transform(self, value: Any, field_name: Optional[str] = None) -> TransformationResult[str, str]:
        """Trim whitespace from string value."""
        self.stats['total'] += 1
        
        if value is None:
            self.stats['unchanged'] += 1
            return TransformationResult.unchanged(value)
            
        try:
            str_value = str(value)
            trimmed = str_value.strip()
            
            if trimmed == str_value:
                self.stats['unchanged'] += 1
                return TransformationResult.unchanged(str_value)
                
            self.stats['success'] += 1
            return TransformationResult.success_result(str_value, trimmed)
            
        except Exception as e:
            self.stats['failure'] += 1
            error_msg = f"Error trimming value: {str(e)}"
            self.transformation_errors.append(error_msg)
            return TransformationResult.failure(value, error_msg)
    
    def _validate_config(self) -> None:
        """Validate transformer configuration."""
        # No specific config needed for trim
        pass


@TransformerFactory.register("uppercase")
class UppercaseTransformer(Transformer[str, str]):
    """Transformer that converts strings to uppercase."""
    
    def transform(self, value: Any, field_name: Optional[str] = None) -> TransformationResult[str, str]:
        """Convert string to uppercase."""
        self.stats['total'] += 1
        
        if value is None:
            self.stats['unchanged'] += 1
            return TransformationResult.unchanged(value)
            
        try:
            str_value = str(value)
            upper = str_value.upper()
            
            if upper == str_value:
                self.stats['unchanged'] += 1
                return TransformationResult.unchanged(str_value)
                
            self.stats['success'] += 1
            return TransformationResult.success_result(str_value, upper)
            
        except Exception as e:
            self.stats['failure'] += 1
            error_msg = f"Error converting to uppercase: {str(e)}"
            self.transformation_errors.append(error_msg)
            return TransformationResult.failure(value, error_msg)
    
    def _validate_config(self) -> None:
        """Validate transformer configuration."""
        # No specific config needed for uppercase
        pass


@TransformerFactory.register("lowercase")
class LowercaseTransformer(Transformer[str, str]):
    """Transformer that converts strings to lowercase."""
    
    def transform(self, value: Any, field_name: Optional[str] = None) -> TransformationResult[str, str]:
        """Convert string to lowercase."""
        self.stats['total'] += 1
        
        if value is None:
            self.stats['unchanged'] += 1
            return TransformationResult.unchanged(value)
            
        try:
            str_value = str(value)
            lower = str_value.lower()
            
            if lower == str_value:
                self.stats['unchanged'] += 1
                return TransformationResult.unchanged(str_value)
                
            self.stats['success'] += 1
            return TransformationResult.success_result(str_value, lower)
            
        except Exception as e:
            self.stats['failure'] += 1
            error_msg = f"Error converting to lowercase: {str(e)}"
            self.transformation_errors.append(error_msg)
            return TransformationResult.failure(value, error_msg)
    
    def _validate_config(self) -> None:
        """Validate transformer configuration."""
        # No specific config needed for lowercase
        pass


@TransformerFactory.register("strip_characters")
class StripCharactersTransformer(Transformer[str, str]):
    """Transformer that strips specific characters from strings."""
    
    def transform(self, value: Any, field_name: Optional[str] = None) -> TransformationResult[str, str]:
        """Remove specified characters from string."""
        self.stats['total'] += 1
        
        if value is None:
            self.stats['unchanged'] += 1
            return TransformationResult.unchanged(value)
            
        try:
            str_value = str(value)
            characters = self.config.get('characters', '')
            
            if not characters:
                self.stats['unchanged'] += 1
                return TransformationResult.unchanged(str_value)
            
            # Create regex pattern to match any of the characters
            pattern = re.compile(f'[{re.escape(characters)}]')
            result = pattern.sub('', str_value)
            
            if result == str_value:
                self.stats['unchanged'] += 1
                return TransformationResult.unchanged(str_value)
                
            self.stats['success'] += 1
            return TransformationResult.success_result(str_value, result)
            
        except Exception as e:
            self.stats['failure'] += 1
            error_msg = f"Error stripping characters: {str(e)}"
            self.transformation_errors.append(error_msg)
            return TransformationResult.failure(value, error_msg)
    
    def _validate_config(self) -> None:
        """Validate transformer configuration."""
        if 'characters' not in self.config:
            raise ValueError("StripCharactersTransformer requires 'characters' configuration")


@TransformerFactory.register("truncate")
class TruncateTransformer(Transformer[str, str]):
    """Transformer that truncates strings to a maximum length."""
    
    def transform(self, value: Any, field_name: Optional[str] = None) -> TransformationResult[str, str]:
        """Truncate string to maximum length."""
        self.stats['total'] += 1
        
        if value is None:
            self.stats['unchanged'] += 1
            return TransformationResult.unchanged(value)
            
        try:
            str_value = str(value)
            max_length = self.config.get('max_length', 255)
            
            if len(str_value) <= max_length:
                self.stats['unchanged'] += 1
                return TransformationResult.unchanged(str_value)
                
            result = str_value[:max_length]
            self.stats['success'] += 1
            
            # Add metadata about truncation
            result_obj = TransformationResult.success_result(str_value, result)
            result_obj.add_metadata('truncated', True)
            result_obj.add_metadata('original_length', len(str_value))
            result_obj.add_metadata('truncated_length', max_length)
            result_obj.add_message(f"Value truncated from {len(str_value)} to {max_length} characters")
            
            return result_obj
            
        except Exception as e:
            self.stats['failure'] += 1
            error_msg = f"Error truncating value: {str(e)}"
            self.transformation_errors.append(error_msg)
            return TransformationResult.failure(value, error_msg)
    
    def _validate_config(self) -> None:
        """Validate transformer configuration."""
        if 'max_length' in self.config and not isinstance(self.config['max_length'], int):
            raise ValueError("'max_length' must be an integer")
            
        if 'max_length' in self.config and self.config['max_length'] <= 0:
            raise ValueError("'max_length' must be positive")


@TransformerFactory.register("pad_left")
class PadLeftTransformer(Transformer[str, str]):
    """Transformer that pads strings on the left with a specified character."""
    
    def transform(self, value: Any, field_name: Optional[str] = None) -> TransformationResult[str, str]:
        """Pad string on left to specified length."""
        self.stats['total'] += 1
        
        if value is None:
            self.stats['unchanged'] += 1
            return TransformationResult.unchanged(value)
            
        try:
            str_value = str(value)
            length = self.config.get('length', 1)
            character = self.config.get('character', '0')
            
            if len(character) != 1:
                error_msg = "Pad character must be a single character"
                self.stats['failure'] += 1
                self.transformation_errors.append(error_msg)
                return TransformationResult.failure(str_value, error_msg)
                
            if len(str_value) >= length:
                self.stats['unchanged'] += 1
                return TransformationResult.unchanged(str_value)
                
            result = str_value.rjust(length, character)
            self.stats['success'] += 1
            return TransformationResult.success_result(str_value, result)
            
        except Exception as e:
            self.stats['failure'] += 1
            error_msg = f"Error padding value: {str(e)}"
            self.transformation_errors.append(error_msg)
            return TransformationResult.failure(value, error_msg)
    
    def _validate_config(self) -> None:
        """Validate transformer configuration."""
        if 'length' in self.config and not isinstance(self.config['length'], int):
            raise ValueError("'length' must be an integer")
            
        if 'length' in self.config and self.config['length'] <= 0:
            raise ValueError("'length' must be positive")
            
        if 'character' in self.config and len(self.config['character']) != 1:
            raise ValueError("'character' must be a single character")


@TransformerFactory.register("extract_pattern")
class ExtractPatternTransformer(Transformer[str, str]):
    """Transformer that extracts content matching a pattern from strings."""
    
    def transform(self, value: Any, field_name: Optional[str] = None) -> TransformationResult[str, str]:
        """Extract pattern match from string."""
        self.stats['total'] += 1
        
        if value is None:
            self.stats['unchanged'] += 1
            return TransformationResult.unchanged(value)
            
        try:
            str_value = str(value)
            pattern = self.config.get('pattern', '')
            
            if not pattern:
                self.stats['unchanged'] += 1
                return TransformationResult.unchanged(str_value)
                
            matches = re.search(pattern, str_value)
            if not matches:
                self.stats['unchanged'] += 1
                return TransformationResult.unchanged(str_value)
                
            result = matches.group(0)
            
            if result == str_value:
                self.stats['unchanged'] += 1
                return TransformationResult.unchanged(str_value)
                
            self.stats['success'] += 1
            return TransformationResult.success_result(str_value, result)
            
        except Exception as e:
            self.stats['failure'] += 1
            error_msg = f"Error extracting pattern: {str(e)}"
            self.transformation_errors.append(error_msg)
            return TransformationResult.failure(value, error_msg)
    
    def _validate_config(self) -> None:
        """Validate transformer configuration."""
        if 'pattern' not in self.config:
            raise ValueError("ExtractPatternTransformer requires 'pattern' configuration")
            
        try:
            re.compile(self.config['pattern'])
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")


@TransformerFactory.register("map_values")
class MapValuesTransformer(Transformer[str, str]):
    """Transformer that maps input values to output values using a mapping dictionary."""
    
    def transform(self, value: Any, field_name: Optional[str] = None) -> TransformationResult[str, str]:
        """Map input value to output value using mapping."""
        self.stats['total'] += 1
        
        if value is None:
            self.stats['unchanged'] += 1
            return TransformationResult.unchanged(value)
            
        try:
            str_value = str(value)
            mapping = self.config.get('mapping', {})
            
            if not mapping:
                self.stats['unchanged'] += 1
                return TransformationResult.unchanged(str_value)
                
            if str_value in mapping:
                result = mapping[str_value]
                self.stats['success'] += 1
                return TransformationResult.success_result(str_value, result)
                
            # Check case-insensitive mapping if specified
            if self.config.get('case_insensitive', False):
                for k, v in mapping.items():
                    if str(k).lower() == str_value.lower():
                        self.stats['success'] += 1
                        return TransformationResult.success_result(str_value, v)
                        
            # Use default value if specified
            if 'default' in self.config:
                self.stats['success'] += 1
                return TransformationResult.success_result(str_value, self.config['default'])
                
            self.stats['unchanged'] += 1
            return TransformationResult.unchanged(str_value)
            
        except Exception as e:
            self.stats['failure'] += 1
            error_msg = f"Error mapping value: {str(e)}"
            self.transformation_errors.append(error_msg)
            return TransformationResult.failure(value, error_msg)
    
    def _validate_config(self) -> None:
        """Validate transformer configuration."""
        if 'mapping' not in self.config or not isinstance(self.config['mapping'], dict):
            raise ValueError("MapValuesTransformer requires 'mapping' configuration as a dictionary")
            
        if 'case_insensitive' in self.config and not isinstance(self.config['case_insensitive'], bool):
            raise ValueError("'case_insensitive' must be a boolean")


#==============================================================================
# Standard Transformer Implementations - Numeric Transformers
#==============================================================================

@TransformerFactory.register("convert_to_decimal")
class ConvertToDecimalTransformer(Transformer[str, Decimal]):
    """Transformer that converts strings to Decimal values."""
    
    def transform(self, value: Any, field_name: Optional[str] = None) -> TransformationResult[str, Union[Decimal, str]]:
        """Convert string to Decimal."""
        self.stats['total'] += 1
        
        if value is None:
            self.stats['unchanged'] += 1
            return TransformationResult.unchanged(value)
            
        try:
            str_value = str(value).strip()
            if not str_value:
                self.stats['unchanged'] += 1
                return TransformationResult.unchanged(str_value)
                
            # Strip any characters specified in the config
            if 'strip_characters' in self.config:
                chars = self.config['strip_characters']
                pattern = re.compile(f'[{re.escape(chars)}]')
                str_value = pattern.sub('', str_value)
                
            # Handle percentages if needed
            is_percentage = False
            if str_value.endswith('%'):
                is_percentage = True
                str_value = str_value[:-1]
                
            # Convert to decimal
            decimal_value = Decimal(str_value)
            
            # Handle percentage conversion if requested
            if is_percentage and self.config.get('convert_percentage', False):
                decimal_value = decimal_value / Decimal('100')
                
            self.stats['success'] += 1
            result = TransformationResult.success_result(value, decimal_value)
            result.add_metadata('is_percentage', is_percentage)
            return result
            
        except (InvalidOperation, ValueError) as e:
            self.stats['failure'] += 1
            error_msg = f"Error converting to decimal: {str(e)}"
            self.transformation_errors.append(error_msg)
            return TransformationResult.failure(value, error_msg)
    
    def _validate_config(self) -> None:
        """Validate transformer configuration."""
        if 'strip_characters' in self.config and not isinstance(self.config['strip_characters'], str):
            raise ValueError("'strip_characters' must be a string")
            
        if 'convert_percentage' in self.config and not isinstance(self.config['convert_percentage'], bool):
            raise ValueError("'convert_percentage' must be a boolean")


@TransformerFactory.register("convert_to_integer")
class ConvertToIntegerTransformer(Transformer[str, int]):
    """Transformer that converts strings to integer values."""
    
    def transform(self, value: Any, field_name: Optional[str] = None) -> TransformationResult[str, Union[int, str]]:
        """Convert string to integer."""
        self.stats['total'] += 1
        
        if value is None:
            self.stats['unchanged'] += 1
            return TransformationResult.unchanged(value)
            
        try:
            str_value = str(value).strip()
            if not str_value:
                self.stats['unchanged'] += 1
                return TransformationResult.unchanged(str_value)
                
            # Strip any characters specified in the config
            if 'strip_characters' in self.config:
                chars = self.config['strip_characters']
                pattern = re.compile(f'[{re.escape(chars)}]')
                str_value = pattern.sub('', str_value)
                
            # Handle floating point values if needed
            if '.' in str_value:
                if self.config.get('truncate', True):
                    # Just truncate the decimal part
                    str_value = str_value.split('.')[0]
                else:
                    # Use proper rounding
                    decimal_value = Decimal(str_value)
                    str_value = str(int(decimal_value.to_integral_exact(ROUND_HALF_UP)))
            
            # Convert to integer
            int_value = int(str_value)
            
            self.stats['success'] += 1
            return TransformationResult.success_result(value, int_value)
            
        except (ValueError, InvalidOperation) as e:
            self.stats['failure'] += 1
            error_msg = f"Error converting to integer: {str(e)}"
            self.transformation_errors.append(error_msg)
            return TransformationResult.failure(value, error_msg)
    
    def _validate_config(self) -> None:
        """Validate transformer configuration."""
        if 'strip_characters' in self.config and not isinstance(self.config['strip_characters'], str):
            raise ValueError("'strip_characters' must be a string")
            
        if 'truncate' in self.config and not isinstance(self.config['truncate'], bool):
            raise ValueError("'truncate' must be a boolean")


@TransformerFactory.register("round_number")
class RoundNumberTransformer(Transformer[Union[str, float, Decimal], Union[Decimal, float]]):
    """Transformer that rounds numeric values to a specified precision."""
    
    def transform(self, value: Any, field_name: Optional[str] = None) -> TransformationResult:
        """Round numeric value to specified precision."""
        self.stats['total'] += 1
        
        if value is None:
            self.stats['unchanged'] += 1
            return TransformationResult.unchanged(value)
            
        try:
            # Convert to decimal for consistent rounding
            if isinstance(value, Decimal):
                decimal_value = value
            elif isinstance(value, (int, float)):
                decimal_value = Decimal(str(value))
            else:
                decimal_value = Decimal(str(value).strip())
                
            # Get rounding configuration
            precision = self.config.get('precision', 2)
            rounding = self.config.get('rounding', 'ROUND_HALF_UP')
            
            # Apply rounding
            rounded_value = round(decimal_value, precision)
            
            # Convert back to float if requested
            if self.config.get('output_float', False):
                rounded_value = float(rounded_value)
                
            if rounded_value == value:
                self.stats['unchanged'] += 1
                return TransformationResult.unchanged(value)
                
            self.stats['success'] += 1
            result = TransformationResult.success_result(value, rounded_value)
            result.add_metadata('precision', precision)
            result.add_metadata('original_value', value)
            return result
            
        except (ValueError, InvalidOperation) as e:
            self.stats['failure'] += 1
            error_msg = f"Error rounding value: {str(e)}"
            self.transformation_errors.append(error_msg)
            return TransformationResult.failure(value, error_msg)
    
    def _validate_config(self) -> None:
        """Validate transformer configuration."""
        if 'precision' in self.config and not isinstance(self.config['precision'], int):
            raise ValueError("'precision' must be an integer")
            
        if 'output_float' in self.config and not isinstance(self.config['output_float'], bool):
            raise ValueError("'output_float' must be a boolean")


@TransformerFactory.register("format_number")
class FormatNumberTransformer(Transformer[Union[str, int, float, Decimal], str]):
    """Transformer that formats numeric values into formatted strings."""
    
    def transform(self, value: Any, field_name: Optional[str] = None) -> TransformationResult[Any, str]:
        """Format numeric value as string with specified formatting."""
        self.stats['total'] += 1
        
        if value is None:
            self.stats['unchanged'] += 1
            return TransformationResult.unchanged(value)
            
        try:
            # Convert to decimal for consistent formatting
            if isinstance(value, Decimal):
                decimal_value = value
            elif isinstance(value, (int, float)):
                decimal_value = Decimal(str(value))
            else:
                decimal_value = Decimal(str(value).strip())
                
            # Get formatting configuration
            format_str = self.config.get('format', '{:,.2f}')
            
            # Special case for handling decimal places
            decimal_places = self.config.get('decimal_places')
            if decimal_places is not None:
                # Round to specified decimal places
                decimal_value = round(decimal_value, decimal_places)
                
                # Create format string if not using Python format string
                if not format_str.startswith('{'):
                    format_str = f"{{:,.{decimal_places}f}}"
            
            # Apply formatting - support both Python format strings and format specifiers
            if format_str.startswith('{'):
                formatted_value = format_str.format(decimal_value)
            else:
                formatted_value = format(decimal_value, format_str)
                
            # Add currency symbol if specified
            currency_symbol = self.config.get('currency_symbol')
            if currency_symbol:
                currency_position = self.config.get('currency_position', 'prefix')
                if currency_position == 'prefix':
                    formatted_value = f"{currency_symbol}{formatted_value}"
                else:
                    formatted_value = f"{formatted_value}{currency_symbol}"
            
            # Add percentage symbol if specified
            if self.config.get('percentage', False):
                formatted_value = f"{formatted_value}%"
                
            self.stats['success'] += 1
            return TransformationResult.success_result(value, formatted_value)
            
        except (ValueError, InvalidOperation) as e:
            self.stats['failure'] += 1
            error_msg = f"Error formatting number: {str(e)}"
            self.transformation_errors.append(error_msg)
            return TransformationResult.failure(value, error_msg)
    
    def _validate_config(self) -> None:
        """Validate transformer configuration."""
        if 'decimal_places' in self.config and not isinstance(self.config['decimal_places'], int):
            raise ValueError("'decimal_places' must be an integer")
            
        if 'percentage' in self.config and not isinstance(self.config['percentage'], bool):
            raise ValueError("'percentage' must be a boolean")


#==============================================================================
# Standard Transformer Implementations - Date Transformers
#==============================================================================

@TransformerFactory.register("normalize_date")
class NormalizeDateTransformer(Transformer[str, str]):
    """Transformer that normalizes dates to a standard format using dateutil.
    
    This transformer takes date strings in various formats and normalizes them
    to a consistent output format. It can use explicit input formats or
    leverage dateutil's flexible parser for automatic format detection.
    
    Configuration options:
    - input_formats: List of format strings to try when parsing input
    - output_format: Format string for output (default: '%Y-%m-%d')
    - dayfirst: Whether to interpret ambiguous dates as day/month/year (default: False)
    - yearfirst: Whether to interpret ambiguous dates as year/month/day (default: False)
    - fuzzy: Whether to allow fuzzy parsing (ignore unknown tokens) (default: False)
    """
    
    def transform(self, value: Any, field_name: Optional[str] = None) -> TransformationResult[str, str]:
        """Normalize date string to a specified output format."""
        self.stats['total'] += 1
        
        if value is None or value == '':
            self.stats['unchanged'] += 1
            return TransformationResult.unchanged(value)
            
        try:
            str_value = str(value).strip()
            
            # Get configured formats
            input_formats = self.config.get('input_formats', [])
            output_format = self.config.get('output_format', '%Y-%m-%d')
            
            # First try parsing with explicit input formats if provided
            parsed_date = None
            if input_formats:
                for fmt in input_formats:
                    try:
                        parsed_date = datetime.strptime(str_value, fmt)
                        break
                    except ValueError:
                        continue
            
            # If explicit formats failed or weren't provided, use dateutil's flexible parser
            if parsed_date is None:
                if not DATEUTIL_AVAILABLE:
                    self.stats['failure'] += 1
                    error_msg = "Date parsing requires python-dateutil package"
                    self.transformation_errors.append(error_msg)
                    return TransformationResult.failure(str_value, error_msg)
                
                try:
                    parsed_date = parser.parse(
                        str_value,
                        dayfirst=self.config.get('dayfirst', False),
                        yearfirst=self.config.get('yearfirst', False),
                        fuzzy=self.config.get('fuzzy', False)
                    )
                except ParserError as e:
                    self.stats['failure'] += 1
                    error_msg = f"Unable to parse date: {str(e)}"
                    self.transformation_errors.append(error_msg)
                    return TransformationResult.failure(str_value, error_msg)
            
            # Format the date according to output format
            formatted_date = parsed_date.strftime(output_format)
            
            # Return unchanged if the formatted date is the same as input
            if formatted_date == str_value:
                self.stats['unchanged'] += 1
                return TransformationResult.unchanged(str_value)
                
            self.stats['success'] += 1
            result = TransformationResult.success_result(str_value, formatted_date)
            result.add_metadata('parsed_date', parsed_date.isoformat())
            result.add_metadata('input_value', str_value)
            result.add_metadata('format_applied', output_format)
            return result
            
        except Exception as e:
            self.stats['failure'] += 1
            error_msg = f"Error normalizing date: {str(e)}"
            self.transformation_errors.append(error_msg)
            return TransformationResult.failure(value, error_msg)
    
    def _validate_config(self) -> None:
        """Validate transformer configuration."""
        if 'output_format' in self.config and not isinstance(self.config['output_format'], str):
            raise ValueError("'output_format' must be a string")
            
        if 'input_formats' in self.config:
            if not isinstance(self.config['input_formats'], list):
                raise ValueError("'input_formats' must be a list of format strings")
            for fmt in self.config['input_formats']:
                if not isinstance(fmt, str):
                    raise ValueError("Each input format must be a string")
                # Validate that format strings are valid
                try:
                    # Use a sample date to validate the format string
                    datetime(2023, 1, 1).strftime(fmt)
                except ValueError as e:
                    raise ValueError(f"Invalid date format string '{fmt}': {str(e)}")
                    
        for param in ['dayfirst', 'yearfirst', 'fuzzy']:
            if param in self.config and not isinstance(self.config[param], bool):
                raise ValueError(f"'{param}' must be a boolean")


@TransformerFactory.register("strip_time")
class StripTimeTransformer(Transformer[str, str]):
    """Transformer that removes time components from datetime values.
    
    This transformer extracts just the date part from a datetime string,
    discarding any time information.
    
    Configuration options:
    - output_format: Format string for output date (default: '%Y-%m-%d')
    """
    
    def transform(self, value: Any, field_name: Optional[str] = None) -> TransformationResult[str, str]:
        """Strip time component from a datetime string."""
        self.stats['total'] += 1
        
        if value is None or value == '':
            self.stats['unchanged'] += 1
            return TransformationResult.unchanged(value)
            
        try:
            str_value = str(value).strip()
            
            # Check if this looks like it contains a time component
            has_time_component = ' ' in str_value or 'T' in str_value or ':' in str_value
            if not has_time_component:
                self.stats['unchanged'] += 1
                return TransformationResult.unchanged(str_value)
            
            # Get output format (defaults to ISO date)
            output_format = self.config.get('output_format', '%Y-%m-%d')
            
            # Parse the date
            parsed_date = None
            
            # First try simple datetime parsing
            try:
                # Try ISO format first
                if 'T' in str_value:
                    formats_to_try = ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f']
                    for fmt in formats_to_try:
                        try:
                            parsed_date = datetime.strptime(str_value, fmt)
                            break
                        except ValueError:
                            continue
                
                # Try common datetime formats
                if parsed_date is None:
                    formats_to_try = ['%Y-%m-%d %H:%M:%S', '%m/%d/%Y %H:%M:%S', '%d/%m/%Y %H:%M:%S']
                    for fmt in formats_to_try:
                        try:
                            parsed_date = datetime.strptime(str_value, fmt)
                            break
                        except ValueError:
                            continue
            except Exception:
                # Ignore errors in initial parsing attempts
                pass
            
            # If standard parsing failed, use dateutil
            if parsed_date is None:
                if not DATEUTIL_AVAILABLE:
                    self.stats['failure'] += 1
                    error_msg = "Date parsing requires python-dateutil package"
                    self.transformation_errors.append(error_msg)
                    return TransformationResult.failure(str_value, error_msg)
                
                try:
                    parsed_date = parser.parse(str_value)
                except ParserError as e:
                    self.stats['failure'] += 1
                    error_msg = f"Unable to parse datetime: {str(e)}"
                    self.transformation_errors.append(error_msg)
                    return TransformationResult.failure(str_value, error_msg)
            
            # Format with just date component
            date_only = parsed_date.strftime(output_format)
            
            # Return unchanged if output is the same as input (already date-only)
            if date_only == str_value:
                self.stats['unchanged'] += 1
                return TransformationResult.unchanged(str_value)
                
            self.stats['success'] += 1
            result = TransformationResult.success_result(str_value, date_only)
            result.add_metadata('had_time', True)
            result.add_metadata('original_datetime', str_value)
            return result
            
        except Exception as e:
            self.stats['failure'] += 1
            error_msg = f"Error stripping time component: {str(e)}"
            self.transformation_errors.append(error_msg)
            return TransformationResult.failure(value, error_msg)
    
    def _validate_config(self) -> None:
        """Validate transformer configuration."""
        if 'output_format' in self.config:
            if not isinstance(self.config['output_format'], str):
                raise ValueError("'output_format' must be a string")
            
            # Validate output format is a valid date format string
            try:
                # Use a sample date to validate the format string
                datetime(2023, 1, 1).strftime(self.config['output_format'])
            except ValueError as e:
                raise ValueError(f"Invalid date format string '{self.config['output_format']}': {str(e)}")


@TransformerFactory.register("date_format")
class DateFormatTransformer(Transformer[str, str]):
    """Transformer that formats date values according to specified format.
    
    This transformer takes dates in a known format and outputs them in a
    different format. It can use either explicit input formats or dateutil's
    flexible parser for input parsing.
    
    Configuration options:
    - input_format: Format string for input parsing (optional)
    - output_format: Format string for output (default: '%Y-%m-%d')
    - dayfirst: Whether to interpret ambiguous dates as day/month/year (default: False)
    - yearfirst: Whether to interpret ambiguous dates as year/month/day (default: False)
    - locale: Locale to use for formatting (optional)
    - locale_format: Format string using locale-specific names (optional)
    """
    
    def transform(self, value: Any, field_name: Optional[str] = None) -> TransformationResult[str, str]:
        """Format date value according to specified format."""
        self.stats['total'] += 1
        
        if value is None or value == '':
            self.stats['unchanged'] += 1
            return TransformationResult.unchanged(value)
            
        try:
            str_value = str(value).strip()
            
            # Get configured formats
            input_format = self.config.get('input_format')
            output_format = self.config.get('output_format', '%Y-%m-%d')
            
            # Parse the date - either using specific input format or flexible parsing
            if input_format:
                try:
                    parsed_date = datetime.strptime(str_value, input_format)
                except ValueError as e:
                    self.stats['failure'] += 1
                    error_msg = f"Failed to parse date using format '{input_format}': {str(e)}"
                    self.transformation_errors.append(error_msg)
                    return TransformationResult.failure(str_value, error_msg)
            else:
                if not DATEUTIL_AVAILABLE:
                    self.stats['failure'] += 1
                    error_msg = "Flexible date parsing requires python-dateutil package"
                    self.transformation_errors.append(error_msg)
                    return TransformationResult.failure(str_value, error_msg)
                
                try:
                    parsed_date = parser.parse(
                        str_value,
                        dayfirst=self.config.get('dayfirst', False),
                        yearfirst=self.config.get('yearfirst', False)
                    )
                except ParserError as e:
                    self.stats['failure'] += 1
                    error_msg = f"Failed to parse date: {str(e)}"
                    self.transformation_errors.append(error_msg)
                    return TransformationResult.failure(str_value, error_msg)
            
            # Format the date according to output format
            formatted_date = parsed_date.strftime(output_format)
            
            # Apply locale-specific formatting if requested
            if self.config.get('locale_format'):
                try:
                    import locale
                    if self.config.get('locale'):
                        locale.setlocale(locale.LC_TIME, self.config['locale'])
                    formatted_date = parsed_date.strftime(self.config['locale_format'])
                except (ImportError, locale.Error) as e:
                    # Fall back to standard format if locale formatting fails
                    logger.warning(f"Locale formatting failed: {e}")
            
            # Return unchanged if the formatted date is the same as input
            if formatted_date == str_value:
                self.stats['unchanged'] += 1
                return TransformationResult.unchanged(str_value)
                
            self.stats['success'] += 1
            result = TransformationResult.success_result(str_value, formatted_date)
            result.add_metadata('input_value', str_value)
            result.add_metadata('output_format', output_format)
            return result
            
        except Exception as e:
            self.stats['failure'] += 1
            error_msg = f"Error formatting date: {str(e)}"
            self.transformation_errors.append(error_msg)
            return TransformationResult.failure(value, error_msg)
    
    def _validate_config(self) -> None:
        """Validate transformer configuration."""
        if 'output_format' in self.config and not isinstance(self.config['output_format'], str):
            raise ValueError("'output_format' must be a string")
            
        # Test output format if provided
        if 'output_format' in self.config:
            try:
                datetime(2023, 1, 1).strftime(self.config['output_format'])
            except ValueError as e:
                raise ValueError(f"Invalid output format string '{self.config['output_format']}': {str(e)}")
                
        # Test input format if provided
        if 'input_format' in self.config:
            if not isinstance(self.config['input_format'], str):
                raise ValueError("'input_format' must be a string")
            try:
                # Use a sample date to validate the format string
                datetime(2023, 1, 1).strftime(self.config['input_format'])
            except ValueError as e:
                raise ValueError(f"Invalid input format string '{self.config['input_format']}': {str(e)}")
                
        for param in ['dayfirst', 'yearfirst']:
            if param in self.config and not isinstance(self.config[param], bool):
                raise ValueError(f"'{param}' must be a boolean")


@TransformerFactory.register("derive_fields_from_date")
class DeriveFieldsFromDateTransformer(Transformer[str, Dict[str, Any]]):
    """Transformer that extracts components from a date into a dictionary of fields.
    
    This transformer takes a date string and returns a dictionary containing various
    date components such as year, month, day, quarter, fiscal year, etc.
    
    Configuration options:
    - components: List of components to extract (default: ['year', 'month', 'day'])
    - fiscal_year_start_month: Month when fiscal year starts (default: 10 for October)
    - input_format: Format string for input parsing (optional)
    
    Available components:
    - year: Calendar year (e.g., 2023)
    - month: Calendar month (1-12)
    - day: Day of month (1-31)
    - quarter: Calendar quarter (1-4)
    - fiscal_year: Fiscal year based on fiscal_year_start_month
    - fiscal_quarter: Fiscal quarter (1-4)
    - day_of_year: Day of year (1-366)
    - week_of_year: ISO week number (1-53)
    - day_of_week: ISO day of week (1=Monday, 7=Sunday)
    - is_weekend: Boolean flag for weekend days (Saturday/Sunday)
    """
    
    def transform(self, value: Any, field_name: Optional[str] = None) -> TransformationResult[str, Dict[str, Any]]:
        """Extract date components as separate fields."""
        self.stats['total'] += 1
        
        if value is None or value == '':
            self.stats['unchanged'] += 1
            return TransformationResult.unchanged(value)
            
        try:
            str_value = str(value).strip()
            
            # Get configuration
            components = self.config.get('components', ['year', 'month', 'day'])
            fiscal_year_start_month = self.config.get('fiscal_year_start_month', 10)  # Default: October
            
            # Parse date
            parsed_date = None
            
            # Try to parse with specific format if provided
            if 'input_format' in self.config:
                try:
                    parsed_date = datetime.strptime(str_value, self.config['input_format'])
                except ValueError as e:
                    self.stats['failure'] += 1
                    error_msg = f"Failed to parse date using format '{self.config['input_format']}': {str(e)}"
                    self.transformation_errors.append(error_msg)
                    return TransformationResult.failure(str_value, error_msg)
            else:
                # Use DateUtil for flexible parsing
                if not DATEUTIL_AVAILABLE:
                    self.stats['failure'] += 1
                    error_msg = "Flexible date parsing requires python-dateutil package"
                    self.transformation_errors.append(error_msg)
                    return TransformationResult.failure(str_value, error_msg)
                
                try:
                    parsed_date = parser.parse(str_value)
                except ParserError as e:
                    self.stats['failure'] += 1
                    error_msg = f"Unable to parse date: {str(e)}"
                    self.transformation_errors.append(error_msg)
                    return TransformationResult.failure(str_value, error_msg)
            
            # Create a dictionary with requested components
            result = {}
            
            for component in components:
                if component == 'year':
                    result['year'] = parsed_date.year
                elif component == 'month':
                    result['month'] = parsed_date.month
                elif component == 'day':
                    result['day'] = parsed_date.day
                elif component == 'quarter':
                    # Calculate calendar quarter (1-4)
                    result['quarter'] = (parsed_date.month - 1) // 3 + 1
                elif component == 'fiscal_year':
                    # Calculate fiscal year based on fiscal_year_start_month
                    calendar_year = parsed_date.year
                    # If month is in new fiscal year, increment calendar year
                    if parsed_date.month >= fiscal_year_start_month:
                        result['fiscal_year'] = calendar_year + 1
                    else:
                        result['fiscal_year'] = calendar_year
                elif component == 'fiscal_quarter':
                    # Calculate fiscal quarter based on fiscal_year_start_month
                    month = parsed_date.month
                    # Adjust month to fiscal year (e.g., if fiscal year starts in October, October = month 1)
                    adjusted_month = (month - fiscal_year_start_month) % 12 + 1
                    # Calculate quarter from adjusted month
                    result['fiscal_quarter'] = (adjusted_month - 1) // 3 + 1
                elif component == 'day_of_year':
                    result['day_of_year'] = parsed_date.timetuple().tm_yday
                elif component == 'week_of_year':
                    # ISO week number (1-53)
                    result['week_of_year'] = parsed_date.isocalendar()[1]
                elif component == 'day_of_week':
                    # Day of week (1=Monday, 7=Sunday per ISO)
                    result['day_of_week'] = parsed_date.isoweekday()
                elif component == 'is_weekend':
                    # Is weekend if Saturday (6) or Sunday (7)
                    result['is_weekend'] = parsed_date.isoweekday() >= 6
            
            self.stats['success'] += 1
            result_obj = TransformationResult.success_result(str_value, result)
            result_obj.add_metadata('derived_components', list(result.keys()))
            result_obj.add_metadata('parsed_date', parsed_date.isoformat())
            return result_obj
            
        except Exception as e:
            self.stats['failure'] += 1
            error_msg = f"Error deriving fields from date: {str(e)}"
            self.transformation_errors.append(error_msg)
            return TransformationResult.failure(value, error_msg)
    
    def _validate_config(self) -> None:
        """Validate transformer configuration."""
        valid_components = [
            'year', 'month', 'day', 'quarter', 'fiscal_year',
            'fiscal_quarter', 'day_of_year', 'week_of_year',
            'day_of_week', 'is_weekend'
        ]
        
        if 'components' in self.config:
            if not isinstance(self.config['components'], list):
                raise ValueError("'components' must be a list of field names")
                
            for component in self.config['components']:
                if component not in valid_components:
                    raise ValueError(f"Invalid date component: '{component}'. Must be one of: {valid_components}")
                    
        if 'fiscal_year_start_month' in self.config:
            if not isinstance(self.config['fiscal_year_start_month'], int):
                raise ValueError("'fiscal_year_start_month' must be an integer")
            if not (1 <= self.config['fiscal_year_start_month'] <= 12):
                raise ValueError("'fiscal_year_start_month' must be between 1 and 12")


@TransformerFactory.register("derive_fiscal_year")
class DeriveFiscalYearTransformer(Transformer[str, int]):
    """Transformer that calculates fiscal year from a date string.
    
    This is a specialized transformer that extracts just the fiscal year from a date,
    based on the configured fiscal year start month.
    
    Configuration options:
    - fiscal_year_start_month: Month when fiscal year starts (default: 10 for October)
    - source_field: Field containing the date to derive from (optional)
    - input_format: Format string for input parsing (optional)
    """
    
    def transform(self, value: Any, field_name: Optional[str] = None) -> TransformationResult[str, int]:
        """Calculate fiscal year from date string."""
        self.stats['total'] += 1
        
        if value is None or value == '':
            self.stats['unchanged'] += 1
            return TransformationResult.unchanged(value)
            
        try:
            str_value = str(value).strip()
            
            # Get configuration
            fiscal_year_start_month = self.config.get('fiscal_year_start_month', 10)  # Default: October
            
            # Parse date using specific format if provided
            if 'input_format' in self.config:
                try:
                    parsed_date = datetime.strptime(str_value, self.config['input_format'])
                except ValueError as e:
                    self.stats['failure'] += 1
                    error_msg = f"Failed to parse date using format '{self.config['input_format']}': {str(e)}"
                    self.transformation_errors.append(error_msg)
                    return TransformationResult.failure(str_value, error_msg)
            else:
                # Use DateUtil for flexible parsing
                if not DATEUTIL_AVAILABLE:
                    self.stats['failure'] += 1
                    error_msg = "Flexible date parsing requires python-dateutil package"
                    self.transformation_errors.append(error_msg)
                    return TransformationResult.failure(str_value, error_msg)
                
                try:
                    parsed_date = parser.parse(str_value)
                except ParserError as e:
                    self.stats['failure'] += 1
                    error_msg = f"Unable to parse date: {str(e)}"
                    self.transformation_errors.append(error_msg)
                    return TransformationResult.failure(str_value, error_msg)
            
            # Calculate fiscal year based on fiscal_year_start_month
            calendar_year = parsed_date.year
            
            # If month is in new fiscal year, increment calendar year
            if parsed_date.month >= fiscal_year_start_month:
                fiscal_year = calendar_year + 1
            else:
                fiscal_year = calendar_year
            
            # Return fiscal year as integer
            self.stats['success'] += 1
            result = TransformationResult.success_result(str_value, fiscal_year)
            result.add_metadata('calendar_year', calendar_year)
            result.add_metadata('fiscal_year_start_month', fiscal_year_start_month)
            return result
            
        except Exception as e:
            self.stats['failure'] += 1
            error_msg = f"Error deriving fiscal year: {str(e)}"
            self.transformation_errors.append(error_msg)
            return TransformationResult.failure(value, error_msg)
    
    def _validate_config(self) -> None:
        """Validate transformer configuration."""
        if 'fiscal_year_start_month' in self.config:
            if not isinstance(self.config['fiscal_year_start_month'], int):
                raise ValueError("'fiscal_year_start_month' must be an integer")
            if not (1 <= self.config['fiscal_year_start_month'] <= 12):
                raise ValueError("'fiscal_year_start_month' must be between 1 and 12")
        
        # Validate input format if provided
        if 'input_format' in self.config:
            if not isinstance(self.config['input_format'], str):
                raise ValueError("'input_format' must be a string")
            try:
                # Use a sample date to validate the format string
                datetime(2023, 1, 1).strftime(self.config['input_format'])
            except ValueError as e:
                raise ValueError(f"Invalid input format string '{self.config['input_format']}': {str(e)}")