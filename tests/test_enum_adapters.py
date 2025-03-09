"""Tests for the enum_adapters module."""
import pytest
from enum import Enum
from usaspending.enum_adapters import EnumFieldAdapter, MappedEnumFieldAdapter


class TestEnum(Enum):
    """Sample enum for testing."""
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


@pytest.fixture
def basic_enum_adapter():
    """Create a basic enum adapter with case-sensitive values."""
    return EnumFieldAdapter(['Red', 'Green', 'Blue'], case_sensitive=True)


@pytest.fixture
def case_insensitive_enum_adapter():
    """Create a case-insensitive enum adapter."""
    return EnumFieldAdapter(['Red', 'Green', 'Blue'], case_sensitive=False)


@pytest.fixture
def mapped_enum_adapter():
    """Create a mapped enum adapter."""
    return MappedEnumFieldAdapter({
        'r': 'Red',
        'g': 'Green',
        'b': 'Blue'
    }, case_sensitive=True)


@pytest.fixture
def case_insensitive_mapped_adapter():
    """Create a case-insensitive mapped enum adapter."""
    return MappedEnumFieldAdapter({
        'Red': '#FF0000',
        'Green': '#00FF00',
        'Blue': '#0000FF'
    }, case_sensitive=False)


def test_enum_adapter_initialization():
    """Test initialization of EnumFieldAdapter."""
    # Case-sensitive initialization
    adapter = EnumFieldAdapter(['A', 'B', 'C'], case_sensitive=True)
    assert adapter.valid_values == {'A', 'B', 'C'}
    assert adapter.case_sensitive is True
    
    # Case-insensitive initialization
    adapter = EnumFieldAdapter(['A', 'B', 'C'], case_sensitive=False)
    assert adapter.valid_values == {'a', 'b', 'c'}
    assert adapter.case_sensitive is False
    
    # Mixed case initialization
    adapter = EnumFieldAdapter(['a', 'B', 'c'], case_sensitive=False)
    assert adapter.valid_values == {'a', 'b', 'c'}
    
    # With None value (should be excluded)
    adapter = EnumFieldAdapter(['A', None, 'C'], case_sensitive=True)
    assert adapter.valid_values == {'A', 'C'}
    
    # Empty adapter
    adapter = EnumFieldAdapter([], case_sensitive=True)
    assert adapter.valid_values == set()


def test_enum_adapter_validate_case_sensitive(basic_enum_adapter):
    """Test validation with case-sensitive enum adapter."""
    adapter = basic_enum_adapter
    
    # Exact matches should validate
    assert adapter.validate('Red', 'test_field')
    assert adapter.validate('Green', 'test_field')
    assert adapter.validate('Blue', 'test_field')
    
    # Different case should fail
    assert adapter.validate('red', 'test_field') is False
    assert "not in valid values" in adapter.errors[0]
    
    adapter.errors = []  # Reset errors
    
    # Invalid values should fail
    assert adapter.validate('Yellow', 'test_field') is False
    assert "not in valid values" in adapter.errors[0]
    
    # None should pass
    assert adapter.validate(None, 'test_field')


def test_enum_adapter_validate_case_insensitive(case_insensitive_enum_adapter):
    """Test validation with case-insensitive enum adapter."""
    adapter = case_insensitive_enum_adapter
    
    # Exact matches should validate
    assert adapter.validate('Red', 'test_field')
    assert adapter.validate('Green', 'test_field')
    assert adapter.validate('Blue', 'test_field')
    
    # Different case should also validate
    assert adapter.validate('red', 'test_field')
    assert adapter.validate('GREEN', 'test_field')
    assert adapter.validate('blue', 'test_field')
    
    # Invalid values should fail
    assert adapter.validate('Yellow', 'test_field') is False
    assert "not in valid values" in adapter.errors[0]
    
    # None should pass
    assert adapter.validate(None, 'test_field')


def test_enum_adapter_validate_non_string_values(case_insensitive_enum_adapter):
    """Test validation of non-string values."""
    adapter = case_insensitive_enum_adapter
    
    # Numeric values get converted to strings
    assert adapter.validate(123, 'test_field') is False
    
    # Enum values
    assert adapter.validate(TestEnum.RED, 'test_field')
    assert TestEnum.RED.value == 'red'


def test_enum_adapter_transform_case_sensitive(basic_enum_adapter):
    """Test transformation with case-sensitive enum adapter."""
    adapter = basic_enum_adapter
    
    # Valid values should return as-is
    assert adapter.transform('Red', 'test_field') == 'Red'
    assert adapter.transform('Green', 'test_field') == 'Green'
    
    # Invalid values should return None
    assert adapter.transform('red', 'test_field') is None
    assert adapter.transform('Yellow', 'test_field') is None
    
    # None should return None
    assert adapter.transform(None, 'test_field') is None


