"""Test suite for field type adapters."""
import pytest
from decimal import Decimal
from datetime import date

from usaspending.schema_adapters import (
    SchemaAdapterFactory,
    DateFieldAdapter,
    DecimalFieldAdapter
)
from usaspending.string_adapters import StringFieldAdapter
from usaspending.enum_adapters import (
    EnumFieldAdapter,
    MappedEnumFieldAdapter
)
from usaspending.boolean_adapters import (
    BooleanFieldAdapter,
    FormattedBooleanAdapter
)

# Date adapter tests
def test_date_adapter_valid():
    adapter = DateFieldAdapter({'format': '%Y-%m-%d'})
    success, result = adapter.transform('2024-01-15')
    assert success
    assert isinstance(result, date)
    assert result == date(2024, 1, 15)

def test_date_adapter_invalid():
    adapter = DateFieldAdapter({'format': '%Y-%m-%d'})
    success, error = adapter.transform('invalid-date')
    assert not success
    assert 'Invalid date format' in error

# Decimal adapter tests
def test_decimal_adapter_valid():
    adapter = DecimalFieldAdapter({'precision': 2})
    success, result = adapter.transform('1234.56')
    assert success
    assert isinstance(result, Decimal)
    assert result == Decimal('1234.56')

def test_decimal_adapter_currency():
    adapter = DecimalFieldAdapter({'precision': 2})
    success, result = adapter.transform('$1,234.56')
    assert success
    assert result == Decimal('1234.56')

# String adapter tests
def test_string_adapter_basic():
    adapter = StringFieldAdapter({})
    success, result = adapter.transform('  test string  ')
    assert success
    assert result == 'test string'

def test_string_adapter_case():
    # Test uppercase
    adapter = StringFieldAdapter({'case': 'upper'})
    success, result = adapter.transform('test')
    assert success
    assert result == 'TEST'
    
    # Test lowercase
    adapter = StringFieldAdapter({'case': 'lower'})
    success, result = adapter.transform('TEST')
    assert success
    assert result == 'test'

def test_string_adapter_length():
    adapter = StringFieldAdapter({
        'min_length': 3,
        'max_length': 5
    })
    # Test valid length
    success, result = adapter.transform('test')
    assert success
    assert result == 'test'
    
    # Test too short
    success, error = adapter.transform('ab')
    assert not success
    assert 'min_length' in error.lower()
    
    # Test too long
    success, error = adapter.transform('testing')
    assert not success
    assert 'max_length' in error.lower()

def test_string_adapter_pattern():
    adapter = StringFieldAdapter({
        'pattern': r'^[A-Z]{2}\d{3}$'
    })
    # Test valid pattern
    success, result = adapter.transform('AB123')
    assert success
    assert result == 'AB123'
    
    # Test invalid pattern
    success, error = adapter.transform('123AB')
    assert not success
    assert 'pattern' in error.lower()

# Enum adapter tests
def test_enum_adapter():
    config = {
        'values': ['A', 'B', 'C'],
        'case_sensitive': False
    }
    adapter = EnumFieldAdapter(config)
    
    # Test valid values
    success, result = adapter.transform('A')
    assert success
    assert result == 'A'
    
    # Test case insensitivity
    success, result = adapter.transform('b')
    assert success
    assert result == 'b'
    
    # Test invalid value
    success, error = adapter.transform('X')
    assert not success
    assert 'Must be one of' in error

def test_mapped_enum_adapter():
    config = {
        'values': {
            'A': 'First Option',
            'B': 'Second Option',
            'C': 'Third Option'
        },
        'case_sensitive': False,
        'allow_unknown': False
    }
    adapter = MappedEnumFieldAdapter(config)
    
    # Test valid values
    success, result = adapter.transform('A')
    assert success
    assert result == 'A'
    
    # Test case insensitivity
    success, result = adapter.transform('b')
    assert success
    assert result == 'b'
    
    # Test invalid value
    success, error = adapter.transform('X')
    assert not success
    assert 'Invalid value' in error

# Boolean adapter tests
def test_boolean_adapter():
    config = {
        'true_values': ['true', 'yes', '1'],
        'false_values': ['false', 'no', '0'],
        'case_sensitive': False,
        'strict': True
    }
    adapter = BooleanFieldAdapter(config)
    
    # Test true values
    for val in config['true_values']:
        success, result = adapter.transform(val)
        assert success
        assert result is True
    
    # Test false values
    for val in config['false_values']:
        success, result = adapter.transform(val)
        assert success
        assert result is False
    
    # Test invalid value
    success, error = adapter.transform('invalid')
    assert not success
    assert 'must be one of' in error.lower()

def test_formatted_boolean_adapter():
    config = {
        'output_format': {
            'true': 'YES',
            'false': 'NO'
        },
        'case_sensitive': False
    }
    adapter = FormattedBooleanAdapter(config)
    
    # Test true value with formatting
    success, result = adapter.transform('true')
    assert success
    assert result is True
    
    model = adapter._create_model()
    instance = model(value=True)
    assert instance.format_output() == 'YES'
    
    # Test false value with formatting
    success, result = adapter.transform('false')
    assert success
    assert result is False
    
    instance = model(value=False)
    assert instance.format_output() == 'NO'

# Factory tests
def test_adapter_factory():
    # Test adapter registration and creation
    for type_name in [
        'date', 'decimal', 'string',
        'enum', 'mapped_enum',
        'boolean', 'formatted_boolean'
    ]:
        adapter = SchemaAdapterFactory.create(type_name, {})
        assert adapter is not None
        
    # Test unknown type
    adapter = SchemaAdapterFactory.create('unknown_type', {})
    assert adapter is None

# Integration tests with field configurations
def test_adapter_with_field_properties():
    # Example field property configurations
    field_configs = {
        'date': {
            'format': '%Y-%m-%d',
            'min_value': '2020-01-01',
            'max_value': '2025-12-31'
        },
        'decimal': {
            'precision': 2,
            'min_value': 0
        },
        'string': {
            'pattern': r'^[A-Z]{3}$',
            'case': 'upper'
        },
        'enum': {
            'values': ['A', 'B', 'C'],
            'case_sensitive': False
        },
        'mapped_enum': {
            'values': {
                'Y': 'Yes',
                'N': 'No',
                'M': 'Maybe'
            },
            'case_sensitive': False
        },
        'formatted_boolean': {
            'output_format': {
                'true': 'YES',
                'false': 'NO'
            }
        }
    }
    
    # Test each field type with its configuration
    for field_type, config in field_configs.items():
        adapter = SchemaAdapterFactory.create(field_type, config)
        assert adapter is not None
        # Basic validation test
        if hasattr(adapter, 'validate'):
            success, _ = adapter.validate('test')  # Use generic test value
            assert isinstance(success, bool)  # Just verify it returns a boolean