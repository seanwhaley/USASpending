"""Tests for configuration provider functionality."""
import pytest
from pathlib import Path
import yaml
from typing import Dict, Any
from pytest import FixtureRequest

from usaspending.config_provider import ConfigurationProvider
from usaspending.exceptions import ConfigurationError


@pytest.fixture
def valid_config() -> Dict[str, Any]:
    """Create valid test configuration."""
    return {
        'validation_types': {
            'string': [
                {'type': 'pattern', 'pattern': '[A-Za-z0-9\\s]+'},
                {'type': 'length', 'min': 1, 'max': 100}
            ],
            'number': [
                {'type': 'range', 'min': 0, 'max': 1000000}
            ]
        },
        'field_types': {
            'name': 'string',
            'amount': 'number'
        },
        'entities': {
            'test_entity': {
                'key_fields': ['id'],
                'field_mappings': {
                    'direct': {
                        'id': 'source_id',
                        'name': 'source_name'
                    }
                }
            }
        }
    }


@pytest.fixture
def mock_config_provider(valid_config: Dict[str, Any]) -> ConfigurationProvider:
    """Create configuration provider mock."""
    provider = ConfigurationProvider()
    provider._config = valid_config
    return provider


def test_config_provider_initialization() -> None:
    """Test provider initialization."""
    provider = ConfigurationProvider()
    assert provider._config == {}
    assert len(provider._errors) == 0


def test_load_config_success(tmp_path: Path, valid_config: Dict[str, Any]) -> None:
    """Test successful configuration loading."""
    config_file = tmp_path / "test_config.yaml"
    with open(config_file, 'w') as f:
        yaml.dump(valid_config, f)
    
    provider = ConfigurationProvider()
    provider.load_config(str(config_file))
    
    assert provider._config == valid_config
    assert len(provider.get_validation_errors()) == 0


def test_load_config_file_not_found() -> None:
    """Test configuration loading with non-existent file."""
    provider = ConfigurationProvider()
    with pytest.raises(ConfigurationError) as exc:
        provider.load_config("non_existent.yaml")
    assert "not found" in str(exc.value)


def test_load_config_invalid_yaml(tmp_path: Path) -> None:
    """Test loading invalid YAML configuration."""
    config_file = tmp_path / "invalid_config.yaml"
    with open(config_file, 'w') as f:
        f.write("invalid: yaml: content:")  # Invalid YAML
    
    provider = ConfigurationProvider()
    with pytest.raises(ConfigurationError) as exc:
        provider.load_config(str(config_file))
    assert "Failed to load" in str(exc.value)


def test_get_config_full(mock_config_provider: ConfigurationProvider, 
                        valid_config: Dict[str, Any]) -> None:
    """Test getting full configuration."""
    config = mock_config_provider.get_config()
    assert config == valid_config
    
    # Verify deep copy
    config['new_section'] = {}
    assert 'new_section' not in mock_config_provider._config


def test_get_config_section(mock_config_provider: ConfigurationProvider) -> None:
    """Test getting configuration section."""
    section = mock_config_provider.get_config('validation_types')
    assert 'string' in section
    assert 'number' in section


def test_get_config_missing_section(mock_config_provider: ConfigurationProvider) -> None:
    """Test getting non-existent configuration section."""
    section = mock_config_provider.get_config('non_existent')
    assert section == {}


def test_validate_config_success(mock_config_provider: ConfigurationProvider) -> None:
    """Test successful configuration validation."""
    assert mock_config_provider.validate_config() is True
    assert len(mock_config_provider.get_validation_errors()) == 0


def test_validate_config_missing_sections() -> None:
    """Test validation with missing required sections."""
    provider = ConfigurationProvider()
    provider._config = {'some_section': {}}
    
    assert provider.validate_config() is False
    errors = provider.get_validation_errors()
    assert len(errors) > 0
    assert 'Missing required sections' in errors[0]


def test_validate_config_invalid_validation_types(
    mock_config_provider: ConfigurationProvider) -> None:
    """Test validation with invalid validation types."""
    mock_config_provider._config['validation_types'] = []  # Should be dict
    
    assert mock_config_provider.validate_config() is False
    errors = mock_config_provider.get_validation_errors()
    assert len(errors) > 0
    assert 'validation_types must be a dictionary' in errors[0]


def test_validate_config_invalid_field_types(
    mock_config_provider: ConfigurationProvider) -> None:
    """Test validation with invalid field types."""
    mock_config_provider._config['field_types'] = []  # Should be dict
    
    assert mock_config_provider.validate_config() is False
    errors = mock_config_provider.get_validation_errors()
    assert len(errors) > 0
    assert 'field_types must be a dictionary' in errors[0]


def test_validate_config_invalid_entities(
    mock_config_provider: ConfigurationProvider) -> None:
    """Test validation with invalid entities."""
    mock_config_provider._config['entities'] = []  # Should be dict
    
    assert mock_config_provider.validate_config() is False
    errors = mock_config_provider.get_validation_errors()
    assert len(errors) > 0
    assert 'entities must be a dictionary' in errors[0]