def test_enum_adapter_transform_case_insensitive(case_insensitive_enum_adapter):
    """Test transformation with case-insensitive enum adapter."""
    adapter = case_insensitive_enum_adapter
    
    # Values with any case should return as provided
    assert adapter.transform('Red', 'test_field') == 'Red'
    assert adapter.transform('red', 'test_field') == 'red'
    assert adapter.transform('RED', 'test_field') == 'RED'
    
    # Invalid values should return None
    assert adapter.transform('Yellow', 'test_field') is None
    
    # None should return None
    assert adapter.transform(None, 'test_field') is None


def test_enum_adapter_get_validation_errors(basic_enum_adapter):
    """Test retrieving validation errors."""
    adapter = basic_enum_adapter
    
    # No errors initially
    assert adapter.get_validation_errors() == []
    
    # After validation failure
    adapter.validate('InvalidValue', 'test_field')
    errors = adapter.get_validation_errors()
    assert len(errors) == 1
    assert "Value 'InvalidValue' not in valid values" in errors[0]
    
    # Ensure the returned list is a copy, not the original
    errors.clear()
    assert len(adapter.get_validation_errors()) == 1


def test_mapped_enum_adapter_initialization():
    """Test initialization of MappedEnumFieldAdapter."""
    # Case-sensitive initialization
    mapping = {'A': 1, 'B': 2, 'C': 3}
    adapter = MappedEnumFieldAdapter(mapping, case_sensitive=True)
    assert adapter.valid_values == {'A', 'B', 'C'}
    assert adapter.mapping == mapping
    
    # Case-insensitive initialization
    adapter = MappedEnumFieldAdapter(mapping, case_sensitive=False)
    assert adapter.valid_values == {'a', 'b', 'c'}
    assert adapter.mapping == {'a': 1, 'b': 2, 'c': 3}


def test_mapped_enum_adapter_validate(mapped_enum_adapter):
    """Test validation with mapped enum adapter."""
    adapter = mapped_enum_adapter
    
    # Keys in the mapping should validate
    assert adapter.validate('r', 'test_field')
    assert adapter.validate('g', 'test_field')
    assert adapter.validate('b', 'test_field')
    
    # Values in the mapping should not validate
    assert adapter.validate('Red', 'test_field') is False
    
    # Invalid keys should not validate
    assert adapter.validate('y', 'test_field') is False


def test_mapped_enum_adapter_validate_case_insensitive(case_insensitive_mapped_adapter):
    """Test validation with case-insensitive mapped enum adapter."""
    adapter = case_insensitive_mapped_adapter
    
    # Keys with any case should validate
    assert adapter.validate('Red', 'test_field')
    assert adapter.validate('red', 'test_field')
    assert adapter.validate('RED', 'test_field')
    assert adapter.validate('Green', 'test_field')
    assert adapter.validate('green', 'test_field')
    
    # Values should not validate
    assert adapter.validate('#FF0000', 'test_field') is False
    
    # Invalid keys should not validate
    assert adapter.validate('Yellow', 'test_field') is False


def test_mapped_enum_adapter_transform(mapped_enum_adapter):
    """Test transformation with mapped enum adapter."""
    adapter = mapped_enum_adapter
    
    # Valid keys should transform to their mapped values
    assert adapter.transform('r', 'test_field') == 'Red'
    assert adapter.transform('g', 'test_field') == 'Green'
    assert adapter.transform('b', 'test_field') == 'Blue'
    
    # Invalid keys should return None
    assert adapter.transform('y', 'test_field') is None
    
    # None should return None
    assert adapter.transform(None, 'test_field') is None


def test_mapped_enum_adapter_transform_case_insensitive(case_insensitive_mapped_adapter):
    """Test transformation with case-insensitive mapped enum adapter."""
    adapter = case_insensitive_mapped_adapter
    
    # Keys with any case should transform to their mapped values
    assert adapter.transform('Red', 'test_field') == '#FF0000'
    assert adapter.transform('red', 'test_field') == '#FF0000'
    assert adapter.transform('RED', 'test_field') == '#FF0000'
    assert adapter.transform('Green', 'test_field') == '#00FF00'
    assert adapter.transform('blue', 'test_field') == '#0000FF'
    
    # Invalid keys should return None
    assert adapter.transform('Yellow', 'test_field') is None
    
    # None should return None
    assert adapter.transform(None, 'test_field') is None


