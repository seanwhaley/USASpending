"""Tests for schema adapter implementations."""
import re
from typing import Dict, Any, List
from decimal import Decimal
from datetime import datetime, date
from marshmallow import Schema, fields
from pydantic import BaseModel

from usaspending.schema_adapters import (
    SchemaAdapterFactory, AdapterTransform,
    DateFieldAdapter, DecimalFieldAdapter,
    StringAdapter, NumericAdapter, DateAdapter,
    BooleanAdapter, EnumAdapter, ListAdapter,
    DictAdapter, PydanticAdapter, MarshmallowAdapter,
    BaseSchemaAdapter, CompositeFieldAdapter,
    AdapterError
)

import pytest

from conftest import TestEnum

@pytest.fixture
def string_adapter():
    """Create string adapter for testing."""
    return StringAdapter(min_length=2, max_length=5, pattern=r'^[a-z]+$')

@pytest.fixture
def numeric_adapter():
    """Create numeric adapter for testing."""
    return NumericAdapter(min_value=0, max_value=100)

@pytest.fixture
def date_adapter():
    """Create date adapter for testing."""
    return DateAdapter(formats=['%Y-%m-%d', '%d/%m/%Y'])

@pytest.fixture
def composite_adapter():
    """Create composite adapter for testing."""
    return CompositeFieldAdapter('test_field', [str.strip, str.upper])

def test_string_adapter(string_adapter):
    """Test string adapter validation and transformation."""
    # Test valid strings
    assert string_adapter.validate_field("test")
    assert string_adapter.validate_field("Testing") is False  # Too long
    assert string_adapter.validate_field("a") is False  # Too short
    assert string_adapter.validate_field("test123") is False  # Invalid pattern
    
    # Test transformation
    assert string_adapter.transform_field(" test ") == "test"
    assert string_adapter.transform_field(None) is None
    
    # Test non-string input
    assert string_adapter.transform_field(123) == "123"
    
    # Test with no pattern
    simple_adapter = StringAdapter()
    assert simple_adapter.validate_field("any string is valid")
    assert simple_adapter.validate_field(None)

def test_numeric_adapter(numeric_adapter):
    """Test numeric adapter validation and transformation."""
    # Test valid numbers
    assert numeric_adapter.validate_field(50)
    assert numeric_adapter.validate_field("75.5")
    assert numeric_adapter.validate_field(-1) is False
    assert numeric_adapter.validate_field(150) is False
    
    # Test transformation
    assert numeric_adapter.transform_field("123.456") == 123.456
    assert numeric_adapter.transform_field(None) is None
    
    # Test float vs decimal mode
    float_adapter = NumericAdapter(decimal=False)
    result = float_adapter.transform_field("123.456")
    assert isinstance(result, float)
    assert result == 123.456
    
    # Test precision validation
    precise_adapter = NumericAdapter(precision=2, decimal=True)
    assert precise_adapter.validate_field("123.45")
    assert precise_adapter.validate_field("123.456") is False  # Too many decimals
    
    # Test handling invalid input
    assert numeric_adapter.validate_field("not a number") is False
    assert numeric_adapter.transform_field("not a number") is None

def test_date_adapter(date_adapter):
    """Test date adapter validation and transformation."""
    # Test valid dates
    assert date_adapter.validate_field("2024-03-15")
    assert date_adapter.validate_field("15/03/2024")
    assert date_adapter.validate_field("invalid") is False
    
    # Test transformation
    result = date_adapter.transform_field("2024-03-15")
    assert isinstance(result, date)
    assert result == date(2024, 3, 15)
    
    # Test with min/max date constraints
    constrained_adapter = DateAdapter(
        formats=['%Y-%m-%d'],
        min_date=date(2023, 1, 1),
        max_date=date(2023, 12, 31)
    )
    assert constrained_adapter.validate_field("2023-06-15")
    assert constrained_adapter.validate_field("2022-12-31") is False  # Too early
    assert constrained_adapter.validate_field("2024-01-01") is False  # Too late
    
    # Test with output_format
    formatted_adapter = DateAdapter(formats=['%Y-%m-%d'], output_format='%m/%d/%Y')
    result = formatted_adapter.transform_field("2023-12-25")
    assert result == "12/25/2023"
    
    # Test with datetime input
    now = datetime.now()
    assert date_adapter.validate_field(now)
    result = date_adapter.transform_field(now)
    assert result == now.date()
    
    # Test with different date format combinations
    assert date_adapter._parse_date("2024-03-15") == date(2024, 3, 15)
    assert date_adapter._parse_date("15/03/2024") == date(2024, 3, 15)
    assert date_adapter._parse_date("invalid date") is None

