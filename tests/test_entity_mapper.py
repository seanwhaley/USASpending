"""Tests for entity mapping functionality."""
import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any, Optional, List

from usaspending.entity_mapper import EntityMapper
from usaspending.exceptions import EntityMappingError
from usaspending.interfaces import IConfigurationProvider, IValidationMediator


class MockConfigProvider(IConfigurationProvider):
    """Mock configuration provider for testing."""
    
    def __init__(self, config: Dict[str, Any]):
        self._config = config
        self._errors: List[str] = []
    
    def get_config(self, section: Optional[str] = None) -> Dict[str, Any]:
        if not section:
            return self._config
        return self._config.get(section, {})
    
    def get_validation_errors(self) -> List[str]:
        return self._errors.copy()
    
    def validate_config(self) -> bool:
        return True


class MockValidationMediator(IValidationMediator):
    """Mock validation mediator for testing."""
    
    def __init__(self, should_validate: bool = True):
        self._should_validate = should_validate
        self._errors: List[str] = []
    
    def validate_entity(self, entity_type: str, data: Dict[str, Any]) -> bool:
        if not self._should_validate:
            self._errors.append(f"Entity validation failed for {entity_type}")
            return False
        return True
    
    def validate_field(self, field_name: str, value: Any, entity_type: Optional[str] = None) -> bool:
        if not self._should_validate:
            self._errors.append(f"Field validation failed for {field_name}")
            return False
        return True
    
    def get_validation_errors(self) -> List[str]:
        return self._errors.copy()


@pytest.fixture
def valid_config():
    """Create valid test configuration."""
    return {
        'entities': {
            'contract': {
                'entity_processing': {
                    'processing_order': 1
                },
                'key_fields': ['contract_id'],
                'field_mappings': {
                    'direct': {
                        'id': 'contract_id',
                        'contract_number': 'piid',
                        'description': 'description_of_requirement'
                    },
                    'multi_source': {
                        'period_of_performance': {
                            'sources': ['period_start_date', 'period_end_date'],
                            'strategy': 'first_non_empty'
                        }
                    },
                    'object': {
                        'location': {
                            'type': 'object',
                            'fields': {
                                'city': 'place_of_performance_city',
                                'state': 'place_of_performance_state'
                            }
                        }
                    },
                    'reference': {
                        'agency': {
                            'type': 'entity_reference',
                            'entity': 'agency',
                            'key_field': 'agency_id'
                        }
                    }
                }
            },
            'agency': {
                'entity_processing': {
                    'processing_order': 2
                },
                'field_mappings': {
                    'multi_source': {
                        'agency_code': {
                            'sources': ['awarding_agency_code', 'funding_agency_code'],
                            'strategy': 'first_non_empty'
                        },
                        'sub_agency_code': {
                            'sources': ['awarding_sub_agency_code', 'funding_sub_agency_code'],
                            'strategy': 'first_non_empty'
                        }
                    }
                }
            }
        },
        'field_properties': {
            'codes': {
                'fields': ['*_code', '*_id'],
                'validation': {
                    'type': 'string',
                    'pattern': '[A-Z0-9]+'
                }
            },
            'dates': {
                'fields': ['*_date'],
                'validation': {
                    'type': 'date'
                }
            }
        }
    }


@pytest.fixture
def mock_config_provider(valid_config):
    """Create configuration provider mock."""
    return MockConfigProvider(valid_config)


@pytest.fixture
def mock_validation_mediator():
    """Create validation mediator mock."""
    return MockValidationMediator()


@pytest.fixture
def entity_mapper(mock_config_provider, mock_validation_mediator):
    """Create entity mapper with mocked dependencies."""
    return EntityMapper(mock_config_provider, mock_validation_mediator)


def test_entity_mapper_initialization(entity_mapper, mock_config_provider, mock_validation_mediator):
    """Test mapper initialization."""
    assert entity_mapper._config_provider == mock_config_provider
    assert entity_mapper._validation_mediator == mock_validation_mediator
    assert entity_mapper.entities == mock_config_provider.get_config('entities')
    assert len(entity_mapper.entity_order) > 0


def test_determine_entity_type(entity_mapper):
    """Test entity type determination."""
    # Contract data
    contract_data = {
        'contract_id': 'C123',
        'piid': 'PIID123'
    }
    assert entity_mapper._determine_entity_type(contract_data) == 'contract'

    # Agency data
    agency_data = {
        'awarding_agency_code': 'AG01',
        'awarding_sub_agency_code': 'SA01'
    }
    assert entity_mapper._determine_entity_type(agency_data) == 'agency'

    # Unknown data
    unknown_data = {
        'some_field': 'value'
    }
    assert entity_mapper._determine_entity_type(unknown_data) is None


def test_check_key_fields(entity_mapper):
    """Test key field checking."""
    # Check contract key fields
    contract_data = {'contract_id': 'C123'}
    assert entity_mapper._check_key_fields(contract_data, 'contract') is True

    # Check agency key fields
    agency_data = {
        'awarding_agency_code': 'AG01',
        'awarding_sub_agency_code': 'SA01'
    }
    assert entity_mapper._check_key_fields(agency_data, 'agency') is True

    # Check missing key fields
    incomplete_data = {'other_field': 'value'}
    assert entity_mapper._check_key_fields(incomplete_data, 'contract') is False