def test_mapped_enum_adapter_handles_non_string_values():
    """Test mapped enum adapter with non-string values."""
    # Numeric values in mapping
    adapter = MappedEnumFieldAdapter({
        '1': 'One',
        '2': 'Two',
        '3': 'Three'
    })
    
    # String representation of numbers should work
    assert adapter.transform('1', 'test_field') == 'One'
    assert adapter.transform('2', 'test_field') == 'Two'
    
    # Actual numbers should also work (converted to string)
    assert adapter.transform(1, 'test_field') == 'One'
    assert adapter.transform(2, 'test_field') == 'Two'


def test_complex_value_mapping():
    """Test with complex output values in the mapping."""
    # Using dictionaries as mapped values
    adapter = MappedEnumFieldAdapter({
        'red': {'hex': '#FF0000', 'rgb': (255, 0, 0)},
        'green': {'hex': '#00FF00', 'rgb': (0, 255, 0)},
        'blue': {'hex': '#0000FF', 'rgb': (0, 0, 255)}
    })
    
    # Test that complex mapped values are returned correctly
    red_value = adapter.transform('red', 'test_field')
    assert red_value['hex'] == '#FF0000'
    assert red_value['rgb'] == (255, 0, 0)
    
    green_value = adapter.transform('green', 'test_field')
    assert green_value['hex'] == '#00FF00'
    assert green_value['rgb'] == (0, 255, 0)


def test_empty_string_handling():
    """Test handling of empty strings in enum adapters."""
    # Test with empty string in valid values
    adapter = EnumFieldAdapter(['', 'A', 'B'], case_sensitive=True)
    assert adapter.validate('', 'test_field')
    assert adapter.transform('', 'test_field') == ''
    
    # Test with empty string input on adapter without empty string as valid value
    adapter = EnumFieldAdapter(['A', 'B'], case_sensitive=True)
    assert not adapter.validate('', 'test_field')
    assert adapter.transform('', 'test_field') is None


def test_whitespace_handling():
    """Test handling of whitespace in enum values."""
    # Test with whitespace values
    adapter = EnumFieldAdapter([' A ', 'B ', ' C'], case_sensitive=True)
    assert adapter.validate(' A ', 'test_field')
    assert adapter.validate('B ', 'test_field')
    assert adapter.transform(' A ', 'test_field') == ' A '
    
    # Test with case insensitive and whitespace
    adapter = EnumFieldAdapter([' A ', 'B ', ' C'], case_sensitive=False)
    assert adapter.validate(' a ', 'test_field')
    assert adapter.validate('b ', 'test_field')


def test_error_message_formatting():
    """Test the formatting of error messages."""
    adapter = EnumFieldAdapter(['Red', 'Green', 'Blue'], case_sensitive=True)
    adapter.validate('Yellow', 'color_field')
    errors = adapter.get_validation_errors()
    assert len(errors) == 1
    assert 'color_field' in errors[0]
    assert 'Yellow' in errors[0]
    assert 'Red, Green, Blue' in errors[0]


def test_mapped_enum_adapter_with_special_characters():
    """Test mapped enum adapter with special characters in keys and values."""
    adapter = MappedEnumFieldAdapter({
        'key-with-dash': 'value-with-dash',
        'key_with_underscore': 'value_with_underscore',
        'key.with.dots': 'value.with.dots',
        'key@with@symbols': 'value@with@symbols'
    })
    
    assert adapter.validate('key-with-dash', 'test_field')
    assert adapter.transform('key-with-dash', 'test_field') == 'value-with-dash'
    assert adapter.validate('key.with.dots', 'test_field')
    assert adapter.transform('key.with.dots', 'test_field') == 'value.with.dots'


def test_mapped_enum_adapter_error_preservation():
    """Test that mapped enum adapter preserves error messages across multiple validations."""
    adapter = MappedEnumFieldAdapter({'valid': 'mapped'})
    
    # First validation failure
    assert not adapter.validate('invalid1', 'field1')
    first_error = adapter.get_validation_errors()[0]
    
    # Second validation failure
    assert not adapter.validate('invalid2', 'field2')
    errors = adapter.get_validation_errors()
    
    # Should have both errors
    assert len(errors) == 2
    assert first_error in errors
    assert any('invalid2' in err for err in errors)


def test_enum_adapter_with_unicode():
    """Test enum adapter with Unicode characters."""
    adapter = EnumFieldAdapter(['é', 'ñ', '漢字'], case_sensitive=True)
    
    assert adapter.validate('é', 'test_field')
    assert adapter.validate('漢字', 'test_field')
    assert adapter.transform('ñ', 'test_field') == 'ñ'
    
    # Test case sensitivity with Unicode
    case_insensitive = EnumFieldAdapter(['É', 'Ñ'], case_sensitive=False)
    assert case_insensitive.validate('é', 'test_field')
    assert case_insensitive.validate('ñ', 'test_field')