def test_boolean_adapter():
    """Test boolean adapter validation and transformation."""
    adapter = BooleanAdapter()
    
    # Test validation
    assert adapter.validate_field(True)
    assert adapter.validate_field("yes")
    assert adapter.validate_field("no")
    assert adapter.validate_field("invalid") is False
    assert adapter.validate_field(None)  # None is valid by default
    
    # Test transformation
    assert adapter.transform_field("yes") is True
    assert adapter.transform_field("no") is False
    assert adapter.transform_field("Y") is True
    assert adapter.transform_field("N") is False
    assert adapter.transform_field("1") is True
    assert adapter.transform_field("0") is False
    assert adapter.transform_field("invalid") is None
    assert adapter.transform_field(None) is None
    
    # Test with boolean input
    assert adapter.transform_field(True) is True
    assert adapter.transform_field(False) is False
    
    # Test case sensitivity
    assert adapter.transform_field("YES") is True
    assert adapter.transform_field("NO") is False

def test_enum_adapter():
    """Test enum adapter validation and transformation."""
    adapter = EnumAdapter('test_field', TestEnum)
    
    # Test validation
    assert adapter.validate_field("a")
    assert adapter.validate_field("b")
    assert adapter.validate_field("c") is False
    
    # Test transformation
    assert adapter.transform_field("a") == TestEnum.OPTION_A
    assert adapter.transform_field("invalid") is None
    
    # Test case sensitivity
    case_adapter = EnumAdapter('test_field', TestEnum, case_sensitive=True)
    assert case_adapter.validate_field("a")
    assert case_adapter.validate_field("A") is False
    
    # Test non-case-sensitivity
    non_case_adapter = EnumAdapter('test_field', TestEnum, case_sensitive=False)
    assert non_case_adapter.validate_field("a")
    assert non_case_adapter.validate_field("A")
    
    # Test required field
    required_adapter = EnumAdapter('test_field', TestEnum, required=True)
    assert required_adapter.validate_field("a")
    assert required_adapter.validate_field(None) is False
    assert "required" in required_adapter.errors[0]

def test_list_adapter():
    """Test list adapter validation and transformation."""
    string_adapter = StringAdapter()
    adapter = ListAdapter(string_adapter, min_items=1, max_items=3)
    
    # Test validation
    assert adapter.validate_field(["test"])
    assert adapter.validate_field([]) is False  # Too few items
    assert adapter.validate_field(["a", "b", "c", "d"]) is False  # Too many items
    
    # Test transformation
    assert adapter.transform_field(["test", " example "]) == ["test", "example"]
    assert adapter.transform_field(None) is None
    
    # Test nested validation
    assert adapter.validate_field(["test", "example", "valid"])
    
    # Test non-list input
    assert adapter.validate_field("not a list") is False
    assert "Expected list" in adapter.errors[0]
    assert adapter.transform_field("not a list") is None
    
    # Test with item validation failures
    numeric_adapter = NumericAdapter(min_value=0)
    numeric_list_adapter = ListAdapter(numeric_adapter)
    assert numeric_list_adapter.validate_field([1, 2, 3])
    assert numeric_list_adapter.validate_field([1, -2, 3]) is False
    assert len(numeric_list_adapter.errors) > 0
    
    # Test without min/max constraints
    simple_adapter = ListAdapter(string_adapter)
    assert simple_adapter.validate_field([])
    assert simple_adapter.validate_field(["a", "b", "c", "d", "e"])

def test_dict_adapter():
    """Test dictionary adapter validation and transformation."""
    field_adapters = {
        'name': StringAdapter(),
        'age': NumericAdapter(min_value=0, max_value=150),
        'tags': ListAdapter(StringAdapter())
    }
    adapter = DictAdapter(field_adapters, required_fields=['name'])
    
    # Test validation
    assert adapter.validate_field({'name': 'Test', 'age': 25})
    assert adapter.validate_field({'age': 25}) is False  # Missing required field
    assert "Missing required fields" in adapter.errors[0]
    
    # Test transformation with nested structures
    result = adapter.transform_field({
        'name': ' Test ',
        'age': '25',
        'tags': ['tag1', ' tag2 ']
    })
    assert result == {
        'name': 'Test',
        'age': 25.0,
        'tags': ['tag1', 'tag2']
    }
    
    # Test transformation keeping additional fields
    result = adapter.transform_field({
        'name': 'Test',
        'age': 25,
        'extra': 'value'
    })
    assert 'extra' in result
    
    # Test transformation with additional fields disabled
    strict_adapter = DictAdapter(field_adapters, required_fields=['name'], additional_fields=False)
    assert strict_adapter.validate_field({'name': 'Test', 'extra': 'value'}) is False
    assert "Unknown fields not allowed" in strict_adapter.errors[0]
    
    # Test non-dict input
    assert adapter.validate_field("not a dict") is False
    assert adapter.transform_field("not a dict") is None
    
    # Test with nested field validation failures
    assert not adapter.validate_field({'name': 'Test', 'age': -5})
    assert len(adapter.errors) > 0

