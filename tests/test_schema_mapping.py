"""Tests for schema mapping functionality."""
import pytest
from src.usaspending.core.schema_mapping import SchemaMapping
from src.usaspending.core.transformers import TransformerFactory
from src.usaspending.core.types import TransformationRule, FieldType

@pytest.fixture
def transformer_factory():
    return TransformerFactory()

@pytest.fixture
def schema_mapping(transformer_factory):
    return SchemaMapping(transformer_factory)

def test_get_adapter_type():
    """Test getting adapter type for different field types."""
    assert SchemaMapping.get_adapter_type('numeric', 'money') == 'numeric'
    assert SchemaMapping.get_adapter_type('string') == 'string'
    assert SchemaMapping.get_adapter_type('unknown') == 'string'  # defaults to string

def test_get_standard_transforms():
    """Test getting standard transformations for field types."""
    money_transforms = SchemaMapping.get_standard_transforms('money')
    assert len(money_transforms) >= 2  # Should have at least strip and numeric transforms
    assert any(t.transform_type == 'string' for t in money_transforms)
    assert any(t.transform_type == 'numeric' for t in money_transforms)

def test_create_adapter(schema_mapping):
    """Test adapter creation with field properties."""
    adapter = schema_mapping.create_adapter('string', {
        'max_length': 10,
        'pattern': '[A-Za-z]+'
    })
    assert adapter is not None
    
def test_create_adapter_with_transforms(schema_mapping):
    """Test adapter creation with transformations."""
    adapter = schema_mapping.create_adapter('numeric', {
        'transformation': {
            'type': 'numeric',
            'parameters': {'decimal_places': 2}
        }
    })
    assert adapter is not None

def test_create_adapter_invalid_type(schema_mapping):
    """Test adapter creation with invalid type."""
    adapter = schema_mapping.create_adapter('invalid_type', {})
    assert adapter is not None  # Should return string adapter as fallback
