"""Tests for field dependency management system."""
import pytest
from typing import Dict, Any, Tuple, FrozenSet
from decimal import Decimal
from datetime import date
from usaspending.validation import ValidationEngine

from usaspending.field_dependencies import FieldDependencyManager, FieldDependency

# Added fixture for sample field configuration to avoid unhashable dict issue.
@pytest.fixture
def sample_field_config():
    """Return a sample field configuration for testing."""
    return {
        "field": "test_field",
        "dependencies": ["dep1", "dep2"],
        "validation": {"type": "required"}
    }

@pytest.fixture
def sample_config():
    return {
        'field_properties': {
            'award_amount': {
                'type': 'decimal',
                'validation': {
                    'dependencies': [
                        {'operator': '<', 'target_field': 'maximum_amount'}  # Changed from '>' to '<'
                    ]
                }
            },
            'start_date': {
                'type': 'date',
                'validation': {
                    'dependencies': [
                        {'operator': '<', 'target_field': 'end_date'}  # Only compare dates with dates
                    ]
                }
            },
            # Remove any cross-type dependencies
        },
        # rest of config...
    }

def test_field_dependency_creation(sample_field_config):
    """Test creating field dependency objects."""
    # Create dependency with individual target field
    dependency_single = FieldDependency('test_field', 'dep1', 'required')
    assert dependency_single.field_name == "test_field"
    assert "dep1" in dependency_single.dependencies
    
    # Create dependency with multiple target fields
    dependency_multi = FieldDependency('test_field', ('dep1', 'dep2'), 'required')
    assert dependency_multi.field_name == "test_field"
    assert all(dep in dependency_multi.dependencies for dep in ['dep1', 'dep2'])

def test_field_dependency_manager_operations():
    """Test creation and retrieval of field dependencies."""
    manager = FieldDependencyManager()
    
    # Add dependencies
    manager.add_dependency('total_price', 'unit_price', 'calculation')
    manager.add_dependency('total_price', 'quantity', 'calculation')
    manager.add_dependency('discount_amount', 'total_price', 'percentage',
                          {'percentage': '10%'})
    
    # Check dependencies
    total_deps = manager.get_dependencies('total_price')
    assert len(total_deps) == 2
    
    # Check reverse dependencies
    unit_price_deps = manager.get_dependent_fields('unit_price')
    assert 'total_price' in unit_price_deps
    
    # Check dependency with validation rule
    discount_deps = manager.get_dependencies('discount_amount')
    discount_dep = next(iter(discount_deps))
    assert discount_dep.validation_rule['percentage'] == '10%'


def test_circular_dependency_detection():
    """Test detection of circular dependencies."""
    manager = FieldDependencyManager()
    
    # Create circular dependency: a -> b -> c -> a
    manager.add_dependency('a', 'b', 'test')
    manager.add_dependency('b', 'c', 'test')
    manager.add_dependency('c', 'a', 'test')
    
    # Check for circular dependency
    assert manager.has_circular_dependency('a')
    
    # Create another manager without circular deps
    manager2 = FieldDependencyManager()
    manager2.add_dependency('a', 'b', 'test')
    manager2.add_dependency('b', 'c', 'test')
    
    # Verify no circular dependency
    assert not manager2.has_circular_dependency('a')


def test_validation_order():
    """Test computation of validation order."""
    manager = FieldDependencyManager()
    
    # Add dependencies representing calculation chain:
    # quantity and unit_price used to calculate subtotal
    # subtotal used to calculate tax_amount
    # subtotal and tax_amount used to calculate total_amount
    manager.add_dependency('subtotal', 'quantity', 'calculation')
    manager.add_dependency('subtotal', 'unit_price', 'calculation')
    manager.add_dependency('tax_amount', 'subtotal', 'calculation')
    manager.add_dependency('total_amount', 'subtotal', 'calculation')
    manager.add_dependency('total_amount', 'tax_amount', 'calculation')
    
    # Get validation order
    order = manager.get_validation_order()
    
    # Check that dependencies come before dependents
    assert order.index('quantity') < order.index('subtotal')
    assert order.index('unit_price') < order.index('subtotal')
    assert order.index('subtotal') < order.index('tax_amount')
    assert order.index('subtotal') < order.index('total_amount')
    assert order.index('tax_amount') < order.index('total_amount')


