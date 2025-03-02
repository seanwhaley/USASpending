import pytest
from datetime import datetime
from unittest.mock import Mock

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
def entity_mapper():
    """Create an EntityMapper instance for testing."""
    return EntityMapper(TEST_CONFIG, "test_entity")

# Added fixture for entity configuration to fix EntityMapper init issue.
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

def test_direct_mapping(entity_mapper):
    """Test direct field mapping."""
    test_data = {
        "id_field": "123",
        "source_name": "Test Name",
        "source_amount": "$1,234.56"
    }
    
    result = entity_mapper.extract_entity_data(test_data)
    assert result is not None
    assert result["name"] == "Test Name"
    assert result["amount"] == 1234.56

def test_multi_source_mapping(entity_mapper):
    """Test multi-source field mapping."""
    test_data = {
        "id_field": "123",
        "address1": "123 Main St",
        "address2": "Suite 100",
        "city": "Springfield",
        "state": "IL",
        "zip": "62701"
    }
    
    result = entity_mapper.extract_entity_data(test_data)
    assert result is not None
    assert result["full_address"] == "123 Main St Suite 100 Springfield IL 62701"

def test_object_mapping(entity_mapper):
    """Test object field mapping."""
    test_data = {
        "id_field": "123",
        "address1": "123 Main St",
        "city": "Springfield",
        "state": "IL",
        "zip": "62701"
    }
    
    result = entity_mapper.extract_entity_data(test_data)
    assert result is not None
    assert "location" in result
    assert result["location"]["street"] == "123 Main St"
    assert result["location"]["city"] == "Springfield"
    assert result["location"]["state"] == "IL"
    assert result["location"]["zip"] == "62701"

def test_reference_mapping(entity_mapper):
    """Test reference field mapping."""
    test_data = {
        "id_field": "123",
        "parent_id": "456",
        "parent_type": "company"
    }
    
    result = entity_mapper.extract_entity_data(test_data)
    assert result is not None
    assert "parent" in result
    assert result["parent"]["type"] == "parent_entity"
    assert result["parent"]["data"]["id"] == "456"
    assert result["parent"]["data"]["type"] == "company"

def test_template_mapping(entity_mapper):
    """Test template field mapping."""
    test_data = {
        "id_field": "123",
        "name_prefix": "Mr",
        "first_name": "John",
        "last_name": "Doe"
    }
    
    result = entity_mapper.extract_entity_data(test_data)
    assert result is not None
    assert result["display_name"] == "Mr John Doe"

def test_missing_required_field(entity_mapper):
    """Test handling of missing required fields."""
    test_data = {
        "source_name": "Test"  # Missing id_field
    }
    
    result = entity_mapper.extract_entity_data(test_data)
    assert result is None

def test_transformation_error(entity_mapper):
    """Test handling of transformation errors."""
    test_data = {
        "id_field": "123",
        "source_amount": "invalid"  # Invalid money format
    }
    
    result = entity_mapper.extract_entity_data(test_data)
    assert result is not None
    assert "amount" not in result

def test_custom_type_validation(entity_mapper):
    """Test custom type validation."""
    test_data = {
        "id_field": "123",
        "zip": "12345-6789"
    }
    
    result = entity_mapper.extract_entity_data(test_data)
    assert result is not None
    assert result["location"]["zip"] == "12345-6789"

    test_data["zip"] = "invalid"
    result = entity_mapper.extract_entity_data(test_data)
    assert result is not None
    assert "zip" not in result["location"]

def test_entity_mapper_creation():
    mapper = EntityMapper(TEST_CONFIG, "test_entity")
    assert mapper is not None
    assert mapper.entity_type == "test_entity"