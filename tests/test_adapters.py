"""Tests for field adapter implementations."""
import warnings
import pytest
from typing import Dict, Any
from decimal import Decimal
from datetime import datetime, date
from pathlib import Path
import tempfile
import yaml

from usaspending.dictionary import Dictionary, FieldDefinition
from usaspending.schema_adapters import (
    SchemaAdapterFactory, AdapterTransform,
    DateFieldAdapter, DecimalFieldAdapter
)
from usaspending.enum_adapters import (
    EnumFieldAdapter, MappedEnumFieldAdapter  # Fixed class name
)
from usaspending.schema_adapters import CompositeFieldAdapter

def test_date_transformations():
    adapter = DateFieldAdapter()
    
    # Test string to date conversion
    assert adapter.process(datetime(2023, 1, 15, 12, 30)) == date(2023, 1, 15)
    
    # Test date object passed through
    test_date = date(2023, 1, 15)
    assert adapter.process(test_date) == test_date
    
    # Test None value
    assert adapter.process(None) is None

def test_fiscal_year_derivation():
    adapter = DateFieldAdapter(fiscal_year=True)
    
    # Test fiscal year derivation (US fiscal year starts in October)
    assert adapter.process(date(2023, 3, 15)) == 2023
    assert adapter.process("2023-09-30") == 2023
    assert adapter.process("2023-10-01") == 2024

def test_decimal_transformations():
    adapter = DecimalFieldAdapter()
    
    # Test string to Decimal conversion
    assert adapter.process(123.45) == Decimal("123.45")
    assert adapter.process(123) == Decimal("123")
    
    # Test with precision
    precision_adapter = DecimalFieldAdapter(precision=2)
    assert precision_adapter.process("123.456") == Decimal("123.46")
    
    # Test None value
    assert adapter.process(None) is None

def test_enum_transformations():
    from enum import Enum
    
    class TestEnum(Enum):
        OPTION_A = "a"
        OPTION_B = "b"
    
    adapter = EnumFieldAdapter(enum_class=TestEnum)
    
    # Test valid enum values
    assert adapter.process("a") == TestEnum.OPTION_A
    assert adapter.process("b") == TestEnum.OPTION_B
    
    # Test case insensitivity
    case_insensitive = EnumFieldAdapter(enum_class=TestEnum, case_sensitive=False)
    assert case_insensitive.process("A") == TestEnum.OPTION_A
    
    # Test invalid enum value
    with pytest.raises(ValueError):
        adapter.process("c")

def test_mapped_enum_transformations():
    from enum import Enum
    
    class TestEnum(Enum):
        OPTION_A = "a"
        OPTION_B = "b"
        
    mapping = {"option_a": "a", "option_b": "b", "alt_a": "a"}
    adapter = MappedEnumFieldAdapter(enum_class=TestEnum, mapping=mapping)
    
    # Test mapped values
    assert adapter.process("option_a") == TestEnum.OPTION_A
    assert adapter.process("option_b") == TestEnum.OPTION_B
    assert adapter.process("alt_a") == TestEnum.OPTION_A
    
    # Test unmapped value
    with pytest.raises(ValueError):
        adapter.process("unknown")

def test_composite_transformations():
    # Test a composite adapter that combines date and string operations
    transforms = [
        AdapterTransform("split", "-"),
        AdapterTransform("get_index", 0),
        AdapterTransform("to_int")
    ]
    
    adapter = CompositeFieldAdapter(transformations=transforms)
    
    # Extract year from a date string
    assert adapter.process("2023-01-15") == 2023
    
    # Test with a date object
    test_date = date(2023, 1, 15)
    date_adapter = CompositeFieldAdapter([
        AdapterTransform("to_isoformat"),  # Convert date to string
        AdapterTransform("split", "-"),
        AdapterTransform("get_index", 0),
        AdapterTransform("to_int")
    ])
    assert date_adapter.process(test_date) == 2023

def test_chained_transformations():
    factory = SchemaAdapterFactory()
    
    # Create a chain of adapters: string -> date -> fiscal year
    date_adapter = DateFieldAdapter()
    fiscal_adapter = DateFieldAdapter(fiscal_year=True)
    
    # Chain the adapters
    chain = factory.chain([date_adapter, fiscal_adapter])
    
    # Test the chain with a string date
    assert chain.process("2023-10-01") == 2024
    assert chain.process("2023-09-30") == 2023
    
    # Test with a date object
    assert chain.process(date(2023, 10, 1)) == 2024

def test_error_handling():
    date_adapter = DateFieldAdapter()
    
    # Test with invalid date format
    with pytest.raises(ValueError):
        date_adapter.process("invalid-date")
    
    # Test with invalid date string
    with pytest.raises(ValueError):
        date_adapter.process("2023-13-45")  # Invalid month and day
    
    decimal_adapter = DecimalFieldAdapter()
    
    # Test with invalid decimal
    with pytest.raises(ValueError):
        decimal_adapter.process("not-a-number")

