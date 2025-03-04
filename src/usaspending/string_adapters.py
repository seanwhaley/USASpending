"""String field adapters implementation."""
from typing import Any, Dict, Optional, Union
import re
from pydantic import BaseModel, Field, field_validator

from .schema_adapters import PydanticAdapter, SchemaAdapterFactory, AdapterTransform

class StringFieldAdapter(PydanticAdapter[str, str]):
    """Base adapter for string fields with common string validations."""
    
    def _create_model(self) -> type[BaseModel]:
        """Create Pydantic model for string validation/transformation."""
        min_length = self.config.get('min_length')
        max_length = self.config.get('max_length')
        pattern = self.config.get('pattern')
        
        class StringModel(BaseModel):
            value: str = Field(
                min_length=min_length,
                max_length=max_length,
                pattern=pattern if pattern else None,
                description=self._generate_field_description()
            )
            
            @field_validator('value', mode='before')
            @classmethod
            def clean_string(cls, v: Any) -> str:
                if not isinstance(v, str):
                    v = str(v)
                return v
        
        return StringModel
    
    def _validate_config(self) -> None:
        """Validate string adapter configuration."""
        if 'min_length' in self.config:
            if not isinstance(self.config['min_length'], int):
                raise ValueError("'min_length' must be an integer")
            if self.config['min_length'] < 0:
                raise ValueError("'min_length' must be non-negative")
                
        if 'max_length' in self.config:
            if not isinstance(self.config['max_length'], int):
                raise ValueError("'max_length' must be an integer")
            if self.config['max_length'] < 0:
                raise ValueError("'max_length' must be non-negative")
            
        if 'pattern' in self.config:
            try:
                re.compile(self.config['pattern'])
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {str(e)}")
    
    def _generate_field_description(self) -> str:
        """Generate field description from configuration."""
        desc_parts = []
        if 'min_length' in self.config:
            desc_parts.append(f"Minimum length: {self.config['min_length']}")
        if 'max_length' in self.config:
            desc_parts.append(f"Maximum length: {self.config['max_length']}")
        if 'pattern' in self.config:
            desc_parts.append(f"Must match pattern: {self.config['pattern']}")
        return ". ".join(desc_parts) if desc_parts else "String field"

# Register string-specific transformations
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
    if match:
        return match.group(0)
    return value

# Register adapter with factory
SchemaAdapterFactory.register('string', StringFieldAdapter)