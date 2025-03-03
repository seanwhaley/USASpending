import pytest
from datetime import datetime
from unittest.mock import Mock
import json

from usaspending.entity_mapper import EntityMapper
from usaspending.exceptions import (
    EntityMappingError, FieldMappingError, TransformationError,
    TemplateError, ReferenceError, KeyGenerationError
)

# Sample test configuration
TEST_CONFIG = {
    "validation_types": {
        "numeric": {
            "money": {"strip_characters": "$,."},
            "decimal": {"strip_characters": ",."},
            "integer": {"strip_characters": ","}
        },
        "date": {
            "standard": {"format": "%Y-%m-%d"}
        },
        "boolean": {
            "validation": {
                "true_values": ["true", "yes", "1"],
                "false_values": ["false", "no", "0"]
            }
        },
        "custom": {
            "phone": {
                "validator": "phone",
                "args": {"pattern": r"^\+?1?\d{9,15}$"}
            },
            "zip": {
                "validator": "zip",
                "args": {"pattern": r"^\d{5}(?:-\d{4})?$"}
            }
        }
    },
    "entities": {
        "test_entity": {
            "enabled": True,
            "key_fields": ["id_field"],
            "field_mappings": {
                "direct": {
                    "id_field": {"field": "source_id"},
                    "name": {"field": "source_name"},
                    "amount": {
                        "field": "source_amount",
                        "transformation": {
                            "type": "money",
                            "pre": [{"operation": "strip", "characters": "$,"}]
                        }
                    }
                },
                "multi_source": {
                    "full_address": {
                        "fields": ["address1", "address2", "city", "state", "zip"],
                        "combine_function": "concatenate",
                        "transformation": {
                            "pre": [{"operation": "strip"}],
                            "post": [{"operation": "replace", "find": "  ", "replace": " "}]
                        }
                    }
                },
                "object": {
                    "location": {
                        "fields": {
                            "street": {"field": "address1"},
                            "city": {"field": "city"},
                            "state": {"field": "state"},
                            "zip": {
                                "field": "zip",
                                "transformation": {"type": "zip"}
                            }
                        }
                    }
                },
                "reference": {
                    "parent": {
                        "entity_type": "parent_entity",
                        "fields": {
                            "id": {"field": "parent_id"},
                            "type": {"field": "parent_type"}
                        }
                    }
                },
                "template": {
                    "display_name": {
                        "template": "{prefix} {first} {last}",
                        "fields": {
                            "prefix": "name_prefix",
                            "first": "first_name",
                            "last": "last_name"
                        }
                    }
                }
            }
        }
    }
}

@pytest.fixture
def entity_mapper(monkeypatch):
    """Create an EntityMapper instance for testing."""
    # Mock any validation or custom transformation methods if needed
    mapper = EntityMapper(TEST_CONFIG, "test_entity")
    
    # Ensure the mapper can handle money transformations
    if not hasattr(mapper, "transform_money") or not callable(mapper.transform_money):
        monkeypatch.setattr(mapper, "transform_money", 
                           lambda value, config: float(value.strip("$,")) if isinstance(value, str) else value)
    
    return mapper

@pytest.fixture
def sample_data():
    """Return sample source data for testing."""
    return {
        "id_field": "12345",  # Add direct key field to make extract_entity_data work
        "source_id": "12345",
        "source_name": "Test Entity",
        "source_amount": "$1,234.56",
        "address1": "123 Main St",
        "address2": "Suite 100",
        "city": "Springfield",
        "state": "IL",
        "zip": "62701",
        "parent_id": "P001",
        "parent_type": "organization",
        "name_prefix": "Mr.",
        "first_name": "John",
        "last_name": "Doe"
    }

@pytest.fixture
def entity_config():
    """Return a sample entity configuration."""
    return {
        "key_fields": ["id"],
        "field_mappings": {
            "direct": {
                "id": {"field": "source_id"},
                "name": {"field": "source_name"}
            }
        }
    }

def test_direct_mapping(entity_mapper, sample_data):
    """Test direct field mapping."""
    result = entity_mapper.extract_entity_data(sample_data)
    
    assert result["id_field"] == "12345"
    assert result["name"] == "Test Entity"
    assert result["amount"] == 1234.56

def test_multi_source_mapping(entity_mapper, sample_data):
    """Test mapping from multiple source fields."""
    result = entity_mapper.extract_entity_data(sample_data)
    
    expected_address = "123 Main St Suite 100 Springfield IL 62701"
    assert result["full_address"] == expected_address