def test_map_entity_success(entity_mapper):
    """Test successful entity mapping."""
    data = {
        'contract_id': 'C123',
        'piid': 'PIID123',
        'description_of_requirement': 'Test contract',
        'place_of_performance_city': 'Test City',
        'place_of_performance_state': 'TS',
        'agency_id': 'AG01'
    }
    
    result = entity_mapper.map_entity(data)
    
    assert result['entity_type'] == 'contract'
    assert result['id'] == 'C123'
    assert result['contract_number'] == 'PIID123'
    assert result['description'] == 'Test contract'
    assert 'location' in result
    assert result['location']['city'] == 'Test City'
    assert result['location']['state'] == 'TS'
    assert 'agency' in result
    assert result['agency']['entity_type'] == 'agency'


def test_map_entity_validation_failure(entity_mapper, mock_validation_mediator):
    """Test entity mapping with validation failure."""
    # Configure validator to fail
    mock_validation_mediator._should_validate = False
    
    data = {'contract_id': 'C123'}
    result = entity_mapper.map_entity(data)
    
    assert result == {}
    assert len(entity_mapper.get_mapping_errors()) > 0


def test_map_entity_unsupported_type(entity_mapper):
    """Test mapping unsupported entity type."""
    data = {'unknown_field': 'value'}
    result = entity_mapper.map_entity(data)
    
    assert result == {}


def test_generate_agency_key(entity_mapper):
    """Test agency key generation."""
    # Complete agency data
    data = {
        'awarding_agency_code': 'AG01',
        'awarding_sub_agency_code': 'SA01',
        'awarding_office_code': 'OF01'
    }
    multi_source = {
        'agency_code': {'sources': ['awarding_agency_code', 'funding_agency_code']},
        'sub_agency_code': {'sources': ['awarding_sub_agency_code', 'funding_sub_agency_code']},
        'office_code': {'sources': ['awarding_office_code', 'funding_office_code']}
    }
    
    key = entity_mapper._generate_agency_key(data, multi_source)
    assert key == 'AG01:SA01:OF01'

    # Minimal agency data
    minimal_data = {'awarding_agency_code': 'AG01'}
    key = entity_mapper._generate_agency_key(minimal_data, multi_source)
    assert key == 'AG01'

    # Invalid agency data
    invalid_data = {'awarding_sub_agency_code': 'SA01'}
    key = entity_mapper._generate_agency_key(invalid_data, multi_source)
    assert key is None


def test_apply_multi_source_mappings(entity_mapper):
    """Test multi-source field mapping."""
    data = {
        'period_start_date': '2024-01-01',
        'period_end_date': '2024-12-31'
    }
    mappings = {
        'period': {
            'sources': ['period_start_date', 'period_end_date'],
            'strategy': 'first_non_empty'
        }
    }
    
    result = entity_mapper._apply_multi_source_mappings(data, mappings)
    assert 'period' in result
    assert result['period'] == '2024-01-01'


def test_apply_object_mappings(entity_mapper):
    """Test object field mapping."""
    data = {
        'place_of_performance_city': 'Test City',
        'place_of_performance_state': 'TS'
    }
    mappings = {
        'location': {
            'type': 'object',
            'fields': {
                'city': 'place_of_performance_city',
                'state': 'place_of_performance_state'
            }
        }
    }
    
    result = entity_mapper._apply_object_mappings(data, mappings)
    assert 'location' in result
    assert result['location']['city'] == 'Test City'
    assert result['location']['state'] == 'TS'


def test_apply_reference_mappings(entity_mapper):
    """Test reference field mapping."""
    data = {'agency_id': 'AG01'}
    mappings = {
        'agency': {
            'type': 'entity_reference',
            'entity': 'agency',
            'key_field': 'agency_id'
        }
    }
    
    result = entity_mapper._apply_reference_mappings(data, mappings)
    assert 'agency' in result
    assert result['agency']['entity_type'] == 'agency'
    assert result['agency']['data']['id'] == 'AG01'


def test_mapping_stats(entity_mapper):
    """Test mapping statistics."""
    data = {
        'contract_id': 'C123',
        'piid': 'PIID123'
    }
    entity_mapper.map_entity(data)
    
    stats = entity_mapper.get_mapping_stats()
    assert 'mapped_fields' in stats
    assert stats['mapped_fields'] > 0
    assert 'cache_size' in stats
    assert 'error_count' in stats


def test_error_handling(entity_mapper, mock_validation_mediator):
    """Test error handling during mapping."""
    # Test validation error
    mock_validation_mediator._should_validate = False
    data = {'contract_id': 'C123'}
    result = entity_mapper.map_entity(data)
    
    assert result == {}
    assert len(entity_mapper.get_mapping_errors()) > 0
    
    # Test mapping error with invalid configuration
    with patch.object(entity_mapper, '_apply_direct_mappings', side_effect=Exception("Mapping error")):
        with pytest.raises(EntityMappingError) as exc:
            entity_mapper.map_entity(data)
        assert "Mapping error" in str(exc.value)


def test_cache_management(entity_mapper):
    """Test cache management."""
    # Initial cache state
    assert len(entity_mapper._mapping_cache) == 0
    assert len(entity_mapper._mapped_fields) == 0
    
    # Map an entity to populate cache
    data = {'contract_id': 'C123'}
    entity_mapper.map_entity(data)
    
    assert len(entity_mapper._mapping_cache) > 0
    assert len(entity_mapper._mapped_fields) > 0
    
    # Clear caches
    entity_mapper.clear_caches()
    
    assert len(entity_mapper._mapping_cache) == 0
    assert len(entity_mapper._mapped_fields) == 0