"""Data transformation operations and factory."""
from typing import Dict, Any, Optional, List, Callable, Type
from abc import ABC, abstractmethod
from datetime import datetime
import re
from decimal import Decimal, InvalidOperation

from .interfaces import ITransformerFactory
from .logging_config import get_logger

logger = get_logger(__name__)

class TransformError(Exception):
    """Error during data transformation."""
    pass

class BaseTransformer(ABC):
    """Base class for data transformers."""
    
    @abstractmethod
    def transform(self, value: Any) -> Any:
        """Transform input value."""
        pass

class DateTransformer(BaseTransformer):
    """Transforms date/time values."""
    
    def __init__(self, input_formats: List[str],
                 output_format: Optional[str] = None,
                 default: Optional[str] = None):
        """Initialize transformer."""
        self.input_formats = input_formats
        self.output_format = output_format
        self.default = default
        
    def transform(self, value: Any) -> Any:
        """Transform date value."""
        if value is None:
            return self.default
            
        if isinstance(value, datetime):
            dt = value
        else:
            dt = None
            for fmt in self.input_formats:
                try:
                    dt = datetime.strptime(str(value), fmt)
                    break
                except ValueError:
                    continue
                    
        if dt is None:
            return self.default
            
        return dt.strftime(self.output_format) if self.output_format else dt

class NumericTransformer(BaseTransformer):
    """Transforms numeric values."""
    
    def __init__(self, precision: Optional[int] = None,
                 decimal: bool = False,
                 default: Optional[Any] = None):
        """Initialize transformer."""
        self.precision = precision
        self.decimal = decimal
        self.default = default
        
    def transform(self, value: Any) -> Any:
        """Transform numeric value."""
        if value is None:
            return self.default
            
        try:
            if self.decimal:
                num = Decimal(str(value))
                if self.precision is not None:
                    return round(num, self.precision)
                return num
            else:
                num = float(str(value))
                if self.precision is not None:
                    return round(num, self.precision)
                return num
        except (ValueError, InvalidOperation):
            return self.default

class StringTransformer(BaseTransformer):
    """Transforms string values."""
    
    def __init__(self, strip: bool = True,
                 case: Optional[str] = None,
                 max_length: Optional[int] = None,
                 pattern: Optional[str] = None,
                 default: Optional[str] = None):
        """Initialize transformer."""
        self.strip = strip
        self.case = case
        self.max_length = max_length
        self.pattern = pattern
        self.default = default
        self._pattern_regex = re.compile(pattern) if pattern else None
        
    def transform(self, value: Any) -> Any:
        """Transform string value."""
        if value is None:
            return self.default
            
        result = str(value)
        
        if self.strip:
            result = result.strip()
            
        if self.case == 'upper':
            result = result.upper()
        elif self.case == 'lower':
            result = result.lower()
            
        if self.pattern and self._pattern_regex:
            match = self._pattern_regex.search(result)
            if match:
                result = match.group(0)
            else:
                return self.default
                
        if self.max_length and len(result) > self.max_length:
            result = result[:self.max_length]
            
        return result

class BooleanTransformer(BaseTransformer):
    """Transforms boolean values."""
    
    def __init__(self, true_values: Optional[List[str]] = None,
                 false_values: Optional[List[str]] = None,
                 default: Optional[bool] = None):
        """Initialize transformer."""
        self.true_values = set(v.lower() for v in (true_values or
                                                  ['true', 'yes', '1', 'y', 't']))
        self.false_values = set(v.lower() for v in (false_values or
                                                   ['false', 'no', '0', 'n', 'f']))
        self.default = default
        
    def transform(self, value: Any) -> Any:
        """Transform boolean value."""
        if value is None:
            return self.default
            
        if isinstance(value, bool):
            return value
            
        str_value = str(value).lower()
        if str_value in self.true_values:
            return True
        if str_value in self.false_values:
            return False
        return self.default

