"""Tests for field adapter implementations."""
import warnings
import pytest
from typing import Dict, Any
from decimal import Decimal
from datetime import datetime, date

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