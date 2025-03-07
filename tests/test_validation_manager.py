"""Tests for validation manager functionality."""
import pytest
from usaspending.validation_manager import ValidationManager, ValidationGroup, FieldDependency
from usaspending.exceptions import ConfigurationError

@pytest.fixture
def sample_config():
    """Return sample configuration for testing."""
    return {
        'validation_groups': {
            'amount_validation': {
                'name': 'Amount Validation',
                'rules': ['compare:less_than_equal:maximum_amount'],
                'enabled': True,
                'error_level': 'error'
            },
            'date_validation': {
                'name': 'Date Validation',
                'rules': ['compare:greater_than:start_date'],
                'enabled': True,
                'error_level': 'error',
                'dependencies': ['amount_validation']
            }
        },
        'field_properties': {
            'start_date': {
                'type': 'date'
            },
            'end_date': {
                'type': 'date',
                'validation': {
                    'groups': ['date_validation'],
                    'dependencies': [
                        {
                            'type': 'comparison',
                            'target_field': 'start_date',
                            'validation_rule': {
                                'operator': 'greater_than'
                            }
                        }
                    ]
                }
            },
            'award_amount': {
                'type': 'decimal',
                'validation': {
                    'groups': ['amount_validation'],
                    'dependencies': [
                        {
                            'type': 'comparison',
                            'target_field': 'maximum_amount',
                            'validation_rule': {
                                'operator': 'less_than_equal'
                            }
                        }
                    ]
                }
            },
            'maximum_amount': {
                'type': 'decimal'
            }
        }
    }

def test_validation_manager_init(sample_config):
    """Test ValidationManager initialization."""
    manager = ValidationManager(sample_config)
    
    # Check validation groups loaded
    assert len(manager.validation_groups) == 2
    assert 'amount_validation' in manager.validation_groups
    assert 'date_validation' in manager.validation_groups
    
    # Check field dependencies loaded
    assert len(manager.field_dependencies) == 2
    assert 'end_date' in manager.field_dependencies
    assert 'award_amount' in manager.field_dependencies

def test_circular_group_dependencies():
    """Test detection of circular dependencies in validation groups."""
    config = {
        'validation_groups': {
            'group1': {
                'name': 'Group 1',
                'rules': ['rule1'],
                'dependencies': ['group2']
            },
            'group2': {
                'name': 'Group 2',
                'rules': ['rule2'],
                'dependencies': ['group1']
            }
        }
    }
    
    with pytest.raises(ConfigurationError, match="Circular dependency detected in validation groups"):
        ValidationManager(config)

def test_circular_field_dependencies():
    """Test detection of circular dependencies in fields."""
    config = {
        'field_properties': {
            'field1': {
                'type': 'string',
                'validation': {
                    'dependencies': [
                        {
                            'type': 'comparison',
                            'target_field': 'field2'
                        }
                    ]
                }
            },
            'field2': {
                'type': 'string',
                'validation': {
                    'dependencies': [
                        {
                            'type': 'comparison',
                            'target_field': 'field1'
                        }
                    ]
                }
            }
        }
    }
    
    with pytest.raises(ConfigurationError, match="Circular dependency detected in field dependencies"):
        ValidationManager(config)

def test_missing_dependencies():
    """Test validation of missing dependencies."""
    config = {
        'validation_groups': {
            'test_group': {
                'name': 'Test Group',
                'rules': ['rule1'],
                'dependencies': ['nonexistent_group']
            }
        }
    }
    
    with pytest.raises(ConfigurationError, match="references non-existent groups"):
        ValidationManager(config)

def test_validation_order(sample_config):
    """Test computation of validation order."""
    manager = ValidationManager(sample_config)
    order = manager.get_validation_order()
    
    # Check start_date comes before end_date
    start_idx = order.index('start_date')
    end_idx = order.index('end_date')
    assert start_idx < end_idx
    
    # Check maximum_amount comes before award_amount
    max_idx = order.index('maximum_amount')
    award_idx = order.index('award_amount')
    assert max_idx < award_idx

def test_get_group_rules(sample_config):
    """Test retrieval of validation group rules."""
    manager = ValidationManager(sample_config)
    
    # Test existing group
    rules = manager.get_group_rules('amount_validation')
    assert len(rules) == 1
    assert rules[0] == 'compare:less_than_equal:maximum_amount'
    
    # Test nonexistent group
    rules = manager.get_group_rules('nonexistent')
    assert not rules

def test_disabled_validation_group(sample_config):
    """Test handling of disabled validation groups."""
    # Disable a group
    sample_config['validation_groups']['amount_validation']['enabled'] = False
    
    manager = ValidationManager(sample_config)
    rules = manager.get_group_rules('amount_validation')
    assert not rules

def test_get_field_dependencies(sample_config):
    """Test retrieval of field dependencies."""
    manager = ValidationManager(sample_config)
    
    # Test field with dependencies
    deps = manager.get_field_dependencies('end_date')
    assert len(deps) == 1
    assert deps[0].target_field == 'start_date'
    assert deps[0].type == 'comparison'
    
    # Test field without dependencies
    deps = manager.get_field_dependencies('start_date')
    assert not deps

def test_empty_config():
    """Test initialization with empty configuration."""
    manager = ValidationManager({})
    assert not manager.validation_groups
    assert not manager.field_dependencies