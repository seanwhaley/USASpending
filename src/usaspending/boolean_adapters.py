"""Boolean field adapters implementation."""
from typing import Any, Dict, Optional, Union, Literal, List
from pydantic import BaseModel, Field, field_validator

from .schema_adapters import PydanticAdapter, SchemaAdapterFactory

class BooleanFieldAdapter(PydanticAdapter[str, bool]):
    """Base adapter for boolean fields."""
    
    def _create_model(self) -> type[BaseModel]:
        """Create Pydantic model for boolean validation/transformation."""
        true_values = self.config.get('true_values', ['true', 'yes', 'y', '1', 't'])
        false_values = self.config.get('false_values', ['false', 'no', 'n', '0', 'f'])
        case_sensitive = self.config.get('case_sensitive', False)
        strict = self.config.get('strict', True)
        
        class BooleanModel(BaseModel):
            value: bool = Field(description=f"True values: {true_values}, False values: {false_values}")
            
            @field_validator('value', mode='before')
            @classmethod
            def parse_bool(cls, v: Any) -> bool:
                if isinstance(v, bool):
                    return v
                
                if not isinstance(v, str):
                    v = str(v)
                
                v = v.strip()
                if not case_sensitive:
                    v = v.lower()
                    true_check = [str(t).lower() for t in true_values]
                    false_check = [str(f).lower() for f in false_values]
                else:
                    true_check = [str(t) for t in true_values]
                    false_check = [str(f) for f in false_values]
                
                if v in true_check:
                    return True
                if v in false_check:
                    return False
                
                if not strict:
                    # Basic truthy/falsy logic for non-strict mode
                    if v in ('1', 't', 'true', 'yes', 'y'):
                        return True
                    if v in ('0', 'f', 'false', 'no', 'n'):
                        return False
                    
                raise ValueError(
                    f"Value must be one of: {', '.join(true_values)} for True "
                    f"or {', '.join(false_values)} for False"
                )
        
        return BooleanModel
    
    def _validate_config(self) -> None:
        """Validate boolean adapter configuration."""
        if 'true_values' in self.config and not isinstance(self.config['true_values'], (list, tuple)):
            raise ValueError("'true_values' must be a list or tuple")
            
        if 'false_values' in self.config and not isinstance(self.config['false_values'], (list, tuple)):
            raise ValueError("'false_values' must be a list or tuple")

class FormattedBooleanAdapter(BooleanFieldAdapter):
    """Boolean adapter with configurable output formatting."""
    
    def _create_model(self) -> type[BaseModel]:
        """Create Pydantic model for formatted boolean validation."""
        output_format = self.config.get('output_format', {})
        true_output = output_format.get('true', 'Y')
        false_output = output_format.get('false', 'N')
        
        class FormattedBooleanModel(BaseModel):
            value: bool = Field(description=f"Boolean field (outputs: {true_output}/{false_output})")
            true_format: str = Field(default=true_output)
            false_format: str = Field(default=false_output)
            
            @field_validator('value', mode='before')
            @classmethod
            def parse_formatted_bool(cls, v: Any) -> bool:
                if isinstance(v, bool):
                    return v
                
                if not isinstance(v, str):
                    v = str(v)
                
                v = v.strip().upper()
                true_variations = cls._get_true_variations()
                false_variations = cls._get_false_variations()
                
                if v in true_variations:
                    return True
                if v in false_variations:
                    return False
                
                raise ValueError(
                    f"Invalid boolean value. Must be one of: "
                    f"{', '.join(true_variations)} for True or "
                    f"{', '.join(false_variations)} for False"
                )
            
            @classmethod
            def _get_true_variations(cls) -> List[str]:
                """Get standard true value variations."""
                return ['Y', 'YES', 'TRUE', '1', 'T']
            
            @classmethod
            def _get_false_variations(cls) -> List[str]:
                """Get standard false value variations."""
                return ['N', 'NO', 'FALSE', '0', 'F']
            
            def format_output(self) -> str:
                """Format boolean value according to configuration."""
                return self.true_format if self.value else self.false_format
        
        return FormattedBooleanModel
    
    def _validate_config(self) -> None:
        """Validate formatted boolean adapter configuration."""
        super()._validate_config()
        output_format = self.config.get('output_format', {})
        if not isinstance(output_format, dict):
            raise ValueError("'output_format' must be a dictionary")
            
        true_format = output_format.get('true')
        false_format = output_format.get('false')
        if true_format and not isinstance(true_format, str):
            raise ValueError("'true' format must be a string")
        if false_format and not isinstance(false_format, str):
            raise ValueError("'false' format must be a string")

# Register adapters with factory
SchemaAdapterFactory.register('boolean', BooleanFieldAdapter)
SchemaAdapterFactory.register('formatted_boolean', FormattedBooleanAdapter)