@pytest.mark.parametrize("transformation, config, expected", [
    ("uppercase", "test", "TEST"),
    ("lowercase", "TEST", "test"),
    ("trim", " test ", "test"),
    ("strip_characters", "$1,234", "1234"),
    ("pad_left", "123", "00123"),
    ("truncate", "12345", "123"),
    ("normalize_whitespace", "test  string", "test string"),
    ("replace_chars", "test", "TesT"),
])
def test_basic_transformations(transformation, config, expected):
    adapter = CompositeFieldAdapter(transformations=[
        AdapterTransform(transformation, config if transformation not in ["uppercase", "lowercase", "trim", "normalize_whitespace"] else None)
    ])
    
    # Special cases for transformations that don't need config
    if transformation == "pad_left":
        adapter = CompositeFieldAdapter(transformations=[AdapterTransform(transformation, 5, "0")])
    elif transformation == "replace_chars":
        adapter = CompositeFieldAdapter(transformations=[AdapterTransform(transformation, {"t": "T", "t": "T"})])
    elif transformation == "truncate":
        adapter = CompositeFieldAdapter(transformations=[AdapterTransform(transformation, 3)])
    
    result = adapter.process(config)
    assert result == expected

def test_dictionary_initialization():
    """Test initializing Dictionary with configuration."""
    config = {
        'field_properties': {
            'test_field': {
                'type': 'string',
                'description': 'Test field',
                'required': True,
                'is_key': False,
                'validation': {
                    'rules': ['min_length:3'],
                    'groups': ['basic']
                },
                'transformation': {
                    'operations': [
                        {'type': 'trim'},
                        {'type': 'uppercase'}
                    ]
                }
            }
        }
    }
    
    dictionary = Dictionary(config)
    
    # Check field definition
    field = dictionary.get_field('test_field')
    assert field is not None
    assert field.type == 'string'
    assert field.description == 'Test field'
    assert field.is_required
    assert not field.is_key
    assert field.validation_rules == ['min_length:3']
    assert field.groups == ['basic']
    assert len(field.transformations) == 2
    
    # Check adapter creation
    assert 'test_field' in dictionary.adapters

def test_field_validation():
    """Test field validation functionality."""
    config = {
        'field_properties': {
            'amount': {
                'type': 'decimal',
                'validation': {
                    'rules': ['min_value:0', 'max_value:1000000']
                }
            }
        }
    }
    
    dictionary = Dictionary(config)
    
    # Test valid value
    assert not dictionary.validate_field('amount', 500.00)
    
    # Test invalid value
    errors = dictionary.validate_field('amount', -100.00)
    assert errors
    assert any('min_value' in error for error in errors)

def test_field_transformation():
    """Test field transformation functionality."""
    config = {
        'field_properties': {
            'code': {
                'type': 'string',
                'transformation': {
                    'operations': [
                        {'type': 'trim'},
                        {'type': 'uppercase'}
                    ]
                }
            }
        }
    }
    
    dictionary = Dictionary(config)
    
    # Test transformation
    result = dictionary.transform_field('code', ' abc123 ')
    assert result == 'ABC123'

def test_dictionary_from_csv():
    """Test creating Dictionary from CSV file."""
    config = {'field_properties': {}}
    
    # Create temporary CSV file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
        f.write('field_name,type,description,required,is_key\n')
        f.write('id,string,Unique identifier,true,true\n')
        f.write('name,string,Entity name,true,false\n')
        temp_path = Path(f.name)
    
    try:
        # Create dictionary from CSV
        dictionary = Dictionary.from_csv(temp_path, config)
        
        # Check fields loaded from CSV
        assert len(dictionary.fields) == 2
        
        id_field = dictionary.get_field('id')
        assert id_field.type == 'string'
        assert id_field.description == 'Unique identifier'
        assert id_field.is_required
        assert id_field.is_key
        
        # Check key fields
        key_fields = dictionary.get_key_fields()
        assert len(key_fields) == 1
        assert 'id' in key_fields
        
        # Check required fields
        required_fields = dictionary.get_required_fields()
        assert len(required_fields) == 2
        assert 'id' in required_fields
        assert 'name' in required_fields
        
    finally:
        temp_path.unlink()

def test_field_groups():
    """Test field group functionality."""
    config = {
        'field_properties': {
            'amount': {
                'type': 'decimal',
                'validation': {
                    'groups': ['monetary', 'summary']
                }
            },
            'total': {
                'type': 'decimal',
                'validation': {
                    'groups': ['monetary', 'required']
                }
            }
        }
    }
    
    dictionary = Dictionary(config)
    
    # Test getting fields by group
    monetary_fields = dictionary.get_fields_by_group('monetary')
    assert len(monetary_fields) == 2
    assert 'amount' in monetary_fields
    assert 'total' in monetary_fields
    
    summary_fields = dictionary.get_fields_by_group('summary')
    assert len(summary_fields) == 1
    assert 'amount' in summary_fields

def test_dictionary_to_json():
    """Test saving Dictionary to JSON file."""
    config = {
        'field_properties': {
            'test_field': {
                'type': 'string',
                'description': 'Test field',
                'validation': {
                    'rules': ['required'],
                    'groups': ['basic']
                }
            }
        }
    }
    
    dictionary = Dictionary(config)
    
    # Save to temporary JSON file
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        temp_path = Path(f.name)
    
    try:
        dictionary.to_json(temp_path)
        
        # Read and verify JSON
        with open(temp_path) as f:
            import json
            data = json.load(f)
        
        assert 'fields' in data
        assert 'test_field' in data['fields']
        assert data['fields']['test_field']['type'] == 'string'
        assert data['fields']['test_field']['description'] == 'Test field'
        
    finally:
        temp_path.unlink()