"""Type definitions for the USASpending data processing package."""
from typing import Dict, List, Any, Set, Optional, Union, TypedDict, DefaultDict, Literal, Type
from dataclasses import dataclass, field
from datetime import datetime

# Type Registry
_TYPE_REGISTRY: Dict[str, type] = {}

def register_type(name: str, type_class: type) -> None:
    """Register an entity type."""
    _TYPE_REGISTRY[name] = type_class

def get_registered_type(name: str) -> Optional[type]:
    """Get a registered entity type."""
    return _TYPE_REGISTRY.get(name)

def get_registered_types() -> Dict[str, type]:
    """Get all registered entity types."""
    return _TYPE_REGISTRY.copy()

def load_types_from_config(config: Dict[str, Any]) -> None:
    """Load and register entity types from configuration.
    
    Args:
        config: Configuration dictionary containing type definitions
    """
    entity_types = config.get('contracts', {}).get('entity_separation', {}).get('entities', {})
    
    for entity_type in entity_types:
        if entity_type not in _TYPE_REGISTRY:
            # Create a new EntityData-based type for this entity
            register_type(entity_type, EntityData)

# Core Validation Types
@dataclass
class ValidationRule:
    """Rule definition for field validation."""
    type: str
    field: str
    rules: List[Dict[str, Any]]
    rule_config: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None  # Add source attribute

    @classmethod
    def from_yaml(cls, yaml_config: Dict[str, Any]) -> 'ValidationRule':
        """Create validation rule from YAML configuration."""
        return cls(
            type=yaml_config.get('type', ''),
            field=yaml_config.get('field', ''),
            rules=yaml_config.get('rules', []),
            rule_config=yaml_config.get('config', {})
        )

@dataclass
class ValidationResult:
    """Result of a validation check."""
    valid: bool
    message: Optional[str] = None
    error_type: Optional[str] = None
    field_name: Optional[str] = None

# Statistics Types
@dataclass
class BaseStats:
    """Base statistics tracking."""
    total: int = 0
    unique: int = 0

class SkippedStats(TypedDict, total=False):
    """Statistics about skipped entities."""
    missing_key_fields: int
    invalid_data: int
    extraction_error: int
    invalid_input: int
    no_relevant_data: int

@dataclass
class EntityStats(BaseStats):
    """Statistics about processed entities."""
    natural_keys_used: int = 0
    hash_keys_used: int = 0
    skipped: SkippedStats = field(
        default_factory=lambda: SkippedStats(
            missing_key_fields=0,
            invalid_data=0,
            extraction_error=0,
            invalid_input=0,
            no_relevant_data=0
        )
    )
    relationships: DefaultDict[str, int] = field(
        default_factory=lambda: DefaultDict(int)
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "total": self.total,
            "unique": self.unique,
            "natural_keys_used": self.natural_keys_used,
            "hash_keys_used": self.hash_keys_used,
            "skipped": dict(self.skipped),
            "relationships": dict(self.relationships)
        }

@dataclass
class ChunkInfo:
    """Information about a data chunk file."""
    file: str
    record_count: int
    chunk_number: int

# Agency-specific types
@dataclass
class AgencyResolutionStats:
    """Statistics about agency resolution."""
    total_agencies: int = 0
    resolved_agencies: int = 0
    unresolved_agencies: int = 0
    resolution_by_level: Dict[str, int] = field(default_factory=dict)
    unresolved_by_level: Dict[str, int] = field(default_factory=dict)

# Configuration Types
class GlobalConfig(TypedDict):
    """Global configuration section."""
    input: Dict[str, Any]
    output: Dict[str, Any]
    processing: Dict[str, Any]
    error_handling: Dict[str, Any]

class ValidationTypeConfig(TypedDict):
    """Validation type configuration."""
    type: str
    rules: Optional[List[Dict[str, Any]]]

class EntityFieldMapping(TypedDict):
    """Entity field mapping configuration."""
    field: str
    source: Union[str, List[str], Dict[str, str]]

class EntityRelationship(TypedDict):
    """Entity relationship configuration."""
    type: str
    from_field: str
    to_field: str
    relationship: str
    inverse: Optional[str]

class EntityConfig(TypedDict):
    """Entity configuration section."""
    key_fields: List[str]
    field_mappings: Dict[str, Union[str, List[str], Dict[str, Any]]]
    relationships: Optional[Dict[str, List[EntityRelationship]]]
    field_patterns: Optional[List[str]]
    exclude_fields: Optional[List[str]]

class ConfigType(TypedDict):
    """Complete configuration type."""
    global_config: GlobalConfig
    validation_types: Dict[str, Dict[str, ValidationTypeConfig]]
    type_conversion: Dict[str, Dict[str, Any]]
    contracts: Dict[str, Any]

# Entity Types
class EntityData(TypedDict, total=False):
    """Base entity data structure."""
    id: str
    type: str
    attributes: Dict[str, Any]
    relationships: Optional[Dict[str, Any]]

# Entity-specific types
class RecipientCharacteristics(TypedDict, total=False):
    """Characteristics of a recipient entity."""
    business_types: List[str]
    socioeconomic_indicators: List[str]
    organizational_structure: Optional[str]
    size_metrics: Optional[Dict[str, Any]]
    industry_codes: Optional[Dict[str, str]]

# Error message configuration types
class ValidationErrorMessages(TypedDict, total=False):
    """Error message templates for validation."""
    invalid: str
    rule_violation: str
    precision_exceeded: str
    below_minimum: str
    above_maximum: str

class ValidationErrorConfig(TypedDict, total=False):
    """Error message configuration by validation type."""
    numeric: ValidationErrorMessages
    date: ValidationErrorMessages
    string: ValidationErrorMessages
    general: ValidationErrorMessages
    csv: ValidationErrorMessages

# Specific validation type configurations
class NumericValidationConfig(TypedDict, total=False):
    """Numeric validation configuration."""
    decimal: Dict[str, Union[int, str]]  # precision, strip_characters
    min_value: float
    max_value: float

class DateValidationConfig(TypedDict, total=False):
    """Date validation configuration."""
    format: str
    not_future: bool
    standard: Dict[str, str]

class StringValidationConfig(TypedDict, total=False):
    """String validation configuration."""
    pattern: Dict[str, str]
    length: Dict[str, int]

# Enhanced ValidationTypeConfig
class EnhancedValidationTypeConfig(TypedDict, total=False):
    """Enhanced validation type configuration."""
    numeric: NumericValidationConfig
    date: DateValidationConfig
    string: StringValidationConfig
    domain: Dict[str, Any]

# Validation configuration section
class ValidationConfig(TypedDict, total=False):
    """Validation configuration section."""
    errors: ValidationErrorConfig
    empty_values: List[str]
    field_types: Dict[str, str]

# Type aliases
RelationshipMap = Dict[str, Dict[str, Set[str]]]
EntityCache = Dict[str, EntityData]
TypeRegistry = Dict[str, type]

# Register built-in types
register_type('recipient', EntityData)