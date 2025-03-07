"""Tests for the boolean_adapters module."""
import pytest
from src.usaspending.boolean_adapters import BooleanFieldAdapter, FormattedBooleanAdapter


@pytest.fixture
def basic_boolean_adapter():
    """Create a basic boolean adapter for testing."""
    return BooleanFieldAdapter()


@pytest.fixture
def custom_boolean_adapter():
    """Create a boolean adapter with custom true/false values."""
    return BooleanFieldAdapter(
        true_values={'yep', 'affirmative', 'positive'},
        false_values={'nope', 'negative', 'deny'}
    )


@pytest.fixture
def formatted_boolean_adapter():
    """Create a formatted boolean adapter."""
    return FormattedBooleanAdapter(
        true_format='✓',
        false_format='✗'
    )


def test_basic_boolean_adapter_initialization():
    """Test the initialization of the BooleanFieldAdapter."""
    adapter = BooleanFieldAdapter()
    
    # Check default values
    assert 'true' in adapter.true_values
    assert 'yes' in adapter.true_values
    assert '1' in adapter.true_values
    assert 'y' in adapter.true_values
    assert 't' in adapter.true_values
    
    assert 'false' in adapter.false_values
    assert 'no' in adapter.false_values
    assert '0' in adapter.false_values
    assert 'n' in adapter.false_values
    assert 'f' in adapter.false_values
    
    assert adapter.errors == []
    
    # Check custom initialization
    custom_adapter = BooleanFieldAdapter(
        true_values={'positive', 'yep'},
        false_values={'negative', 'nope'}
    )
    assert custom_adapter.true_values == {'positive', 'yep'}
    assert custom_adapter.false_values == {'negative', 'nope'}


def test_boolean_adapter_validate_true_values(basic_boolean_adapter):
    """Test validation of true values."""
    adapter = basic_boolean_adapter
    
    # Boolean true
    assert adapter.validate(True, 'test_field')
    
    # Numeric 1
    assert adapter.validate(1, 'test_field')
    
    # String representations of true
    assert adapter.validate('true', 'test_field')
    assert adapter.validate('True', 'test_field')
    assert adapter.validate('TRUE', 'test_field')
    assert adapter.validate('yes', 'test_field')
    assert adapter.validate('Yes', 'test_field')
    assert adapter.validate('YES', 'test_field')
    assert adapter.validate('1', 'test_field')
    assert adapter.validate('y', 'test_field')
    assert adapter.validate('Y', 'test_field')
    assert adapter.validate('t', 'test_field')
    assert adapter.validate('T', 'test_field')
    
    # No validation errors
    assert adapter.errors == []


def test_boolean_adapter_validate_false_values(basic_boolean_adapter):
    """Test validation of false values."""
    adapter = basic_boolean_adapter
    
    # Boolean false
    assert adapter.validate(False, 'test_field')
    
    # Numeric 0
    assert adapter.validate(0, 'test_field')
    
    # String representations of false
    assert adapter.validate('false', 'test_field')
    assert adapter.validate('False', 'test_field')
    assert adapter.validate('FALSE', 'test_field')
    assert adapter.validate('no', 'test_field')
    assert adapter.validate('No', 'test_field')
    assert adapter.validate('NO', 'test_field')
    assert adapter.validate('0', 'test_field')
    assert adapter.validate('n', 'test_field')
    assert adapter.validate('N', 'test_field')
    assert adapter.validate('f', 'test_field')
    assert adapter.validate('F', 'test_field')
    
    # No validation errors
    assert adapter.errors == []


def test_boolean_adapter_validate_none(basic_boolean_adapter):
    """Test validation of None value."""
    adapter = basic_boolean_adapter
    
    # None is considered valid
    assert adapter.validate(None, 'test_field')
    assert adapter.errors == []