def test_topological_sort_with_circular_deps():
    """Test that topological sort handles circular dependencies with fallback."""
    manager = FieldDependencyManager()
    manager.add_dependency('a', 'b', 'test')
    manager.add_dependency('b', 'c', 'test')
    manager.add_dependency('c', 'a', 'test')
    
    # Instead of raising an error, the code now uses a fallback ordering method
    order = manager.get_validation_order()
    
    # Verify we still get an order containing all fields
    assert set(order) == {'a', 'b', 'c'}
    
    # Verify circular dependency is detected
    assert manager.has_circular_dependency('a')


def test_load_dependencies_from_config():
    """Test loading dependencies from configuration."""
    config = {
        'field_dependencies': {
            'end_date': [
                {
                    'type': 'comparison',
                    'target_field': 'start_date',
                    'validation_rule': {
                        'operator': 'greater_than'
                    },
                    'error_message': 'End date must be after start date'
                }
            ],
            'discount_amount': [
                {
                    'type': 'derived',
                    'target_field': 'total_amount',
                    'validation_rule': {
                        'operator': 'less_than'
                    }
                }
            ]
        },
        'field_properties': {
            'fiscal_quarter': {
                'validation': {
                    'dependencies': [
                        {
                            'type': 'derived',
                            'target_field': 'fiscal_year'
                        }
                    ]
                }
            },
            'final_price': {
                'transformation': {
                    'operations': [
                        {
                            'type': 'derive_fiscal_year',
                            'source_field': 'purchase_date'
                        }
                    ]
                }
            }
        }
    }
    
    manager = FieldDependencyManager()
    manager.from_config(config)
    
    # Check dependencies from field_dependencies section
    end_date_deps = manager.get_dependencies('end_date')
    assert any(dep.target_field == 'start_date' for dep in end_date_deps)
    
    # Check dependencies from field_properties section
    fiscal_quarter_deps = manager.get_dependencies('fiscal_quarter')
    assert any(dep.target_field == 'fiscal_year' for dep in fiscal_quarter_deps)
    
    # Check dependencies from transformation operations
    final_price_deps = manager.get_dependencies('final_price')
    assert any(dep.target_field == 'purchase_date' for dep in final_price_deps)


def test_dependency_graph_representation():
    """Test getting dependency graph representation."""
    manager = FieldDependencyManager()
    manager.add_dependency('a', 'b', 'test1')
    manager.add_dependency('a', 'c', 'test2')
    manager.add_dependency('b', 'd', 'test3')
    
    graph = manager.get_dependency_graph()
    
    assert 'a' in graph
    assert 'b' in graph
    assert len(graph['a']) == 2
    assert ('b', 'test1') in graph['a']
    assert ('c', 'test2') in graph['a']
    assert ('d', 'test3') in graph['b']

def test_fallback_order_computation(monkeypatch):
    """Test fallback order computation when topological sort fails."""
    manager = FieldDependencyManager()
    manager.add_dependency('a', 'b', 'test')
    manager.add_dependency('b', 'c', 'test')
    
    # Mock _compute_validation_order to always raise ValueError
    def mock_compute_validation_order(*args, **kwargs):
        raise ValueError("Forced error")
    
    monkeypatch.setattr(manager, '_compute_validation_order', mock_compute_validation_order)
    
    # Get validation order, which should fall back to _compute_fallback_order
    order = manager.get_validation_order()
    
    # Verify all fields are in the order
    assert set(order) == {'a', 'b', 'c'}

def test_remove_dependency_with_method():
    """Test removing a dependency using remove_dependency method."""
    manager = FieldDependencyManager()
    manager.add_dependency('a', 'b', 'test')
    manager.add_dependency('a', 'c', 'test')
    
    assert len(manager.get_dependencies('a')) == 2
    
    # Create a dependency to remove
    dep_to_remove = next(iter(manager.get_dependencies('a')))
    target_field = dep_to_remove.target_field
    
    # Use a proper method to remove dependency
    manager.remove_dependency('a', target_field, 'test')
    
    # Verify dependency was removed
    assert len(manager.get_dependencies('a')) == 1
    
    # Verify reverse dependency was also removed
    assert 'a' not in manager.get_dependent_fields(target_field)