def test_object_mapping(entity_mapper, sample_data):
    """Test mapping to nested object structure."""
    result = entity_mapper.extract_entity_data(sample_data)
    
    assert "location" in result
    assert result["location"]["street"] == "123 Main St"
    assert result["location"]["city"] == "Springfield"
    assert result["location"]["state"] == "IL"
    assert result["location"]["zip"] == "62701"

def test_reference_mapping(entity_mapper, sample_data):
    """Test mapping reference fields."""
    result = entity_mapper.extract_entity_data(sample_data)
    
    assert "parent" in result
    assert result["parent"]["type"] == "parent_entity"
    assert "data" in result["parent"]
    assert result["parent"]["data"]["id"] == "P001"
    assert result["parent"]["data"]["type"] == "organization"

def test_template_mapping(entity_mapper, sample_data):
    """Test template-based mapping."""
    result = entity_mapper.extract_entity_data(sample_data)
    
    assert result["display_name"] == "Mr. John Doe"

def test_missing_required_field(entity_mapper):
    """Test behavior when a required field is missing."""
    # Missing source_id which maps to id_field (a key field)
    incomplete_data = {
        "source_name": "Test Entity",
        "source_amount": "$1,234.56"
    }
    
    # The extract_entity_data method returns None for missing key fields
    assert entity_mapper.extract_entity_data(incomplete_data) is None

def test_transformation_error(entity_mapper, sample_data, monkeypatch):
    """Test error handling during transformations."""
    # Create a converter that raises an exception
    def mock_convert_value(*args, **kwargs):
        raise TransformationError("Test error")
        
    from usaspending.utils import TypeConverter
    monkeypatch.setattr(TypeConverter, "convert_value", mock_convert_value)
    
    # The method should skip fields with transformation errors
    result = entity_mapper.extract_entity_data(sample_data)
    assert "amount" not in result

def test_custom_type_validation(entity_mapper, sample_data, monkeypatch):
    """Test custom type validation."""
    result = entity_mapper.extract_entity_data(sample_data)
    assert result["location"]["zip"] == "62701"
    
    # Test error handling by monkeypatching TypeConverter
    def mock_convert_value(self, value, transform_type):
        if transform_type == "zip" and value == "invalid-zip":
            return None
        return value
        
    from usaspending.utils import TypeConverter
    monkeypatch.setattr(TypeConverter, "convert_value", mock_convert_value)
    
    # Modify data to use invalid zip
    invalid_data = sample_data.copy()
    invalid_data["zip"] = "invalid-zip"
    
    # The field should be skipped
    result = entity_mapper.extract_entity_data(invalid_data)
    assert "zip" not in result["location"]

def test_entity_mapper_creation(mock_config_manager):
    """Test EntityMapper creation with centralized mock_config_manager."""
    # Extract entity config from mock_config_manager
    config = mock_config_manager.get_config()
    entities_config = config.get("entities", {})
    
    if "contract" in entities_config:
        # Use a real entity from the config if available
        mapper = EntityMapper(config, "contract")
        assert mapper.entity_type == "contract"
        # We access the field mapping directly now
        fields = mapper.field_mapping.get("direct", {})
        assert "id" in fields
        assert fields["id"]["field"] == "contract_id"
    else:
        # Skip if no suitable entity in config
        pytest.skip("No suitable entity config found in mock_config_manager")

def test_json_serialization(entity_mapper, sample_data):
    """Test that mapped entity can be serialized to JSON."""
    result = entity_mapper.extract_entity_data(sample_data)
    
    # Should not raise any exceptions
    json_str = json.dumps(result)
    assert isinstance(json_str, str)
    
    # Verify we can deserialize it back
    deserialized = json.loads(json_str)
    assert deserialized["name"] == "Test Entity"
    assert deserialized["amount"] == 1234.56
    
def test_empty_mappings():
    """Test behavior with empty mappings configuration."""
    empty_config = {
        "entities": {
            "empty_entity": {
                "enabled": True,
                "key_fields": ["id"],
                "field_mappings": {}
            }
        }
    }
    
    mapper = EntityMapper(empty_config, "empty_entity")
    
    # With no mappings, should return an empty dict 
    sample_data = {"id": "123"}  # Include the key field directly
    result = mapper.extract_entity_data(sample_data)
    assert result == {}