def test_boolean_adapter_validate_invalid_values(basic_boolean_adapter):
    """Test validation of invalid boolean values."""
    adapter = basic_boolean_adapter
    
    # Invalid string
    assert adapter.validate('invalid', 'test_field') is False
    assert len(adapter.errors) == 1
    assert "Value 'invalid' is not a valid boolean" in adapter.errors[0]
    
    # Reset errors
    adapter.errors = []
    
    # Invalid number
    assert adapter.validate(2, 'test_field') is False
    assert len(adapter.errors) == 1
    
    # Reset errors
    adapter.errors = []
    
    # Invalid type
    assert adapter.validate([], 'test_field') is False
    assert len(adapter.errors) == 1


def test_custom_boolean_adapter_validation(custom_boolean_adapter):
    """Test validation with custom true/false values."""
    adapter = custom_boolean_adapter
    
    # Custom true values
    assert adapter.validate('yep', 'test_field')
    assert adapter.validate('affirmative', 'test_field')
    assert adapter.validate('positive', 'test_field')
    
    # Custom false values
    assert adapter.validate('nope', 'test_field')
    assert adapter.validate('negative', 'test_field')
    assert adapter.validate('deny', 'test_field')
    
    # Standard values should fail
    assert adapter.validate('true', 'test_field') is False
    assert adapter.validate('false', 'test_field') is False
    assert "not a valid boolean" in adapter.errors[0]


def test_boolean_adapter_transform_true_values(basic_boolean_adapter):
    """Test transformation of true values."""
    adapter = basic_boolean_adapter
    
    # Boolean true
    assert adapter.transform(True, 'test_field') is True
    
    # Numeric 1
    assert adapter.transform(1, 'test_field') is True
    
    # String representations of true
    assert adapter.transform('true', 'test_field') is True
    assert adapter.transform('True', 'test_field') is True
    assert adapter.transform('TRUE', 'test_field') is True
    assert adapter.transform('yes', 'test_field') is True
    assert adapter.transform('Yes', 'test_field') is True
    assert adapter.transform('YES', 'test_field') is True
    assert adapter.transform('1', 'test_field') is True
    assert adapter.transform('y', 'test_field') is True
    assert adapter.transform('Y', 'test_field') is True
    assert adapter.transform('t', 'test_field') is True
    assert adapter.transform('T', 'test_field') is True


def test_boolean_adapter_transform_false_values(basic_boolean_adapter):
    """Test transformation of false values."""
    adapter = basic_boolean_adapter
    
    # Boolean false
    assert adapter.transform(False, 'test_field') is False
    
    # Numeric 0
    assert adapter.transform(0, 'test_field') is False
    
    # String representations of false
    assert adapter.transform('false', 'test_field') is False
    assert adapter.transform('False', 'test_field') is False
    assert adapter.transform('FALSE', 'test_field') is False
    assert adapter.transform('no', 'test_field') is False
    assert adapter.transform('No', 'test_field') is False
    assert adapter.transform('NO', 'test_field') is False
    assert adapter.transform('0', 'test_field') is False
    assert adapter.transform('n', 'test_field') is False
    assert adapter.transform('N', 'test_field') is False
    assert adapter.transform('f', 'test_field') is False
    assert adapter.transform('F', 'test_field') is False


def test_boolean_adapter_transform_none(basic_boolean_adapter):
    """Test transformation of None value."""
    adapter = basic_boolean_adapter
    
    # None transforms to None
    assert adapter.transform(None, 'test_field') is None


def test_boolean_adapter_transform_invalid_values(basic_boolean_adapter):
    """Test transformation of invalid boolean values."""
    adapter = basic_boolean_adapter
    
    # Invalid string returns None
    assert adapter.transform('invalid', 'test_field') is None
    
    # Invalid number returns None
    assert adapter.transform(2, 'test_field') is None
    
    # Invalid type returns None
    assert adapter.transform([], 'test_field') is None


def test_custom_boolean_adapter_transform(custom_boolean_adapter):
    """Test transformation with custom true/false values."""
    adapter = custom_boolean_adapter
    
    # Custom true values
    assert adapter.transform('yep', 'test_field') is True
    assert adapter.transform('affirmative', 'test_field') is True
    assert adapter.transform('positive', 'test_field') is True
    
    # Custom false values
    assert adapter.transform('nope', 'test_field') is False
    assert adapter.transform('negative', 'test_field') is False
    assert adapter.transform('deny', 'test_field') is False
    
    # Standard values should return None
    assert adapter.transform('true', 'test_field') is None
    assert adapter.transform('false', 'test_field') is None


