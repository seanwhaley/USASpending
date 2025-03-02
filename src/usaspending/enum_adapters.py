"""Enumerated field adapters implementation."""
from typing import Any, Dict, Optional, Union, Set
from pydantic import BaseModel, Field, field_validator

from .schema_adapters import PydanticAdapter, SchemaAdapterFactory, AdapterTransform

class EnumFieldAdapter(PydanticAdapter[str, str]):
    """Base adapter for enumerated fields."""
    
    def _create_model(self) -> type[BaseModel]:
        """Create Pydantic model for enum validation/transformation."""
        values = self.config.get('values', set())
        case_sensitive = self.config.get('case_sensitive', True)
        allow_unknown = self.config.get('allow_unknown', False)
        
        # Create validation set
        valid_values = {str(v) for v in values}
        value_desc = ', '.join(sorted(valid_values))
        
        class EnumModel(BaseModel):
            value: str = Field(description=f"Must be one of: {value_desc}")
            
            @field_validator('value')
            @classmethod 
            def validate_enum(cls, v: str) -> str:
                check_value = str(v).upper() if not case_sensitive else str(v)
                valid_set = {str(val).upper() if not case_sensitive else str(val) for val in valid_values}
                
                if check_value not in valid_set and not allow_unknown:
                    raise ValueError(f"Value must be one of: {value_desc}")
                return v
            
            @field_validator('value', mode='before')
            @classmethod
            def clean_value(cls, v: Any) -> str:
                if not isinstance(v, str):
                    v = str(v)
                return v.strip()
        
        return EnumModel
    
    def _validate_config(self) -> None:
        """Validate enum adapter configuration."""
        if 'values' not in self.config:
            raise ValueError("EnumFieldAdapter requires 'values' configuration")
        
        if not isinstance(self.config['values'], (list, set, dict)):
            raise ValueError("'values' must be a list, set, or dictionary")
        
        if 'case_sensitive' in self.config and not isinstance(self.config['case_sensitive'], bool):
            raise ValueError("'case_sensitive' must be a boolean")
            
        if 'allow_unknown' in self.config and not isinstance(self.config['allow_unknown'], bool):
            raise ValueError("'allow_unknown' must be a boolean")

class MappedEnumFieldAdapter(EnumFieldAdapter):
    """Adapter for enums with value mappings and descriptions."""
    
    def _create_model(self) -> type[BaseModel]:
        """Create Pydantic model for mapped enum validation."""
        values = self.config.get('values', {})
        descriptions = self.config.get('descriptions', {})
        case_sensitive = self.config.get('case_sensitive', True)
        allow_unknown = self.config.get('allow_unknown', False)
        
        if not isinstance(values, dict):
            # Convert list/set to dict with identity mapping
            values = {str(v): str(v) for v in values}
            
        value_desc = ', '.join(f'{k}={descriptions.get(k, v)}' for k, v in values.items())
        
        class MappedEnumModel(BaseModel):
            value: str = Field(description=f"Valid values: {value_desc}")
            
            @field_validator('value')
            @classmethod
            def validate_mapped_enum(cls, v: str) -> str:
                check_value = str(v).upper() if not case_sensitive else str(v)
                valid_set = {str(val).upper() if not case_sensitive else str(val) for val in values.keys()}
                
                if check_value not in valid_set and not allow_unknown:
                    raise ValueError(f"Invalid value. Must be one of: {value_desc}")
                return v
            
            @field_validator('value', mode='before')
            @classmethod
            def clean_mapped_enum(cls, v: Any) -> str:
                if not isinstance(v, str):
                    v = str(v)
                v = v.strip()
                if not case_sensitive:
                    v = v.upper()
                # Handle common variations if provided
                variations = {var.upper(): code for code, vars in values.items() for var in vars} if isinstance(values, dict) else {}
                return variations.get(v.upper(), v) if not case_sensitive else variations.get(v, v)
        
        return MappedEnumModel

# Register enum-specific transformations
@AdapterTransform.register('map_values')
def transform_map_values(value: str, mapping: Dict[str, str], case_sensitive: bool = True) -> str:
    """Map input values to output values."""
    check_value = value if case_sensitive else value.upper()
    mapping_keys = mapping.keys() if case_sensitive else {k.upper(): v for k, v in mapping.items()}
    return mapping_keys.get(check_value, value)

@AdapterTransform.register('normalize_enum')
def transform_normalize_enum(value: str, valid_values: Set[str], case_sensitive: bool = True) -> str:
    """Normalize enum value to match valid values."""
    if not case_sensitive:
        check_value = value.upper()
        valid_set = {v.upper(): v for v in valid_values}
        return valid_set.get(check_value, value)
    return value if value in valid_values else value

# Register adapters with factory
SchemaAdapterFactory.register('enum', EnumFieldAdapter)
SchemaAdapterFactory.register('mapped_enum', MappedEnumFieldAdapter)