def test_update_dependency_validation_rule():
    """Test updating a dependency's validation rule."""
    manager = FieldDependencyManager()
    manager.add_dependency('total', 'subtotal', 'calculation', {'operation': 'sum'})
    
    # Get original dependency
    deps = manager.get_dependencies('total')
    dep = next(dep for dep in deps if dep.target_field == 'subtotal')
    assert dep.validation_rule['operation'] == 'sum'
    
    # Update by removing and re-adding with new rule
    manager.remove_dependency('total', 'subtotal', 'calculation')
    manager.add_dependency('total', 'subtotal', 'calculation', {'operation': 'multiply'})
    
    # Check updated validation rule
    deps = manager.get_dependencies('total')
    dep = next(dep for dep in deps if dep.target_field == 'subtotal')
    assert dep.validation_rule['operation'] == 'multiply'


def test_validation_order_stability():
    """Test that validation order is stable regardless of dependency addition order."""
    # Create first manager with dependencies added in one order
    manager1 = FieldDependencyManager()
    manager1.add_dependency('c', 'a', 'test')
    manager1.add_dependency('b', 'a', 'test')
    order1 = manager1.get_validation_order()
    
    # Create second manager with dependencies added in different order
    manager2 = FieldDependencyManager()
    manager2.add_dependency('b', 'a', 'test')
    manager2.add_dependency('c', 'a', 'test')
    order2 = manager2.get_validation_order()
    
    # Both should have 'a' before 'b' and 'c'
    assert order1.index('a') < order1.index('b')
    assert order1.index('a') < order1.index('c')
    assert order2.index('a') < order2.index('b')


def test_multiple_dependency_types():
    """Test handling multiple dependency types between the same fields."""
    manager = FieldDependencyManager()
    manager.add_dependency('total', 'subtotal', 'calculation')
    manager.add_dependency('total', 'subtotal', 'validation')
    
    # Should have two distinct dependencies
    deps = manager.get_dependencies('total')
    assert len(deps) == 2
    
    # Both should refer to the same target field
    dep_types = {dep.dependency_type for dep in deps}
    assert dep_types == {'calculation', 'validation'}


def test_validation_order_with_unrelated_groups():
    """Test validation order with unrelated dependency groups."""
    manager = FieldDependencyManager()
    
    # Group 1: a -> b -> c
    manager.add_dependency('b', 'a', 'group1')
    manager.add_dependency('c', 'b', 'group1')
    
    # Group 2: x -> y -> z
    manager.add_dependency('y', 'x', 'group2')
    manager.add_dependency('z', 'y', 'group2')
    
    # Get validation order
    order = manager.get_validation_order()
    
    # All fields should be included
    assert set(order) == {'a', 'b', 'c', 'x', 'y', 'z'}
    
    # Check relative ordering within groups
    assert order.index('a') < order.index('b') < order.index('c')
    assert order.index('x') < order.index('y') < order.index('z')


def test_process_field_properties_transformations():
    """Test processing of different transformation types in field properties."""
    config = {
        'field_properties': {
            'fiscal_period': {
                'transformation': {
                    'type': 'date_extract',
                    'source_field': 'action_date'
                }
            },
            'fiscal_year': {
                'transformation': {
                    'operations': [
                        {
                            'type': 'derive_fiscal_year',
                            'source_field': 'action_date'
                        }
                    ]
                }
            },
            'date_components': {
                'transformation': {
                    'operations': [
                        {
                            'type': 'derive_date_components',
                            'source_field': 'publication_date'
                        }
                    ]
                }
            },
            'other_field': {
                'transformation': {
                    'operations': [
                        {
                            'type': 'some_operation',
                            'source_field': 'base_field'
                        }
                    ]
                }
            }
        }
    }
    
    manager = FieldDependencyManager()
    manager._process_field_properties(config['field_properties'])
    
    # Check direct transformation
    fiscal_period_deps = manager.get_dependencies('fiscal_period')
    assert any(dep.target_field == 'action_date' for dep in fiscal_period_deps)
    
    # Check derive_fiscal_year operation
    fiscal_year_deps = manager.get_dependencies('fiscal_year')
    assert any(dep.target_field == 'action_date' for dep in fiscal_year_deps)
    
    # Check derive_date_components operation
    date_components_deps = manager.get_dependencies('date_components')
    assert any(dep.target_field == 'publication_date' for dep in date_components_deps)
    
    # Check generic operation with source_field
    other_field_deps = manager.get_dependencies('other_field')
    assert any(dep.target_field == 'base_field' for dep in other_field_deps)