class ListTransformer(BaseTransformer):
    """Transforms list values."""
    
    def __init__(self, item_transformer: BaseTransformer,
                 separator: str = ',',
                 strip: bool = True,
                 default: Optional[List[Any]] = None):
        """Initialize transformer."""
        self.item_transformer = item_transformer
        self.separator = separator
        self.strip = strip
        self.default = default or []
        
    def transform(self, value: Any) -> Any:
        """Transform list value."""
        if value is None:
            return self.default
            
        if isinstance(value, str):
            items = value.split(self.separator)
        elif isinstance(value, (list, tuple)):
            items = value
        else:
            return self.default
            
        result = []
        for item in items:
            if self.strip and isinstance(item, str):
                item = item.strip()
            transformed = self.item_transformer.transform(item)
            if transformed is not None:
                result.append(transformed)
                
        return result

class MappingTransformer(BaseTransformer):
    """Transforms values using mapping."""
    
    def __init__(self, mapping: Dict[str, Any],
                 case_sensitive: bool = False,
                 default: Optional[Any] = None):
        """Initialize transformer."""
        self.mapping = mapping
        if not case_sensitive:
            self.mapping = {
                str(k).lower(): v
                for k, v in mapping.items()
            }
        self.case_sensitive = case_sensitive
        self.default = default
        
    def transform(self, value: Any) -> Any:
        """Transform value using mapping."""
        if value is None:
            return self.default
            
        key = str(value)
        if not self.case_sensitive:
            key = key.lower()
            
        return self.mapping.get(key, self.default)

class RegexTransformer(BaseTransformer):
    """Transforms values using regex."""
    
    def __init__(self, pattern: str,
                 group: int = 0,
                 replace: Optional[str] = None,
                 default: Optional[str] = None):
        """Initialize transformer."""
        self.pattern = pattern
        self.group = group
        self.replace = replace
        self.default = default
        self._regex = re.compile(pattern)
        
    def transform(self, value: Any) -> Any:
        """Transform value using regex."""
        if value is None:
            return self.default
            
        str_value = str(value)
        
        if self.replace is not None:
            return self._regex.sub(self.replace, str_value)
            
        match = self._regex.search(str_value)
        if match:
            try:
                return match.group(self.group)
            except IndexError:
                return self.default
        return self.default

class TransformerFactory(ITransformerFactory):
    """Factory for creating transformers."""
    
    def __init__(self, cache_size: int = 5000):
        """Initialize factory."""
        self.transformer_map: Dict[str, Type[BaseTransformer]] = {
            'date': DateTransformer,
            'numeric': NumericTransformer,
            'string': StringTransformer,
            'bool': BooleanTransformer,
            'list': ListTransformer,
            'mapping': MappingTransformer,
            'regex': RegexTransformer
        }
        self.cache = TransformerCache[Any](max_size=cache_size)
        
    def create_transformer(self, transform_type: str,
                         config: Dict[str, Any]) -> BaseTransformer:
        """Create cached transformer instance."""
        transformer_class = self.transformer_map.get(transform_type)
        if not transformer_class:
            raise ValueError(f"Unknown transformer type: {transform_type}")
            
        base_transformer = transformer_class(**config)
        
        # Wrap with caching if not already cached
        if not isinstance(base_transformer, CachedTransformer):
            return CachedTransformer(base_transformer, self.cache)
            
        return base_transformer
        
    def get_available_transforms(self) -> List[str]:
        """Get available transformation types."""
        return sorted(self.transformer_map.keys())
        
    def register_transformer(self, transform_type: str,
                           transformer_class: Type[BaseTransformer]) -> None:
        """Register custom transformer type."""
        self.transformer_map[transform_type] = transformer_class
        
class CachedTransformer(BaseTransformer):
    """Transformer wrapper that adds caching."""
    
    def __init__(self, base_transformer: BaseTransformer,
                 cache: TransformerCache[Any]):
        """Initialize with base transformer and cache."""
        self.base_transformer = base_transformer
        self.cache = cache
        
    def transform(self, value: Any) -> Any:
        """Transform with caching."""
        if value is None:
            return None
            
        # Compute cache key
        cache_key = self.cache.compute_cache_key(
            value,
            self.base_transformer.__class__.__name__,
            self._get_config()
        )
        
        # Try cache first
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            return cached_result
            
        # Transform and cache result
        result = self.base_transformer.transform(value)
        if result is not None:
            self.cache.put(cache_key, result)
            
        return result
        
    def _get_config(self) -> Dict[str, Any]:
        """Extract configuration from base transformer."""
        return {
            k: v for k, v in vars(self.base_transformer).items()
            if not k.startswith('_')
        }