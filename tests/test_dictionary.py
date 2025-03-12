import pytest
from pathlib import Path
from typing import Dict, Any, Set
from usaspending.dictionary import Dictionary
from usaspending.core.fields import FieldDefinition
from usaspending.core.types import ValidationRule, RuleType, ValidationSeverity, FieldType

@pytest.fixture
def sample_config() -> Dict[str, Any]:
    return {
        "field_properties": {
            "id": {
                "type": "string",
                "required": True,
                "is_key": True,
                "groups": ["primary", "required"],
                "validation_rules": [
                    {
                        "type": "required",
                        "message": "ID is required",
                        "severity": "error"
                    }
                ]
            },
            "amount": {
                "type": "decimal",
                "required": True,
                "groups": ["financial", "required"],
                "validation_rules": [
                    {
                        "type": "range",
                        "parameters": {"min": 0},
                        "message": "Amount must be positive",
                        "severity": "error"
                    }
                ],
                "transformations": [
                    {
                        "type": "decimal",
                        "parameters": {"precision": 2}
                    }
                ]
            },
            "status": {
                "type": "string",
                "required": False,
                "groups": ["metadata"],
                "validation_rules": [
                    {
                        "type": "enum",
                        "parameters": {"values": ["active", "inactive"]},
                        "message": "Invalid status",
                        "severity": "warning"
                    }
                ]
            }
        }
    }

@pytest.fixture
def dictionary(sample_config):
    return Dictionary(sample_config)

def test_dictionary_initialization(dictionary):
    assert len(dictionary.fields) == 3
    assert all(isinstance(field, FieldDefinition) for field in dictionary.fields.values())
    assert len(dictionary.field_groups) > 0

def test_get_field(dictionary):
    field = dictionary.get_field("id")
    assert field is not None
    assert field.type == FieldType.STRING
    assert field.required
    assert field.is_key

def test_get_field_type(dictionary):
    assert dictionary.get_field_type("amount") == "decimal"
    assert dictionary.get_field_type("nonexistent") is None

def test_get_field_transformations(dictionary):
    transformations = dictionary.get_field_transformations("amount")
    assert len(transformations) == 1
    assert transformations[0]["type"] == "decimal"
    assert transformations[0]["parameters"]["precision"] == 2

def test_get_field_validation_rules(dictionary):
    rules = dictionary.get_field_validation_rules("status")
    assert len(rules) == 1
    assert rules[0].rule_type == RuleType.ENUM
    assert "active" in rules[0].parameters["values"]

def test_get_fields_in_group(dictionary):
    required_fields = dictionary.get_fields_in_group("required")
    assert len(required_fields) == 2
    assert "id" in required_fields
    assert "amount" in required_fields

def test_get_key_fields(dictionary):
    key_fields = dictionary.get_key_fields()
    assert len(key_fields) == 1
    assert "id" in key_fields

def test_get_required_fields(dictionary):
    required_fields = dictionary.get_required_fields()
    assert len(required_fields) == 2
    assert "id" in required_fields
    assert "amount" in required_fields

def test_validate_field_success(dictionary):
    errors = dictionary.validate_field("amount", "100.50")
    assert len(errors) == 0

def test_validate_field_failure(dictionary):
    errors = dictionary.validate_field("amount", "-50.00")
    assert len(errors) > 0
    assert any("must be positive" in error for error in errors)

def test_transform_field(dictionary):
    result = dictionary.transform_field("amount", "100.567")
    assert float(result) == 100.57  # Should round to 2 decimal places

def test_validate_enum_field(dictionary):
    assert len(dictionary.validate_field("status", "active")) == 0
    assert len(dictionary.validate_field("status", "invalid")) > 0

@pytest.fixture
def temp_csv_path(tmp_path):
    csv_path = tmp_path / "test_fields.csv"
    with open(csv_path, 'w') as f:
        f.write("""field_name,type,required,is_key,groups,validation_rules
test_field,string,true,false,"group1,group2","required,pattern:^[A-Z]+$"
""")
    return csv_path

def test_dictionary_from_csv(temp_csv_path):
    config = {"csv_mapping": {"delimiter": ","}}
    dictionary = Dictionary.from_csv(temp_csv_path, config)
    
    field = dictionary.get_field("test_field")
    assert field is not None
    assert field.type == FieldType.STRING
    assert field.required
    assert not field.is_key
    assert "group1" in field.groups
    assert len(field.validation_rules) == 2

@pytest.fixture
def temp_json_path(tmp_path):
    return tmp_path / "test_fields.json"

def test_dictionary_to_json(dictionary, temp_json_path):
    dictionary.to_json(temp_json_path)
    assert temp_json_path.exists()
    
    # Create new dictionary from saved JSON
    new_dict = Dictionary({"field_properties": {}})
    # The file should be readable and contain our fields
    assert temp_json_path.stat().st_size > 0

def test_cleanup(dictionary):
    dictionary.cleanup()
    assert len(dictionary.fields) == 0
    assert len(dictionary.field_groups) == 0
    assert len(dictionary._adapters) == 0