def test_composite_adapter(composite_adapter):
    """Test composite adapter chained transformations."""
    # Test validation
    assert composite_adapter.validate_field("test")
    assert composite_adapter.validate_field(None)
    
    # Test transformation
    assert composite_adapter.transform_field(" test ") == "TEST"
    assert composite_adapter.transform_field(None) is None
    
    # Test required field
    required_adapter = CompositeFieldAdapter('test_field', [str.upper], required=True)
    assert required_adapter.validate_field("test")
    assert required_adapter.validate_field(None) is False
    
    # Test failing transformation
    def failing_transform(x):
        raise ValueError("Test error")
        
    error_adapter = CompositeFieldAdapter('test_field', [failing_transform])
    assert not error_adapter.validate_field("test")
    assert len(error_adapter.errors) > 0
    assert error_adapter.transform_field("test") is None

def test_pydantic_adapter():
    """Test Pydantic model adapter."""
    class TestModel(BaseModel):
        name: str
        age: int
    
    adapter = PydanticAdapter('person', TestModel)
    
    # Test validation
    valid_data = {'person': {'name': 'Test', 'age': 25}}
    invalid_data = {'person': {'name': 'Test', 'age': 'invalid'}}
    
    assert not adapter.validate(valid_data)  # No validation errors
    assert adapter.validate(invalid_data)  # Has validation errors
    
    # Test transformation
    result = adapter.transform(valid_data)
    assert result == {'name': 'Test', 'age': 25}
    
    # Test with missing field
    missing_data = {'other_field': 'value'}
    assert adapter.validate(missing_data) == []  # Not required by default
    assert adapter.transform(missing_data) is None
    
    # Test with required field
    required_adapter = PydanticAdapter('person', TestModel, required=True)
    assert required_adapter.validate(missing_data) == ["Required field 'person' is missing"]

def test_marshmallow_adapter():
    """Test Marshmallow schema adapter."""
    class TestSchema(Schema):
        name = fields.String(required=True)
        age = fields.Integer()
        email = fields.Email()
    
    adapter = MarshmallowAdapter('person', TestSchema)
    
    # Test validation
    valid_data = {'person': {'name': 'Test', 'age': 25}}
    invalid_data = {'person': {'age': 25}}  # Missing required name
    bad_email_data = {'person': {'name': 'Test', 'email': 'not-an-email'}}
    
    assert not adapter.validate(valid_data)  # No validation errors
    assert adapter.validate(invalid_data)  # Has validation errors
    assert adapter.validate(bad_email_data)  # Has validation errors
    assert "not a valid email" in adapter.validate(bad_email_data)[0].lower()
    
    # Test transformation
    result = adapter.transform(valid_data)
    assert result == {'name': 'Test', 'age': 25}
    
    # Test with missing field
    missing_data = {'other_field': 'value'}
    assert adapter.validate(missing_data) == []  # Not required by default
    assert adapter.transform(missing_data) is None
    
    # Test with required field
    required_adapter = MarshmallowAdapter('person', TestSchema, required=True)
    assert required_adapter.validate(missing_data) == ["Required field 'person' is missing"]
    
    # Test with exception in schema
    class BuggySchema(Schema):
        def dump(self, data):
            raise Exception("Schema dump error")
            
    buggy_adapter = MarshmallowAdapter('person', BuggySchema)
    assert buggy_adapter.transform({'person': {'name': 'Test'}}) is None

def test_date_field_adapter():
    """Test date field adapter."""
    adapter = DateFieldAdapter('test_date', ['%Y-%m-%d'])
    
    # Test validation
    assert adapter.validate_field('2024-03-15')
    assert adapter.validate_field('invalid') is False
    
    # Test transformation
    result = adapter.transform_field('2024-03-15')
    assert isinstance(result, date)
    assert result == date(2024, 3, 15)
    
    # Test with min/max constraints
    constrained = DateFieldAdapter(
        'test_date', 
        ['%Y-%m-%d'], 
        min_date=date(2020, 1, 1), 
        max_date=date(2025, 12, 31)
    )
    assert constrained.validate_field('2023-01-01')
    assert constrained.validate_field('2019-01-01') is False
    assert constrained.validate_field('2026-01-01') is False
    
    # Test required field
    required_adapter = DateFieldAdapter('test_date', ['%Y-%m-%d'], required=True)
    assert required_adapter.validate_field('2023-01-01')
    assert required_adapter.validate_field(None) is False
    
    # Test with invalid types
    assert not adapter.validate_field(123)
    assert "Could not parse date" in adapter.errors[0]

