"""Tests for field dependency management system."""

import pytest
from typing import Dict, Any
from decimal import Decimal
from datetime import date
from usaspending.validation import ValidationEngine
from usaspending.field_dependencies import FieldDependencyManager, FieldDependency

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
    """Return a sample configuration for testing."""
    return {
        'field_properties': {
            'award_amount': {
                'type': 'numeric',
                'validation': {
                    'dependencies': [
                        {'target_field': 'maximum_amount', 'type': 'comparison', 'validation_rule': {'operator': 'less_than_or_equal'}}
                    ]
                }
            },
            'maximum_amount': {'type': 'numeric'},
            'start_date': {'type': 'date'},
            'end_date': {
                'type': 'date',
                'validation': {
                    'dependencies': [
                        {'target_field': 'start_date', 'type': 'comparison', 'validation_rule': {'operator': 'greater_than'}}
                    ]
                }
            }
        }
    }

def test_field_dependency_creation(sample_field_config):
    """Test creation of field dependency objects."""
    dep = FieldDependency('test_field', 'dep1', 'required')
    assert dep.field_name == "test_field"
    assert dep.target_field == "dep1"
    assert dep.dependency_type == "required"

    # Test multiple dependencies
    dep = FieldDependency('test_field', ('dep1', 'dep2'), 'required')
    assert dep.field_name == "test_field"
    assert dep.target_field == ('dep1', 'dep2')
    assert dep.dependency_type == "required"

def test_field_dependency_manager_operations():
    """Test operations of the FieldDependencyManager."""
    manager = FieldDependencyManager()

    # Add dependencies
    manager.add_dependency('total_price', 'unit_price', 'calculation')
    manager.add_dependency('discount_amount', 'total_price', 'percentage', {'percentage': '10%'})

    # Check dependencies
    deps = manager.get_dependencies('total_price')
    assert len(deps) == 1
    assert deps[0].target_field == 'unit_price'

    discount_deps = manager.get_dependencies('discount_amount')
    assert len(discount_deps) == 1
    assert discount_deps[0].target_field == 'total_price'
    assert discount_deps[0].validation_rule['percentage'] == '10%'

def test_circular_dependency_detection():
    """Test detection of circular dependencies."""
    manager = FieldDependencyManager()
    manager.add_dependency('a', 'b', 'test')
    manager.add_dependency('b', 'c', 'test')
    manager.add_dependency('c', 'a', 'test')

    assert manager.has_circular_dependency('a')
    assert manager.has_circular_dependency('b')
    assert manager.has_circular_dependency('c')

def test_validation_order():
    """Test computation of validation order."""
    manager = FieldDependencyManager()
    manager.add_dependency('total_amount', 'subtotal', 'calculation')
    manager.add_dependency('subtotal', 'unit_price', 'calculation')
    manager.add_dependency('unit_price', 'quantity', 'calculation')

    order = manager.get_validation_order()
    assert order.index('quantity') < order.index('unit_price')
    assert order.index('unit_price') < order.index('subtotal')
    assert order.index('subtotal') < order.index('total_amount')

def test_topological_sort_with_circular_deps():
    """Test topological sort with circular dependencies."""
    manager = FieldDependencyManager()
    manager.add_dependency('a', 'b', 'test')
    manager.add_dependency('b', 'c', 'test')
    manager.add_dependency('c', 'a', 'test')

    with pytest.raises(ValueError):
        manager.get_validation_order()

def test_load_dependencies_from_config(sample_config):
    """Test loading dependencies from configuration."""
    manager = FieldDependencyManager()
    manager.from_config(sample_config)

    award_amount_deps = manager.get_dependencies('award_amount')
    assert any(dep.target_field == 'maximum_amount' for dep in award_amount_deps)

    end_date_deps = manager.get_dependencies('end_date')
    assert any(dep.target_field == 'start_date' for dep in end_date_deps)

def test_dependency_graph_representation():
    """Test representation of dependency graph."""
    manager = FieldDependencyManager()
    manager.add_dependency('a', 'b', 'test')
    manager.add_dependency('b', 'c', 'test')
    manager.add_dependency('c', 'a', 'test')

    graph = manager.get_dependency_graph()
    assert 'a' in graph
    assert 'b' in graph
    assert 'c' in graph
    assert ('b', 'test') in graph['a']
    assert ('c', 'test') in graph['b']
    assert ('a', 'test') in graph['c']

