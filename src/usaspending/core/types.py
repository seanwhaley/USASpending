"""Core type definitions and type management system."""
from typing import Dict, List, Any, Set, Optional, Union, TypedDict, DefaultDict, Literal, Type, TypeVar, NewType, cast, NamedTuple, Generic, Protocol
from enum import Enum, auto
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from .config import ComponentConfig

# Generic type for cache operations
T = TypeVar('T')
Entity = TypeVar('Entity')
Component = TypeVar('Component')

# Basic type aliases 
EntityKey = NewType('EntityKey', str)
EntityData = Dict[str, Any]
ConfigData = Dict[str, Any]

@dataclass
class ConfigValidationResult:
    """Result of configuration validation operation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    context: Optional[Dict[str, Any]] = None

class EntityType(str, Enum):
    """Entity types in the system."""
    AGENCY = "agency"
    CONTRACT = "contract"
    LOCATION = "location"
    RECIPIENT = "recipient"
    TRANSACTION = "transaction"
    SUB_AGENCY = "sub_agency"
    OFFICE = "office"
    
class RelationType(str, Enum):
    """Types of relationships between entities."""
    HIERARCHICAL = "hierarchical"  # Parent-child relationships (e.g., Agency-SubAgency)
    ASSOCIATIVE = "associative"    # Peer relationships (e.g., Contract-Recipient)
    REFERENCE = "reference"        # Lookup relationships (e.g., Transaction-Location)
    
    @property
    def is_hierarchical(self) -> bool:
        """Check if relationship type is hierarchical."""
        return self == RelationType.HIERARCHICAL
        
    @property
    def is_associative(self) -> bool:
        """Check if relationship type is associative."""
        return self == RelationType.ASSOCIATIVE
        
    @property
    def is_reference(self) -> bool:
        """Check if relationship type is reference."""
        return self == RelationType.REFERENCE

class Cardinality(str, Enum):
    """Relationship cardinality types."""
    ONE_TO_ONE = "1:1"
    ONE_TO_MANY = "1:n"
    MANY_TO_ONE = "n:1"
    MANY_TO_MANY = "n:n"

@dataclass
class EntityRelationship:
    """Defines a relationship between two entities."""
    source_entity: EntityType
    target_entity: EntityType
    relation_type: RelationType
    source_property: str
    target_property: str
    cardinality: Cardinality
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self) -> None:
        """Validate relationship configuration."""
        if self.source_entity == self.target_entity and self.relation_type.is_hierarchical:
            if not self.metadata or not self.metadata.get("allow_self_reference"):
                raise ValueError("Self-referential hierarchical relationships require explicit allow_self_reference=True in metadata")
                
        if self.relation_type.is_hierarchical and self.cardinality not in {Cardinality.ONE_TO_MANY, Cardinality.MANY_TO_ONE}:
            raise ValueError("Hierarchical relationships must have 1:n or n:1 cardinality")

class FieldType(Enum):
    """Field data types."""
    STRING = auto()
    INTEGER = auto()
    FLOAT = auto()
    BOOLEAN = auto()
    DATE = auto()
    MONEY = auto()
    ENUM = auto()
    LIST = auto()
    COMPOSITE = auto()
    
    @property
    def is_numeric(self) -> bool:
        """Check if field type is numeric."""
        return self in {FieldType.INTEGER, FieldType.FLOAT, FieldType.MONEY}
        
    @property
    def is_collection(self) -> bool:
        """Check if field type is a collection."""
        return self in {FieldType.LIST, FieldType.COMPOSITE}

AdapterResult = Optional[Union[str, int, float, bool, datetime, Decimal, List[Any]]]

class ValidationSeverity(str, Enum):
    """Validation message severity levels."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