def test_decimal_field_adapter():
    """Test decimal field adapter."""
    adapter = DecimalFieldAdapter('amount', precision=2)
    
    # Test validation
    assert adapter.validate_field('123.45')
    assert adapter.validate_field('123.456') is False  # Too many decimal places
    
    # Test transformation
    result = adapter.transform_field('123.456')
    assert isinstance(result, Decimal)
    assert result == Decimal('123.46')  # Rounds to 2 decimal places

    # Test with min/max constraints
    constrained = DecimalFieldAdapter(
        'amount',
        min_value=Decimal('10.0'),
        max_value=Decimal('100.0')
    )
    assert constrained.validate_field('50.0')
    assert constrained.validate_field('5.0') is False
    assert constrained.validate_field('200.0') is False

def test_adapter_factory():
    """Test adapter factory for creating different adapters."""
    factory = SchemaAdapterFactory()
    
    # Test creating string adapter
    string_adapter = factory.create_adapter('string', min_length=2, max_length=10)
    assert isinstance(string_adapter, StringAdapter)
    assert string_adapter.min_length == 2
    assert string_adapter.max_length == 10
    
    # Test creating numeric adapter
    numeric_adapter = factory.create_adapter('numeric', min_value=0, max_value=100)
    assert isinstance(numeric_adapter, NumericAdapter)
    assert numeric_adapter.min_value == 0
    assert numeric_adapter.max_value == 100
    
    # Test creating date adapter
    date_adapter = factory.create_adapter('date', formats=['%Y-%m-%d'])
    assert isinstance(date_adapter, DateAdapter)
    assert date_adapter.formats == ['%Y-%m-%d']
    
    # Test creating boolean adapter
    bool_adapter = factory.create_adapter('boolean')
    assert isinstance(bool_adapter, BooleanAdapter)
    
    # Test creating list adapter
    list_adapter = factory.create_adapter('list', item_adapter=string_adapter)
    assert isinstance(list_adapter, ListAdapter)
    assert list_adapter.item_adapter == string_adapter
    
    # Test unknown adapter type
    with pytest.raises(ValueError) as exc:
        factory.create_adapter('unknown')
    assert "Unknown adapter type" in str(exc.value)

@pytest.mark.parametrize("transformation_type,input_value,expected,config", [
    ("uppercase", "test", "TEST", {}),
    ("lowercase", "TEST", "test", {}),
    ("trim", " test ", "test", {}),
    ("strip_characters", "$1,234", "1234", "$,"),
    ("pad_left", "123", "00123", {"length": 5}),
    ("truncate", "12345", "123", {"length": 3}),
    ("normalize_whitespace", "test  string", "test string", {}),
    ("split", "a,b,c", ["a", "b", "c"], ","),
    ("get_index", ["a", "b", "c"], "b", 1),
    ("to_int", "123", 123, {}),
    ("to_isoformat", date(2023, 1, 1), "2023-01-01", {}),
])
def test_adapter_transform(transformation_type, input_value, expected, config):
    """Test different adapter transformations."""
    transform = AdapterTransform(type=transformation_type, config=config)
    result = transform(input_value)
    assert result == expected

def test_adapter_transform_failures():
    """Test handling of transformation failures."""
    # Test with invalid transformation type
    with pytest.raises(ValueError) as exc:
        transform = AdapterTransform(type="not_a_transform")
        transform("test")
    assert "Unknown transformation type" in str(exc.value)
    
    # Test with failing transformation
    transform = AdapterTransform(type="get_index", config=5)
    result = transform(["a", "b"])  # Index out of range
    assert result is None
    
    # Test with type conversion error
    transform = AdapterTransform(type="to_int")
    result = transform("not a number")
    assert result is None

def test_adapter_transform_none_handling():
    """Test handling of None values in transformations."""
    # All transformations should return None when input is None
    for transform_type in ["uppercase", "lowercase", "trim", "split"]:
        transform = AdapterTransform(type=transform_type)
        assert transform(None) is None