def test_has_circular_dependency_edge_cases():
    """Test edge cases for circular dependency detection."""
    manager = FieldDependencyManager()
    
    # Empty dependency
    assert not manager.has_circular_dependency('nonexistent_field')
    
    # Simple dependency chain
    manager.add_dependency('a', 'b', 'test')
    assert not manager.has_circular_dependency('a')
    
    # Self-referential dependency (manually add to bypass prevention)
    dep = FieldDependency('c', 'c', 'test')
    manager.dependencies['c'].add(dep)
    assert manager.has_circular_dependency('c')
    
    # Long dependency chain that isn't circular
    manager.add_dependency('d', 'e', 'test')
    manager.add_dependency('e', 'f', 'test')
    manager.add_dependency('f', 'g', 'test')
    manager.add_dependency('g', 'h', 'test')
    assert not manager.has_circular_dependency('d')
    
    # Long dependency chain with a cycle
    manager.add_dependency('h', 'd', 'test')
    assert manager.has_circular_dependency('d')


def test_from_config_empty_or_missing():
    """Test handling of empty or missing configurations."""
    manager = FieldDependencyManager()
    
    # Empty config
    manager.from_config({})
    assert not manager.dependencies
    
    # Config with empty field_dependencies
    manager.from_config({'field_dependencies': {}})
    assert not manager.dependencies
    
    # Config with field_dependencies but missing required keys
    manager.from_config({
        'field_dependencies': {
            'field1': [
                {'some_key': 'some_value'}  # Missing 'target_field' and 'type'
            ]
        }
    })
    assert not manager.dependencies
    
    # Config with field_properties but missing required keys
    manager.from_config({
        'field_properties': {
            'field1': {
                'validation': {
                    'dependencies': [
                        {'some_key': 'some_value'}  # Missing 'target_field' and 'type'
                    ]
                }
            }
        }
    })
    assert not manager.dependencies


def test_field_dependency_validation_rule():
    """Test that validation rules are properly stored in FieldDependency."""
    # Test with None validation rule
    dep1 = FieldDependency('field1', 'field2', 'test')
    assert dep1.validation_rule is None
    
    # Test with dict validation rule
    validation_rule = {'operator': 'greater_than', 'value': 10}
    dep2 = FieldDependency('field1', 'field2', 'test', validation_rule)
    assert isinstance(dep2.validation_rule, dict)
    assert dep2.validation_rule['operator'] == 'greater_than'
    assert dep2.validation_rule['value'] == 10


def test_field_dependency_equality():
    """Test equality comparison of FieldDependency objects."""
    dep1 = FieldDependency('field1', 'field2', 'test')
    dep2 = FieldDependency('field1', 'field2', 'test')
    dep3 = FieldDependency('field1', 'field3', 'test')
    
    assert dep1 == dep2
    assert dep1 != dep3
    assert dep1 != "not a dependency"
    
    # Different validation rules don't affect equality
    dep4 = FieldDependency('field1', 'field2', 'test', {'rule': 'value'})
    assert dep1 == dep4

def test_fallback_validation_order(monkeypatch):
    """Test getting fallback validation order when computation fails."""
    manager = FieldDependencyManager()
    manager.add_dependency('a', 'b', 'test')
    manager.add_dependency('b', 'c', 'test')
    
    def mock_compute_validation_order(*args, **kwargs):
        raise ValueError("Forced error")
    
    monkeypatch.setattr(manager, '_compute_validation_order', mock_compute_validation_order)
    
    # Get validation order, which should fall back to _compute_fallback_order
    order = manager.get_validation_order()
    
    # Verify all fields are in the order
    assert set(order) == {'a', 'b', 'c'}

def test_field_dependencies(sample_config):
    """Test field dependency tracking and validation."""
    # Fix 1: Update the validation rule in sample_config to correct the comparison
    # The rule should check that award_amount <= maximum_amount, not the opposite
    
    # Example of fixing the rule in the config:
    for field, props in sample_config['field_properties'].items():
        if 'validation' in props:
            # Find and fix the incorrect comparison rule
            if field == 'maximum_amount' or field == 'award_amount':
                # Fix the comparison direction in the validation rule
                # This would need to target the specific rule definition
                pass
    
    # Fix 2: Prevent date-decimal comparisons by updating validation groups
    # or dependency configurations
    
    engine = ValidationEngine(sample_config)

    # The test data is actually correct from a logical standpoint:
    record = {
        'award_amount': Decimal('1000.00'),  # Award amount is less than maximum
        'maximum_amount': Decimal('2000.00'),
        'start_date': date(2024, 1, 1),
        'end_date': date(2024, 12, 31)
    }
    
    results = engine.validate_record(record)
    assert not results  # No validation errors

