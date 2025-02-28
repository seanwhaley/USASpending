"""Test configuration functionality."""
import pytest
from pathlib import Path
import yaml
from usaspending.config import load_config, validate_contracts_config

def test_validate_contracts_config(sample_config):
    """Test that a valid configuration passes validation."""
    assert validate_contracts_config(sample_config) is True

def test_invalid_config_missing_section():
    """Test that missing sections raise appropriate errors."""
    invalid_config = {
        "contracts": {
            "output": {},  # Missing required sections
        }
    }
    with pytest.raises(ValueError, match="Missing required section 'contracts.input'"):
        validate_contracts_config(invalid_config)

def test_invalid_config_wrong_type():
    """Test that wrong types raise appropriate errors."""
    invalid_config = {
        "contracts": {
            "input": {
                "file": "test.csv",
                "batch_size": "1000"  # Should be int, not str
            },
            "output": {
                "main_file": "out.json",
                "indent": 2,
                "ensure_ascii": False
            },
            "chunking": {
                "enabled": True,
                "records_per_chunk": 1000,
                "create_index": True
            },
            "type_conversion": {
                "date_fields": [],
                "numeric_fields": [],
                "boolean_true_values": [],
                "boolean_false_values": []
            }
        }
    }
    with pytest.raises(ValueError, match="batch_size must be an integer"):
        validate_contracts_config(invalid_config)

def test_load_config_file_not_found():
    """Test that non-existent config file raises appropriate error."""
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent.yaml")

def test_load_config_success(tmp_path: Path, sample_config):
    """Test successful config loading from file."""
    config_file = tmp_path / "test_config.yaml"
    with open(config_file, 'w') as f:
        yaml.dump(sample_config, f)
    
    loaded_config = load_config(str(config_file))
    assert loaded_config == sample_config