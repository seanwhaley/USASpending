"""Tests for field dependency management system."""
import pytest
from typing import Dict, Any, Tuple, FrozenSet

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

def test_field_dependency_creation(sample_field_config):
    """Test creating field dependency objects."""
    # Create a frozen version of the config to make it hashable
    field_name = sample_field_config["field"]
    dependencies = tuple(sample_field_config["dependencies"])
    validation_type = sample_field_config["validation"]["type"]
    
    dependency = FieldDependency(field_name, dependencies, validation_type)
    
    assert dependency.field_name == "test_field"
    assert "dep1" in dependency.dependencies
    assert "dep2" in dependency.dependencies

def test_field_dependency_creation():
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
    """Test that topological sort raises error on circular dependencies."""
    manager = FieldDependencyManager()
    manager.add_dependency('a', 'b', 'test')
    manager.add_dependency('b', 'c', 'test')
    manager.add_dependency('c', 'a', 'test')
    
    with pytest.raises(ValueError) as excinfo:
        manager.get_validation_order()
    assert "Circular dependency" in str(excinfo.value)


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

class FieldDependency:
    def __init__(self, field_name: str, target_field: str, dependency_type: str, 
                 validation_rule=None):
        self.field_name = field_name
        self.target_field = target_field
        self.dependency_type = dependency_type
        # Convert dict to a frozenset of items to make it hashable
        self.validation_rule = validation_rule if validation_rule is None else dict(validation_rule)
        
    def __eq__(self, other):
        if not isinstance(other, FieldDependency):
            return False
        return (self.field_name == other.field_name and 
                self.target_field == other.target_field and
                self.dependency_type == other.dependency_type)
                
    def __hash__(self):
        # Make hashable by using only immutable attributes
        return hash((self.field_name, self.target_field, self.dependency_type))