def test_error_handling():
    """Test adapter error collection and clearing."""
    adapter = StringAdapter(min_length=5)
    
    # Generate validation errors
    adapter.validate_field("abc")
    assert len(adapter.errors) > 0
    
    # Clear errors
    adapter.clear_cache()
    assert len(adapter.errors) == 0

def test_adapter_chaining():
    """Test chaining multiple adapters together."""
    # Create a chain: string → uppercase → truncate
    string_adapter = StringAdapter(strip=True)
    
    def uppercase(value):
        return value.upper() if value else value
        
    def truncate(value):
        return value[:3] if value else value
    
    composite = CompositeFieldAdapter('test', [
        string_adapter.transform_field,
        uppercase,
        truncate
    ])
    
    result = composite.transform_field("  hello world  ")
    assert result == "HEL"  # Stripped, uppercased, truncated

def test_adapter_error_messages():
    """Test specific error messages from adapters."""
    # String adapter errors
    adapter = StringAdapter(min_length=5, max_length=10, pattern=r'^[A-Z]+$')
    adapter.validate_field("abc")
    assert "length" in adapter.errors[0] and "minimum" in adapter.errors[0]
    
    adapter.validate_field("abcdefghijklm")
    assert "length" in adapter.errors[0] and "exceeds maximum" in adapter.errors[0]
    
    adapter.validate_field("abc123")
    assert "pattern" in adapter.errors[0]
    
    # Numeric adapter errors
    num_adapter = NumericAdapter(min_value=10, max_value=20)
    num_adapter.validate_field(5)
    assert "less than minimum" in num_adapter.errors[0]
    
    num_adapter.validate_field(25)
    assert "exceeds maximum" in num_adapter.errors[0]
    
    # Date adapter errors
    date_adapter = DateAdapter(
        formats=['%Y-%m-%d'],
        min_date=date(2023, 1, 1),
        max_date=date(2023, 12, 31)
    )
    date_adapter.validate_field("2022-01-01")
    assert "before minimum" in date_adapter.errors[0]
    
    date_adapter.validate_field("2024-01-01")
    assert "after maximum" in date_adapter.errors[0]

def test_adapter_cache_clearing():
    """Test clearing adapter caches."""
    adapter = StringAdapter(min_length=5)
    adapter.validate_field("abc")  # Will generate errors
    assert len(adapter.errors) > 0
    
    adapter.clear_cache()
    assert len(adapter.errors) == 0
    
    # Test complex adapter
    dict_adapter = DictAdapter({
        'name': StringAdapter(min_length=3),
        'age': NumericAdapter(min_value=18)
    })
    dict_adapter.validate_field({'name': 'a', 'age': 15})
    assert len(dict_adapter.errors) > 0
    
    dict_adapter.clear_cache()
    assert len(dict_adapter.errors) == 0

def test_multi_type_validation():
    """Test validation of fields that accept multiple types."""
    # Create an adapter that validates either strings or numbers
    class MultiTypeAdapter(BaseSchemaAdapter):
        def validate_field(self, value):
            self.errors.clear()
            if value is None:
                return True
                
            if not isinstance(value, (str, int, float)):
                self.errors.append(f"Expected string or number, got {type(value)}")
                return False
            return True
            
        def transform_field(self, value):
            return value
            
    adapter = MultiTypeAdapter()
    assert adapter.validate_field("string")
    assert adapter.validate_field(123)
    assert adapter.validate_field(45.6)
    assert adapter.validate_field(None)
    assert not adapter.validate_field([])
    assert "Expected string or number" in adapter.errors[0]

def test_nested_validation_errors():
    """Test error collection in nested adapters."""
    # Create a nested structure
    string_adapter = StringAdapter(min_length=3)
    list_adapter = ListAdapter(string_adapter)
    dict_adapter = DictAdapter({
        'items': list_adapter,
        'name': string_adapter
    })
    
    # Test with nested validation failures
    result = dict_adapter.validate_field({
        'name': 'ok',
        'items': ['ok', 'a']  # 'a' is too short
    })
    
    assert result is False
    assert len(dict_adapter.errors) > 0
    assert "length" in dict_adapter.errors[0]

def test_validation_errors_inheritance():
    """Test inheritance of validation errors from field to adapter."""
    # Create an adapter that uses another adapter
    string_adapter = StringAdapter(min_length=3)
    composite = CompositeFieldAdapter('test', [string_adapter.transform_field])
    
    # Generate errors in the inner adapter
    string_adapter.validate_field('a')  # Too short
    assert len(string_adapter.errors) > 0
    
    # Error should not propagate automatically
    assert len(composite.errors) == 0
    
    # But validation should fail if called directly
    assert composite.validate_field('a') is False
    assert len(composite.errors) > 0
