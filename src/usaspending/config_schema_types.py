"""Configuration schema type definitions."""
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field, ConfigDict

class TransformOperation(BaseModel):
    """Schema for transformation operations."""
    model_config = ConfigDict(extra='allow')
    
    type: str = Field(..., description="Type of transformation operation")
    # Common parameters
    input_formats: Optional[List[str]] = Field(None, description="Input date formats to try")
    output_format: Optional[str] = Field(None, description="Output format for dates/numbers")
    
    # String operations
    characters: Optional[str] = Field(None, description="Characters for strip operation")
    length: Optional[int] = Field(None, description="Length for padding/truncation")
    character: Optional[str] = Field(None, description="Character for padding")
    pattern: Optional[str] = Field(None, description="Pattern for extraction/matching")
    
    # Numeric operations
    precision: Optional[int] = Field(None, description="Decimal precision")
    places: Optional[int] = Field(None, description="Rounding places")
    currency: Optional[bool] = Field(None, description="Format as currency")
    grouping: Optional[bool] = Field(None, description="Use grouping separators")
    
    # Date operations
    dayfirst: Optional[bool] = Field(None, description="Parse dates with day first")
    yearfirst: Optional[bool] = Field(None, description="Parse dates with year first")
    fuzzy: Optional[bool] = Field(None, description="Allow fuzzy date parsing")
    fiscal_year_start_month: Optional[int] = Field(None, description="Fiscal year start month")
    components: Optional[List[str]] = Field(None, description="Date components to extract")
    
    # Mapping operations
    mapping: Optional[Dict[str, Any]] = Field(None, description="Value mapping dictionary")
    case_sensitive: Optional[bool] = Field(None, description="Case-sensitive mapping")
    default: Optional[Any] = Field(None, description="Default value for mapping")
    valid_values: Optional[List[str]] = Field(None, description="Valid enum values")
    replacements: Optional[Dict[str, str]] = Field(None, description="Character replacement map")

class TransformationConfig(BaseModel):
    """Schema for field transformation configuration."""
    model_config = ConfigDict(extra='forbid')
    
    timing: str = Field("before_validation", description="When to apply transformations")
    operations: List[TransformOperation] = Field(default_factory=list, description="List of transformation operations")

class DependencyConfig(BaseModel):
    """Schema for field dependency configuration."""
    model_config = ConfigDict(extra='forbid')
    
    type: str = Field(..., description="Type of dependency relationship")
    target_field: str = Field(..., description="Field that this field depends on")
    validation_rule: Optional[Dict[str, Any]] = Field(None, description="Validation rule for dependency")
    error_message: Optional[str] = Field(None, description="Custom error message")
    error_level: str = Field(default="error", description="How to handle validation failures")

class ValidationGroup(BaseModel):
    """Schema for validation group configuration."""
    model_config = ConfigDict(extra='forbid')
    
    name: str = Field(..., description="Name of validation group")
    description: Optional[str] = Field(None, description="Description of validation group purpose")
    enabled: bool = Field(default=True, description="Whether this group is active")
    rules: List[str] = Field(default_factory=list, description="Validation rules in this group")
    dependencies: List[str] = Field(default_factory=list, description="Other groups this depends on")
    error_level: str = Field(default="error", description="How to handle validation failures")

class ValidationConfig(BaseModel):
    """Schema for field validation configuration."""
    model_config = ConfigDict(extra='forbid')
    
    format: Optional[str] = Field(None, description="Format string for validation")
    pattern: Optional[str] = Field(None, description="Regex pattern for validation")
    min_value: Optional[Union[int, float]] = Field(None, description="Minimum allowed value")
    max_value: Optional[Union[int, float]] = Field(None, description="Maximum allowed value")
    precision: Optional[int] = Field(None, description="Required decimal precision")
    values: Optional[List[str]] = Field(None, description="Valid enum values")
    error_message: Optional[str] = Field(None, description="Custom error message")
    dependencies: Optional[List[DependencyConfig]] = Field(None, description="Field dependencies")
    groups: Optional[List[str]] = Field(None, description="Validation groups this field belongs to")
    conditional_rules: Optional[Dict[str, ValidationConfig]] = Field(None, description="Conditional validation rules")

class FieldProperties(BaseModel):
    """Schema for field property configuration."""
    model_config = ConfigDict(extra='forbid')
    
    type: str = Field(..., description="Field type")
    validation: Optional[ValidationConfig] = Field(None, description="Validation rules")
    transformation: Optional[TransformationConfig] = Field(None, description="Transformation rules")