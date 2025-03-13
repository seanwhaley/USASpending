import pytest
from decimal import Decimal
from datetime import datetime, date
from src.usaspending.core.transformers import (
    TransformationEngine,
    BaseTransformer,
    StringTransformer,
    NumericTransformer,
    DateTransformer
)
from src.usaspending.core.types import TransformationRule
from src.usaspending.core.exceptions import TransformationError

class TestTransformer(BaseTransformer):
    """Test implementation of BaseTransformer."""
    def transform(self, value: str, parameters: dict = None) -> str:
        return f"transformed_{value}"

@pytest.fixture
def transformation_engine():
    return TransformationEngine()

@pytest.fixture
def string_transformer():
    return StringTransformer()

@pytest.fixture
def numeric_transformer():
    return NumericTransformer()

@pytest.fixture
def date_transformer():
    return DateTransformer()

def test_transformation_engine_initialization(transformation_engine):
    assert len(transformation_engine._transformers) > 0
    assert 'string' in transformation_engine._transformers
    assert 'numeric' in transformation_engine._transformers
    assert 'date' in transformation_engine._transformers

def test_transformation_engine_register_transformer(transformation_engine):
    transformer = TestTransformer()
    transformation_engine.register_transformer('test', transformer)
    assert 'test' in transformation_engine._transformers
    assert transformation_engine._transformers['test'] == transformer

def test_string_transformer_basic(string_transformer):
    # Test basic string transformations
    assert string_transformer.transform("hello") == "hello"
    assert string_transformer.transform(123) == "123"
    assert string_transformer.transform(45.67) == "45.67"
    assert string_transformer.transform(None) is None

def test_string_transformer_rules():
    transformer = StringTransformer()
    
    # Test uppercase transformation
    value = transformer.transform("hello", {
        'type': 'uppercase'
    })
    assert value == "HELLO"
    
    # Test lowercase transformation
    value = transformer.transform("HELLO", {
        'type': 'lowercase'
    })
    assert value == "hello"
    
    # Test strip transformation
    value = transformer.transform("  hello  ", {
        'type': 'strip'
    })
    assert value == "hello"

def test_string_transformer_chained_rules():
    transformer = StringTransformer()
    
    # Test multiple transformations
    value = transformer.transform("  HELLO world  ", {
        'rules': [
            {'type': 'strip'},
            {'type': 'uppercase'}
        ]
    })
    assert value == "HELLO WORLD"

def test_numeric_transformer_basic(numeric_transformer):
    # Test integer conversions
    assert numeric_transformer.transform("123", {'type': 'integer'}) == 123
    assert numeric_transformer.transform("-456", {'type': 'integer'}) == -456
    
    # Test decimal conversions
    assert numeric_transformer.transform("123.45", {'type': 'decimal'}) == Decimal("123.45")
    assert numeric_transformer.transform("-67.89", {'type': 'decimal'}) == Decimal("-67.89")
    
    # Test null handling
    assert numeric_transformer.transform(None, {'type': 'integer'}) is None
    assert numeric_transformer.transform(None, {'type': 'decimal'}) is None

def test_numeric_transformer_precision():
    transformer = NumericTransformer()
    
    # Test decimal precision
    value = transformer.transform("123.4567", {
        'type': 'decimal',
        'precision': 2
    })
    assert value == Decimal("123.46")  # Rounds to 2 decimal places

def test_numeric_transformer_invalid_input():
    transformer = NumericTransformer()
    
    # Test invalid integer
    with pytest.raises(TransformationError):
        transformer.transform("invalid", {'type': 'integer'})
    
    # Test invalid decimal
    with pytest.raises(TransformationError):
        transformer.transform("invalid", {'type': 'decimal'})

def test_date_transformer_basic(date_transformer):
    # Test basic date parsing
    assert date_transformer.transform("2024-03-14") == datetime(2024, 3, 14)
    assert date_transformer.transform("2024/03/14") == datetime(2024, 3, 14)
    assert date_transformer.transform(None) is None

def test_date_transformer_custom_format():
    transformer = DateTransformer()
    
    # Test custom date format
    value = transformer.transform("03/14/2024", {
        'format': '%m/%d/%Y'
    })
    assert value == datetime(2024, 3, 14)

def test_date_transformer_invalid_input():
    transformer = DateTransformer()
    
    # Test invalid date
    with pytest.raises(TransformationError):
        transformer.transform("invalid")
    
    # Test invalid format
    with pytest.raises(TransformationError):
        transformer.transform("2024-03-14", {'format': 'invalid'})

def test_transformation_rule_creation():
    # Test basic rule
    rule = TransformationRule(
        transform_type='uppercase',
        parameters={}
    )
    assert rule.transform_type == 'uppercase'
    assert rule.parameters == {}
    
    # Test rule with parameters
    rule = TransformationRule(
        transform_type='decimal',
        parameters={'precision': 2}
    )
    assert rule.transform_type == 'decimal'
    assert rule.parameters == {'precision': 2}

def test_transformation_engine_apply_rules(transformation_engine):
    rules = [
        TransformationRule(
            transform_type='string.strip',
            parameters={}
        ),
        TransformationRule(
            transform_type='string.uppercase',
            parameters={}
        )
    ]
    
    value = transformation_engine.apply_transformations("  hello world  ", rules)
    assert value == "HELLO WORLD"

def test_transformation_engine_invalid_transformer(transformation_engine):
    with pytest.raises(TransformationError):
        transformation_engine.apply_transformations(
            "test",
            [TransformationRule(transform_type='nonexistent', parameters={})]
        )

def test_transformer_type_conversion():
    transformers = {
        'string': StringTransformer(),
        'numeric': NumericTransformer(),
        'date': DateTransformer()
    }
    
    test_value = "123.45"
    
    # Test string to number conversion
    number = transformers['numeric'].transform(test_value, {'type': 'decimal'})
    assert isinstance(number, Decimal)
    assert number == Decimal("123.45")
    
    # Test number to string conversion
    string = transformers['string'].transform(number)
    assert isinstance(string, str)
    assert string == "123.45"
    
    # Test string to date conversion
    date_str = "2024-03-14"
    date_obj = transformers['date'].transform(date_str)
    assert isinstance(date_obj, datetime)
    
    # Test date to string conversion
    formatted_date = transformers['string'].transform(date_obj)
    assert isinstance(formatted_date, str)
    assert "2024" in formatted_date

def test_transformation_error_handling(transformation_engine):
    # Create a transformation that will fail
    rules = [
        TransformationRule(
            transform_type='numeric.integer',
            parameters={}
        )
    ]
    
    # Test with invalid input
    with pytest.raises(TransformationError) as exc_info:
        transformation_engine.apply_transformations("invalid", rules)
    assert "transformation failed" in str(exc_info.value).lower()

def test_custom_transformer_registration():
    engine = TransformationEngine()
    
    # Create and register custom transformer
    custom_transformer = TestTransformer()
    engine.register_transformer('custom', custom_transformer)
    
    # Test custom transformation
    rules = [
        TransformationRule(
            transform_type='custom',
            parameters={}
        )
    ]
    
    result = engine.apply_transformations("test", rules)
    assert result == "transformed_test"
