"""Type definitions for the USASpending data processing package."""
from typing import Dict, List, Any, Set, Optional, Union, TypedDict, DefaultDict
from dataclasses import dataclass, field
from datetime import datetime

class SkippedStats(TypedDict, total=False):
    """Statistics about skipped entities."""
    missing_key_fields: int
    invalid_data: int
    extraction_error: int
    invalid_input: int
    no_relevant_data: int

@dataclass
class ChunkInfo:
    """Information about a data chunk file."""
    file: str
    record_count: int
    chunk_number: int

# Define EntityData before it's used
class EntityData(TypedDict, total=False):
    """Entity data structure definition."""
    uei: str
    characteristics: Dict[str, bool]
    name: Optional[str]
    address: Optional[Dict[str, str]]
    identifiers: Optional[Dict[str, str]]
    business_types: Optional[List[str]]

@dataclass
class EntityStats:
    """Statistics about processed entities."""
    total: int = 0
    unique: int = 0
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
class ContractRelationshipStats:
    """Statistics about contract relationships."""
    parent_contracts: int = 0
    child_contracts: int = 0
    orphaned_references: int = 0
    recipient_contracts: int = 0
    parent_recipient_contracts: int = 0
    recipient_relationships: int = 0

    def to_dict(self) -> Dict[str, int]:
        """Convert stats to dictionary."""
        return {
            "parent_contracts": self.parent_contracts,
            "child_contracts": self.child_contracts,
            "orphaned_references": self.orphaned_references,
            "recipient_contracts": self.recipient_contracts,
            "parent_recipient_contracts": self.parent_recipient_contracts,
            "recipient_relationships": self.recipient_relationships
        }

@dataclass
class RecipientCharacteristics:
    """Recipient business characteristics."""
    ownership: Set[str] = field(default_factory=set)
    structure: Set[str] = field(default_factory=set)
    size: Set[str] = field(default_factory=set)
    government: Set[str] = field(default_factory=set)
    institution: Set[str] = field(default_factory=set)

@dataclass
class AgencyRelations:
    """Agency relationship tracking."""
    parent_mappings: Dict[str, Dict[str, str]] = field(default_factory=dict)
    roles: Dict[str, Set[str]] = field(
        default_factory=lambda: {
            'awarding': set(),
            'funding': set()
        }
    )

@dataclass
class ContractValues:
    """Contract value tracking."""
    current: float = 0.0
    potential: float = 0.0
    obligated: float = 0.0
    modifications: Set[str] = field(default_factory=set)

# Type aliases with more specific types
ConfigType = Dict[str, Any]
RelationshipMap = Dict[str, Dict[str, Set[str]]]
EntityCache = Dict[str, EntityData]

# New types for tracking parent agencies
ParentAgencyMapping = Dict[str, Dict[str, str]]  # {parent_id: {'level': 'department|sub_agency|office', 'mapped_id': 'actual_agency_id'}}
PendingParentAgencies = Dict[str, Dict[str, Any]]  # {parent_id: {'name': str, 'data': Dict}}

@dataclass
class ParentAgencyReference:
    """Parent award agency reference."""
    agency_id: str
    agency_name: str
    level: Optional[str] = None
    resolved_id: Optional[str] = None

class AgencyHierarchyLevel(TypedDict):
    """Agency hierarchy level definition."""
    code: str
    name: str
    source_fields: Dict[str, List[str]]

class AgencyResolutionStats(TypedDict):
    """Statistics for parent agency resolution."""
    total_references: int
    resolved_immediately: int
    resolved_later: int
    unresolved: int
    levels: Dict[str, int]  # Count of resolutions by level

# Specific type definitions for configuration sections
class TypeConversionConfig(TypedDict):
    """Type conversion configuration section."""
    date_fields: List[str]
    numeric_fields: List[str]
    boolean_true_values: List[str]
    boolean_false_values: List[str]

class ChunkingConfig(TypedDict):
    """Chunking configuration section."""
    enabled: bool
    records_per_chunk: int
    create_index: bool

class InputConfig(TypedDict):
    """Input configuration section."""
    file: str
    batch_size: int

class OutputConfig(TypedDict):
    """Output configuration section."""
    main_file: str
    indent: int
    ensure_ascii: bool

# Fix ContractFinancialData to use proper Optional types
class ContractFinancialData(TypedDict, total=False):
    """Contract-level financial data."""
    total_obligated: float
    total_outlayed: Optional[float]
    base_exercised_value: float
    current_value: float
    base_all_options: float
    potential_value: float

class ProductServiceData(TypedDict):
    """Product or service classification."""
    code: str
    description: str
    
class CompetitionData(TypedDict):
    """Competition and set-aside information."""
    extent_competed: Dict[str, str]  # code/description
    set_aside: Dict[str, str]       # code/description
    
class SolicitationData(TypedDict):
    """Solicitation-related information."""
    identifier: Optional[str]
    procedures: Dict[str, str]      # code/description
    number_of_offers: int

class TransactionEntity(TypedDict, total=False):
    """Transaction-specific data."""
    transaction_key: str
    action_date: str
    action_type: str
    modification_number: str
    description: str
    obligation_amount: float
    contract_ref: str
    recipient_ref: str
    awarding_agency_ref: str
    funding_agency_ref: str

class PlaceOfPerformanceData(TypedDict, total=False):
    """Place of performance location data."""
    city: str
    state: str
    zip: str
    country: str
    county: str
    congressional_district: str
    foreign_city: Optional[str]
    foreign_country_name: Optional[str]

class ContractData(TypedDict, total=False):
    """Contract entity data structure."""
    award_id: str
    piid: str
    parent_piid: Optional[str]
    parent_agency_id: Optional[str]
    solicitation_id: Optional[str]
    description: str
    transaction_desc: Optional[str]
    type: str
    current_value: float
    potential_value: float
    current_total: float
    potential_total: float
    total_obligated: float
    performance_start: Optional[str]
    performance_end: Optional[str]
    last_modified: str
    is_parent: bool
    child_count: int

# Validation Types
@dataclass
class ValidationRule:
    """Rule definition for field validation."""
    type: str
    field: str
    rules: List[Dict[str, Any]]

@dataclass
class ValidationResult:
    """Result of a validation check."""
    valid: bool
    message: Optional[str] = None