def test_fallback_order_computation(monkeypatch):
    """Test fallback order computation when topological sort fails."""
    manager = FieldDependencyManager()
    manager.add_dependency('a', 'b', 'test')
    manager.add_dependency('b', 'c', 'test')

    def mock_compute_validation_order(*args, **kwargs):
        raise ValueError

    monkeypatch.setattr(manager, '_compute_validation_order', mock_compute_validation_order)

    order = manager.get_validation_order()
    assert set(order) == {'a', 'b', 'c'}

def test_remove_dependency_with_method():
    """Test removing dependency using remove_dependency method."""
    manager = FieldDependencyManager()
    manager.add_dependency('a', 'b', 'test')
    manager.add_dependency('a', 'c', 'test')

    assert len(manager.get_dependencies('a')) == 2

    manager.remove_dependency('a', 'b', 'test')
    assert len(manager.get_dependencies('a')) == 1

def test_update_dependency_validation_rule():
    """Test updating dependency validation rule."""
    manager = FieldDependencyManager()
    manager.add_dependency('total', 'subtotal', 'calculation', {'operation': 'sum'})

    deps = manager.get_dependencies('total')
    assert len(deps) == 1
    assert deps[0].validation_rule['operation'] == 'sum'

def test_multiple_dependency_types():
    """Test handling multiple dependency types for a single field."""
    manager = FieldDependencyManager()
    manager.add_dependency('total', 'subtotal', 'calculation')
    manager.add_dependency('total', 'subtotal', 'validation')

    deps = manager.get_dependencies('total')
    assert len(deps) == 2
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

    order = manager.get_validation_order()
    assert set(order) == {'a', 'b', 'c', 'x', 'y', 'z'}
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

    fiscal_period_deps = manager.get_dependencies('fiscal_period')
    assert any(dep.target_field == 'action_date' for dep in fiscal_period_deps)

    fiscal_year_deps = manager.get_dependencies('fiscal_year')
    assert any(dep.target_field == 'action_date' for dep in fiscal_year_deps)

    date_components_deps = manager.get_dependencies('date_components')
    assert any(dep.target_field == 'publication_date' for dep in date_components_deps)

    other_field_deps = manager.get_dependencies('other_field')
    assert any(dep.target_field == 'base_field' for dep in other_field_deps)

def test_has_circular_dependency_edge_cases():
    """Test edge cases for circular dependency detection."""
    manager = FieldDependencyManager()

    assert not manager.has_circular_dependency('nonexistent_field')

    manager.add_dependency('a', 'b', 'test')
    assert not manager.has_circular_dependency('a')

    dep = FieldDependency('c', 'c', 'test')
    manager.dependencies['c'].add(dep)
    assert manager.has_circular_dependency('c')

    manager.add_dependency('d', 'e', 'test')
    manager.add_dependency('e', 'f', 'test')
    manager.add_dependency('f', 'g', 'test')
    manager.add_dependency('g', 'h', 'test')
    assert not manager.has_circular_dependency('d')

    manager.add_dependency('h', 'd', 'test')
    assert manager.has_circular_dependency('d')

def test_from_config_empty_or_missing():
    """Test handling of empty or missing configurations."""
    manager = FieldDependencyManager()

    manager.from_config({})
    assert not manager.dependencies

    manager.from_config({'field_dependencies': {}})
    assert not manager.dependencies

    manager.from_config({
        'field_dependencies': {
            'field1': [
                {'some_key': 'some_value'}
            ]
        }
    })
    assert not manager.dependencies

    manager.from_config({
        'field_properties': {
            'field1': {
                'validation': {
                    'dependencies': [
                        {'some_key': 'some_value'}
                    ]
                }
            }
        }
    })
    assert not manager.dependencies

def test_field_dependency_validation_rule():
    """Test that validation rules are properly stored in FieldDependency."""
    dep1 = FieldDependency('field1', 'field2', 'test')
    assert dep1.validation_rule is None

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

    order = manager.get_validation_order()
    assert set(order) == {'a', 'b', 'c'}

def test_field_dependencies(sample_config):
    """Test field dependency tracking and validation."""
    engine = ValidationEngine(sample_config)

    record = {
        'award_amount': Decimal('2000.00'),
        'maximum_amount': Decimal('2000.00'),
        'start_date': date(2024, 1, 1),
        'end_date': date(2024, 12, 31)
    }

    entity_stores = {}
    results = engine.validate_record(record, entity_stores)
    assert all(result.valid for result in results)

    record['end_date'] = date(2023, 12, 31)
    results = engine.validate_record(record, entity_stores)
    assert any(not result.valid for result in results)
    assert any(result.field_name == 'end_date' for result in results)

