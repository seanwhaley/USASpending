"""
USASpending Data Processing Package
===================================
This package contains modules for schema adapters, validation, and data processing for USASpending.
"""

# Schema adapters and validation - direct imports from schema_adapters module
from .schema_adapters import (
    SchemaAdapterFactory,
    FieldAdapter,
    PydanticAdapter, 
    MarshmallowAdapter,
    DateFieldAdapter,
    DecimalFieldAdapter,
    BaseSchemaAdapter,
    StringAdapter,
    NumericAdapter,
    DateAdapter,
    BooleanAdapter,
    EnumAdapter,
    ListAdapter,
    DictAdapter,
    AdapterTransform
)
from .string_adapters import StringFieldAdapter
from .enum_adapters import (
    EnumFieldAdapter,
    MappedEnumFieldAdapter
)
from .boolean_adapters import (
    BooleanFieldAdapter,
    FormattedBooleanAdapter
)

# Core functionality
from .config import ConfigManager
from .entity_mapper import EntityMapper
from .entity_serializer import EntitySerializer
from .entity_factory import EntityFactory
from .entity_cache import EntityCache
from .chunked_writer import ChunkedWriter
from .exceptions import USASpendingException
from .processor import convert_csv_to_json, DataProcessor

# File and data utilities
from .file_utils import (
    read_json_file as load_json,
    write_json_file as save_json,
    get_files,
    ensure_directory as ensure_directory_exists
)
from .utils import (
    format_datetime,
    validate_path
)

# Core data structures and interfaces
from .dictionary import Dictionary
from .entity_store import EntityStore
from .field_dependencies import FieldDependencies
from .field_selector import FieldSelector
from .interfaces import (
    IDataProcessor,
    IValidator,
    ISchemaAdapter,
    IFieldValidator
)
from .keys import Keys
from .logging_config import get_logger, configure_logging
from .schema_mapping import SchemaMapping
from .serialization_utils import (
    serialize_to_json,
    deserialize_from_json,
    format_decimal
)
from .startup_checks import perform_startup_checks
from .transformers import (
    transform_date,
    transform_decimal,
    transform_enum
)
from .types import Types
from .validation_base import BaseValidator

__all__ = [
    # Schema adapters
    'SchemaAdapterFactory',
    'FieldAdapter',
    'PydanticAdapter',
    'MarshmallowAdapter',
    'DateFieldAdapter',
    'DecimalFieldAdapter',
    'BaseSchemaAdapter',
    'StringAdapter',
    'NumericAdapter',
    'DateAdapter',
    'BooleanAdapter',
    'EnumAdapter',
    'ListAdapter',
    'DictAdapter',
    'AdapterTransform',
    'StringFieldAdapter',
    'EnumFieldAdapter',
    'MappedEnumFieldAdapter',
    'BooleanFieldAdapter',
    'FormattedBooleanAdapter',
    
    # Configuration and processing
    'ConfigManager',  # Now using ConfigManager directly instead of Config
    'Validator',
    'EntityMapper',
    'EntitySerializer',
    'EntityFactory',
    'EntityCache',
    'ChunkedWriter',
    'USASpendingException',
    
    # Direct functions instead of aliases
    'load_json',
    'save_json',
    'format_datetime',
    'validate_path',
    'Dictionary',
    'EntityStore',
    'FieldDependencies',
    'FieldSelector',
    'get_files',
    'create_directory',
    'ensure_directory_exists',
    'read_csv',
    'IDataProcessor',
    'IValidator',
    'ISchemaAdapter',
    'Keys',
    'get_logger',
    'configure_logging',
    'Processor',
    'SchemaMapping',
    'serialize_to_json',
    'deserialize_from_json',
    'format_decimal',
    'perform_startup_checks',
    'transform_date',
    'transform_decimal',
    'transform_enum',
    'Types',
    'Validation'
]