class RuleType(str, Enum):
    """Types of validation rules."""
    TYPE = "type"             # Value type validation
    PATTERN = "pattern"       # Regex pattern matching
    RANGE = "range"          # Numeric range validation
    ENUM = "enum"            # Enumerated values
    REQUIRED = "required"     # Required field validation
    LENGTH = "length"        # String length validation
    FORMAT = "format"        # String format validation
    EMAIL = "email"          # Email format validation
    PHONE = "phone"          # Phone number format
    URL = "url"             # URL format validation
    ZIP = "zip"             # ZIP code format
    COMPARISON = "comparison" # Field comparison
    DATE_RANGE = "date_range" # Date range validation
    CONDITIONAL = "conditional" # Conditional validation
    DERIVED = "derived"      # Derived field validation
    CUSTOM = "custom"        # Custom validation function

@dataclass
class ValidationRule:
    """Validation rule definition."""
    id: str
    field_name: str
    rule_type: RuleType
    parameters: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    severity: ValidationSeverity = ValidationSeverity.ERROR
    enabled: bool = True
    groups: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    validation_context: Optional[Dict[str, Any]] = None

@dataclass
class ValidationResult:
    """Result of validation operation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    severity: ValidationSeverity = ValidationSeverity.ERROR
    field_name: Optional[str] = None
    rule_type: Optional[RuleType] = None
    validation_context: Optional[Dict[str, Any]] = None

TransformerType = Literal["string", "numeric", "date", "boolean", "enum"]

@dataclass
class TransformationRule:
    """Definition of a data transformation rule."""
    field_name: str
    transform_type: TransformerType
    parameters: Dict[str, Any]

@dataclass
class ComponentTypeConfig:
    """Configuration for component type definitions."""
    settings: Dict[str, Any]
    mappings: Optional[List[Dict[str, Any]]] = None
    entities: Optional[List[Dict[str, Any]]] = None

@dataclass
class EntityConfig:
    """Configuration for an entity type."""
    name: str
    fields: Dict[str, Any]
    key_fields: List[str]
    validations: Optional[List[Dict[str, Any]]] = None
    mappings: Optional[Dict[str, Any]] = None
    relationships: Optional[Dict[str, Any]] = None

@dataclass
class MappingResult:
    """Result of an entity mapping operation."""
    success: bool
    data: Optional[EntityData] = None
    errors: List[str] = field(default_factory=list)

@dataclass
class RuleSet:
    """Collection of validation rules."""
    name: str
    rules: List[ValidationRule]
    enabled: bool = True
    description: Optional[str] = None

class JsonData(TypedDict):
    """Type definition for JSON data."""
    type: str
    data: Dict[str, Any]

@dataclass
class SystemConfig:
    """System-wide configuration."""
    entity_types: List[EntityType]
    relationships: List[EntityRelationship]
    validation_rules: Dict[str, List[ValidationRule]]
    transformations: Dict[str, List[TransformationRule]]
    settings: Dict[str, Any]

# Protocol definitions
class ValidatableEntity(Protocol):
    """Protocol for validatable entities."""
    def validate(self) -> bool: ...

class IValidatable(Protocol):
    """Protocol for objects that can be validated."""
    def validate(self, data: Any) -> bool: ...
    def get_errors(self) -> List[str]: ...

class IConfigurable(Protocol):
    """Protocol for configurable components."""
    def configure(self, config: ComponentConfig) -> None: ...

class ITransformer(Protocol[T]):
    """Protocol for data transformers."""
    def transform(self, value: T) -> T: ...

DataclassInstance = TypeVar('DataclassInstance')

class DataclassProtocol(Protocol):
    """Protocol for dataclass instances."""
    __dataclass_fields__: Dict[str, Any]

EntityT = TypeVar('EntityT', bound=DataclassProtocol)

__all__ = [
    'EntityKey',
    'EntityData',
    'EntityType',
    'EntityRelationship',
    'RelationType',
    'Cardinality',
    'ValidationRule',
    'ValidationResult',
    'ValidationSeverity',
    'RuleType',
    'ComponentTypeConfig',
    'EntityConfig',
    'MappingResult',
    'TransformationRule',
    'TransformerType',
    'FieldType',
    'AdapterResult',
    'RuleSet',
    'JsonData',
    'SystemConfig',
    'ConfigData',
    'ConfigValidationResult',
    'Entity',
    'Component',
    'ValidatableEntity',
    'IValidatable',
    'IConfigurable',
    'ITransformer',
    'DataclassInstance',
    'EntityT'
]
