"""Tests for field adapter implementations."""
import warnings
import pytest
from typing import Dict, Any
from decimal import Decimal
from datetime import datetime, date

from usaspending.schema_adapters import (
    SchemaAdapterFactory, AdapterTransform,
    DateFieldAdapter, DecimalFieldAdapter, EnumFieldAdapter, 
    MappedEnumAdapter, CompositeFieldAdapter
)

def test_date_transformations():
    """Test date field transformations."""
    adapter = DateFieldAdapter({
        'transformation': {
            'operations': [
                {'type': 'normalize_date', 'output_format': '%Y-%m-%d'}
            ]
        }
    })
    
    # Test various date formats
    success, result = adapter.transform('2024-01-15')
    assert success and result == date(2024, 1, 15)
    
    success, result = adapter.transform('15/01/2024')
    assert success and result == date(2024, 1, 15)
    
    success, result = adapter.transform('Jan 15, 2024')
    assert success and result == date(2024, 1, 15)

def test_fiscal_year_derivation():
    """Test fiscal year derivation from dates."""
    adapter = DateFieldAdapter({
        'transformation': {
            'operations': [
                {'type': 'derive_fiscal_year', 'fiscal_year_start_month': 10}
            ]
        }
    })
    
    # Test fiscal year calculations
    success, result = adapter.transform('2024-01-15')
    assert success and result == 2024  # January is in FY 2024
    
    success, result = adapter.transform('2024-10-15')
    assert success and result == 2025  # October is in FY 2025

def test_decimal_transformations():
    """Test decimal field transformations."""
    adapter = DecimalFieldAdapter({
        'precision': 2,
        'transformation': {
            'operations': [
                {'type': 'strip_characters', 'characters': '$,'},
                {'type': 'convert_to_decimal'},
                {'type': 'round_number', 'places': 2}
            ]
        }
    })
    
    # Test various numeric formats
    success, result = adapter.transform('$1,234.567')
    assert success and result == Decimal('1234.57')
    
    success, result = adapter.transform('1234.567')
    assert success and result == Decimal('1234.57')
    
    success, result = adapter.transform('1,234')
    assert success and result == Decimal('1234.00')

def test_enum_transformations():
    """Test enum field transformations."""
    adapter = EnumFieldAdapter({
        'values': ['ACTIVE', 'INACTIVE', 'PENDING'],
        'case_sensitive': False,
        'transformation': {
            'operations': [
                {'type': 'trim'},
                {'type': 'uppercase'}
            ]
        }
    })
    
    # Test various enum values
    success, result = adapter.transform('active ')
    assert success and result == 'ACTIVE'
    
    success, result = adapter.transform(' INACTIVE')
    assert success and result == 'INACTIVE'
    
    success, result = adapter.transform('pending')
    assert success and result == 'PENDING'
    
    # Test invalid value
    success, result = adapter.transform('invalid')
    assert not success

def test_mapped_enum_transformations():
    """Test mapped enum transformations."""
    adapter = MappedEnumAdapter({
        'mapping': {
            'A': 'ACTIVE',
            'I': 'INACTIVE',
            'P': 'PENDING'
        },
        'case_sensitive': False,
        'default': 'UNKNOWN',
        'transformation': {
            'operations': [
                {'type': 'trim'},
                {'type': 'uppercase'}
            ]
        }
    })
    
    # Test various mapped values
    success, result = adapter.transform('a')
    assert success and result == 'ACTIVE'
    
    success, result = adapter.transform('I')
    assert success and result == 'INACTIVE'
    
    # Test default value
    success, result = adapter.transform('X')
    assert success and result == 'UNKNOWN'

def test_composite_transformations():
    """Test composite field transformations."""
    adapter = CompositeFieldAdapter({
        'components': ['fiscal_year', 'fiscal_quarter'],
        'transformation': {
            'operations': [
                {
                    'type': 'derive_date_components',
                    'components': ['fiscal_year', 'fiscal_quarter'],
                    'fiscal_year_start_month': 10
                }
            ]
        }
    })
    
    # Test date component extraction
    success, result = adapter.transform('2024-01-15')
    assert success
    assert isinstance(result, dict)
    assert result['fiscal_year'] == 2024
    assert result['fiscal_quarter'] == 2

def test_chained_transformations():
    """Test chaining multiple transformations."""
    adapter = DecimalFieldAdapter({
        'precision': 2,
        'transformation': {
            'operations': [
                {'type': 'strip_characters', 'characters': '$,'},
                {'type': 'convert_to_decimal'},
                {'type': 'round_number', 'places': 2},
                {'type': 'format_number', 'currency': True, 'grouping': True}
            ]
        }
    })
    
    # Test complex transformation chain
    success, result = adapter.transform('$1,234,567.891')
    assert success
    assert result == '$1,234,567.89'

def test_error_handling():
    """Test transformation error handling."""
    adapter = DecimalFieldAdapter({
        'precision': 2,
        'transformation': {
            'operations': [
                {'type': 'convert_to_decimal'}
            ]
        }
    })
    
    # Test invalid input
    success, error = adapter.transform('invalid')
    assert not success
    assert isinstance(error, str)
    assert 'Invalid' in error

@pytest.mark.parametrize('transform_type,input_value,config,expected', [
    ('uppercase', 'test', {}, 'TEST'),
    ('lowercase', 'TEST', {}, 'test'),
    ('trim', ' test ', {}, 'test'),
    ('strip_characters', '$1,234', {'characters': '$,'}, '1234'),
    ('pad_left', '123', {'length': 5, 'character': '0'}, '00123'),
    ('truncate', '12345', {'max_length': 3}, '123'),
    ('normalize_whitespace', 'test  string', {}, 'test string'),
    ('replace_chars', 'test', {'replacements': {'t': 'T'}}, 'TesT'),
])
def test_basic_transformations(transform_type: str, input_value: str, 
                             config: Dict[str, Any], expected: str):
    """Test basic transformation operations."""
    transform_fn = AdapterTransform.get(transform_type)
    assert transform_fn is not None
    
    result = transform_fn(input_value, **config)
    assert result == expected