def test_get_validation_errors(basic_boolean_adapter):
    """Test retrieving validation errors."""
    adapter = basic_boolean_adapter
    
    # No errors initially
    assert adapter.get_validation_errors() == []
    
    # After validation failure
    adapter.validate('invalid', 'test_field')
    errors = adapter.get_validation_errors()
    assert len(errors) == 1
    assert "Value 'invalid' is not a valid boolean" in errors[0]
    
    # Ensure the returned list is a copy, not the original
    errors.clear()
    assert len(adapter.get_validation_errors()) == 1


def test_formatted_boolean_adapter_initialization():
    """Test the initialization of the FormattedBooleanAdapter."""
    # Default formats
    adapter = FormattedBooleanAdapter()
    assert adapter.true_format == 'Yes'
    assert adapter.false_format == 'No'
    
    # Custom formats
    custom_adapter = FormattedBooleanAdapter(
        true_format='✓',
        false_format='✗'
    )
    assert custom_adapter.true_format == '✓'
    assert custom_adapter.false_format == '✗'
    
    # Custom formats and values
    advanced_adapter = FormattedBooleanAdapter(
        true_format='Approved',
        false_format='Rejected',
        true_values={'approved', 'accept'},
        false_values={'rejected', 'decline'}
    )
    assert advanced_adapter.true_format == 'Approved'
    assert advanced_adapter.false_format == 'Rejected'
    assert 'approved' in advanced_adapter.true_values
    assert 'rejected' in advanced_adapter.false_values


def test_formatted_boolean_adapter_transform(formatted_boolean_adapter):
    """Test transformation with formatted outputs."""
    adapter = formatted_boolean_adapter
    
    # True values should transform to the true_format
    assert adapter.transform(True, 'test_field') == '✓'
    assert adapter.transform('yes', 'test_field') == '✓'
    assert adapter.transform(1, 'test_field') == '✓'
    
    # False values should transform to the false_format
    assert adapter.transform(False, 'test_field') == '✗'
    assert adapter.transform('no', 'test_field') == '✗'
    assert adapter.transform(0, 'test_field') == '✗'
    
    # None and invalid values should transform to None
    assert adapter.transform(None, 'test_field') is None
    assert adapter.transform('invalid', 'test_field') is None


def test_formatted_boolean_adapter_validation(formatted_boolean_adapter):
    """Test validation with formatted boolean adapter."""
    adapter = formatted_boolean_adapter
    
    # Validation should work the same as with BooleanFieldAdapter
    assert adapter.validate(True, 'test_field')
    assert adapter.validate('yes', 'test_field')
    assert adapter.validate(False, 'test_field')
    assert adapter.validate('no', 'test_field')
    assert adapter.validate(None, 'test_field')
    
    # Invalid values
    assert adapter.validate('invalid', 'test_field') is False
    assert len(adapter.errors) == 1


def test_formatted_boolean_adapter_with_different_formats():
    """Test with various output formats."""
    # Test with numerical outputs
    num_adapter = FormattedBooleanAdapter(true_format='1', false_format='0')
    assert num_adapter.transform(True, 'test_field') == '1'
    assert num_adapter.transform(False, 'test_field') == '0'
    
    # Test with emoji outputs
    emoji_adapter = FormattedBooleanAdapter(true_format='👍', false_format='👎')
    assert emoji_adapter.transform(True, 'test_field') == '👍'
    assert emoji_adapter.transform(False, 'test_field') == '👎'
    
    # Test with uppercase outputs
    upper_adapter = FormattedBooleanAdapter(true_format='TRUE', false_format='FALSE')
    assert upper_adapter.transform(True, 'test_field') == 'TRUE'
    assert upper_adapter.transform(False, 'test_field') == 'FALSE'