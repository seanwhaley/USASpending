import pytest
from decimal import Decimal
from datetime import datetime
from typing import Any, Dict
from src.usaspending.core.adapters import (
    BaseAdapter,
    StringAdapter,
    IntegerAdapter,
    DecimalAdapter,
    DateAdapter,
    BooleanAdapter
)
from src.usaspending.core.types import TransformationRule, FieldType

class TestAdapter(BaseAdapter):
    """Test implementation of BaseAdapter."""
    def transform_field(self, value: Any) -> Any:
        return value

@pytest.fixture
def adapter():
    return TestAdapter()

@pytest.fixture
def string_adapter():
    return StringAdapter()

@pytest.fixture
def integer_adapter():
    return IntegerAdapter()

@pytest.fixture
def decimal_adapter():
    return DecimalAdapter()

@pytest.fixture
def date_adapter():
    return DateAdapter()

@pytest.fixture
def boolean_adapter():
    return BooleanAdapter()

def test_base_adapter_initialization(adapter):
    assert adapter._transformations == []
    assert adapter._field_name is None

def test_string_adapter_basic_conversion(string_adapter):
    # Test basic string conversions
    assert string_adapter.transform_field(123) == "123"
    assert string_adapter.transform_field(45.67) == "45.67"
    assert string_adapter.transform_field(True) == "True"
    assert string_adapter.transform_field(None) is None
    assert string_adapter.transform_field("") == ""

def test_string_adapter_transformations():
    # Create adapter with transformations
    transformations = [
        TransformationRule(
            transform_type='uppercase',
            parameters={}
        ),
        TransformationRule(
            transform_type='strip',
            parameters={}
        )
    ]
    adapter = StringAdapter(transformations=transformations)
    
    # Test transformation chain
    assert adapter.transform_field("  hello world  ") == "HELLO WORLD"
    assert adapter.transform_field("test") == "TEST"

def test_integer_adapter_basic_conversion(integer_adapter):
    # Test valid conversions
    assert integer_adapter.transform_field("123") == 123
    assert integer_adapter.transform_field(45.67) == 45
    assert integer_adapter.transform_field("-789") == -789
    assert integer_adapter.transform_field(None) is None
    
    # Test invalid conversions
    with pytest.raises(ValueError):
        integer_adapter.transform_field("invalid")
    with pytest.raises(ValueError):
        integer_adapter.transform_field("")

def test_decimal_adapter_basic_conversion(decimal_adapter):
    # Test valid conversions
    assert decimal_adapter.transform_field("123.45") == Decimal("123.45")
    assert decimal_adapter.transform_field(789) == Decimal("789")
    assert decimal_adapter.transform_field("-45.67") == Decimal("-45.67")
    assert decimal_adapter.transform_field(None) is None
    
    # Test invalid conversions
    with pytest.raises(ValueError):
        decimal_adapter.transform_field("invalid")
    with pytest.raises(ValueError):
        decimal_adapter.transform_field("")

def test_decimal_adapter_precision():
    # Create adapter with precision setting
    adapter = DecimalAdapter(transformations=[
        TransformationRule(
            transform_type='decimal',
            parameters={'precision': 2}
        )
    ])
    
    # Test precision handling
    assert adapter.transform_field("123.4567") == Decimal("123.46")
    assert adapter.transform_field("45.6") == Decimal("45.60")

def test_date_adapter_basic_conversion(date_adapter):
    # Test valid conversions
    assert date_adapter.transform_field("2024-03-14") == datetime(2024, 3, 14)
    assert date_adapter.transform_field("2024/03/14") == datetime(2024, 3, 14)
    assert date_adapter.transform_field(None) is None
    
    # Test invalid conversions
    with pytest.raises(ValueError):
        date_adapter.transform_field("invalid")
    with pytest.raises(ValueError):
        date_adapter.transform_field("")

def test_date_adapter_custom_format():
    # Create adapter with custom format
    adapter = DateAdapter(transformations=[
        TransformationRule(
            transform_type='date',
            parameters={'format': '%m/%d/%Y'}
        )
    ])
    
    # Test custom format parsing
    assert adapter.transform_field("03/14/2024") == datetime(2024, 3, 14)
    with pytest.raises(ValueError):
        adapter.transform_field("2024-03-14")  # Wrong format

def test_boolean_adapter_basic_conversion(boolean_adapter):
    # Test true values
    assert boolean_adapter.transform_field("true")
    assert boolean_adapter.transform_field("True")
    assert boolean_adapter.transform_field("1")
    assert boolean_adapter.transform_field(1)
    assert boolean_adapter.transform_field(True)
    
    # Test false values
    assert not boolean_adapter.transform_field("false")
    assert not boolean_adapter.transform_field("False")
    assert not boolean_adapter.transform_field("0")
    assert not boolean_adapter.transform_field(0)
    assert not boolean_adapter.transform_field(False)
    
    # Test null handling
    assert boolean_adapter.transform_field(None) is None
    
    # Test invalid values
    with pytest.raises(ValueError):
        boolean_adapter.transform_field("invalid")

def test_boolean_adapter_custom_values():
    # Create adapter with custom true/false values
    adapter = BooleanAdapter(transformations=[
        TransformationRule(
            transform_type='boolean',
            parameters={
                'true_values': ['yes', 'y'],
                'false_values': ['no', 'n']
            }
        )
    ])
    
    # Test custom values
    assert adapter.transform_field("yes")
    assert adapter.transform_field("y")
    assert not adapter.transform_field("no")
    assert not adapter.transform_field("n")
    
    # Test invalid value
    with pytest.raises(ValueError):
        adapter.transform_field("maybe")

def test_adapter_chained_transformations():
    adapter = StringAdapter(transformations=[
        TransformationRule(
            transform_type='strip',
            parameters={}
        ),
        TransformationRule(
            transform_type='uppercase',
            parameters={}
        ),
        TransformationRule(
            transform_type='replace',
            parameters={'old': ' ', 'new': '_'}
        )
    ])
    
    assert adapter.transform_field("  hello world  ") == "HELLO_WORLD"

def test_adapter_field_name():
    adapter = StringAdapter(field_name="test_field")
    assert adapter._field_name == "test_field"
    
    # Test error message includes field name
    with pytest.raises(ValueError) as exc_info:
        adapter.transform_field(123.45, strict=True)
    assert "test_field" in str(exc_info.value)

def test_adapter_error_handling():
    adapter = IntegerAdapter()
    
    # Test non-strict mode (default)
    with pytest.raises(ValueError):
        adapter.transform_field("invalid")
    
    # Test strict mode
    with pytest.raises(ValueError):
        adapter.transform_field("invalid", strict=True)
