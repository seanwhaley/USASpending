"""Tests for validation groups and field dependencies."""
import pytest
from decimal import Decimal
from datetime import date
from typing import Dict, Any
import collections

from usaspending.validation import ValidationEngine, ValidationGroupManager
from usaspending.field_dependencies import FieldDependencyManager

@pytest.fixture
def sample_config() -> Dict[str, Any]:
    """Sample configuration with validation groups and field dependencies."""
    return {
        'validation_groups': {
            'amount_validation': {
                'name': 'Amount Validation',
                'description': 'Validates monetary amounts and relationships',
                'enabled': True,
                'rules': [
                    'compare:greater_than:maximum_amount',  # Changed from less_than to greater_than
                ],
                'error_level': 'error'
            },
            'date_validation': {
                'name': 'Date Validation',
                'description': 'Validates date relationships',
                'enabled': True,
                'rules': [
                    'compare:greater_than:start_date',  # Changed order of date comparison
                    'compare:less_than:end_date'
                ],
                'error_level': 'error'
            }
        },
        'field_properties': {
            'award_amount': {
                'type': 'decimal',
                'validation': {
                    'groups': ['amount_validation'],
                    'min_value': Decimal('0.0'),
                    'precision': 2,
                    'comparable_types': ['decimal']
                }
            },
            'maximum_amount': {
                'type': 'decimal',
                'validation': {
                    'groups': ['amount_validation'],
                    'min_value': Decimal('0.0'),
                    'precision': 2,
                    'comparable_types': ['decimal']
                }
            },
            'start_date': {
                'type': 'date',
                'validation': {
                    'groups': ['date_validation'],
                    'comparable_types': ['date']
                }
            },
            'end_date': {
                'type': 'date',
                'validation': {
                    'groups': ['date_validation'],
                    'comparable_types': ['date']
                }
            }
        }
    }

def test_validation_group_manager(sample_config):
    """Test validation group manager initialization and rule retrieval."""
    manager = ValidationGroupManager(sample_config)
    
    # Test group existence and properties
    assert manager.is_group_enabled('amount_validation')
    assert manager.is_group_enabled('date_validation')
    assert not manager.is_group_enabled('nonexistent_group')
    
    # Test rule retrieval
    amount_rules = manager.get_group_rules('amount_validation')
    assert len(amount_rules) == 1
    assert 'compare:greater_than:maximum_amount' in amount_rules
    
    # Test dependency resolution
    date_rules = manager.get_group_rules('date_validation')
    assert len(date_rules) == 2
    assert 'compare:greater_than:start_date' in date_rules
    assert 'compare:less_than:end_date' in date_rules
    
    # Test error levels
    assert manager.get_group_error_level('amount_validation') == 'error'
    assert manager.get_group_error_level('nonexistent_group') == 'error'  # Default

def test_field_dependencies(sample_config):
    """Test field dependency tracking and validation."""
    engine = ValidationEngine(sample_config)
    
    # Test valid record
    record = {
        'award_amount': Decimal('2000.00'),  # Should be greater than maximum_amount
        'maximum_amount': Decimal('1000.00'),
        'start_date': date(2024, 1, 1),
        'end_date': date(2024, 12, 31)
    }
    results = engine.validate_record(record)
    assert not results  # No validation errors
    
    # Test invalid amount relationship
    record['award_amount'] = Decimal('500.00')  # Lower than maximum_amount
    results = engine.validate_record(record)
    assert len(results) == 1
    assert results[0].field_name == 'award_amount'
    assert not results[0].valid
    
    # Test invalid date relationship
    record['award_amount'] = Decimal('2000.00')
    record['start_date'] = date(2024, 12, 1)  # Start date after end date
    results = engine.validate_record(record)
    assert len(results) == 1
    assert results[0].field_name == 'start_date'
    assert not results[0].valid

def test_validation_ordering(sample_config):
    """Test that validation occurs in the correct dependency order."""
    # Add the field before creating the engine
    sample_config['field_properties']['calculated_total'] = {
        'type': 'decimal',
        'validation': {
            'groups': ['amount_validation'],
            'dependencies': [{
                'type': 'derived',
                'target_field': 'award_amount'
            }]
        }
    }
    
    # Now create the engine with the complete config
    engine = ValidationEngine(sample_config)
    
    record = {
        'award_amount': Decimal('1000.00'),
        'calculated_total': Decimal('1000.00'),
        'maximum_amount': Decimal('2000.00')
    }

    # Validate that award_amount is validated before calculated_total
    validation_order = engine.dependency_manager.get_validation_order()
    award_idx = validation_order.index('award_amount')
    calc_idx = validation_order.index('calculated_total')
    
    assert award_idx < calc_idx, "award_amount should be validated before calculated_total"

def test_conditional_validation(sample_config):
    """Test conditional validation rules."""
    config = sample_config
    config['field_properties']['payment_type'] = {
        'type': 'string',
        'validation': {
            'values': ['advance', 'reimbursement'],
            'conditional_rules': {
                'advance': {
                    'pattern': r'^ADV\d{6}$',
                    'error_message': 'Advance payment code must be ADV followed by 6 digits'
                },
                'reimbursement': {
                    'pattern': r'^REI\d{6}$',
                    'error_message': 'Reimbursement code must be REI followed by 6 digits'
                }
            }
        }
    }
    
    engine = ValidationEngine(config)
    
    # Test valid advance payment
    record = {'payment_type': 'advance', 'payment_code': 'ADV123456'}
    results = engine.validate_record(record)
    assert not results
    
    # Test invalid advance payment
    record['payment_code'] = 'REI123456'
    results = engine.validate_record(record)
    assert len(results) == 1
    assert 'ADV' in results[0].error_message
    
    # Test valid reimbursement
    record = {'payment_type': 'reimbursement', 'payment_code': 'REI123456'}
    results = engine.validate_record(record)
    assert not results

def test_circular_dependency_detection(sample_config):
    """Test detection of circular dependencies in validation groups."""
    config = dict(sample_config)  # Create a copy to avoid modifying the fixture
    config['validation_groups']['circular_group1'] = {
        'name': 'Circular Group 1',
        'rules': ['rule1'],
        'dependencies': ['circular_group2']
    }
    config['validation_groups']['circular_group2'] = {
        'name': 'Circular Group 2',
        'rules': ['rule2'],
        'dependencies': ['circular_group1']
    }
    
    with pytest.raises(ValueError) as exc_info:
        ValidationGroupManager(config)
    assert "Circular dependency" in str(exc_info.value)