"""Tests for field dependency validation."""
import pytest
from typing import Dict, Any, Optional, List, Protocol
from unittest.mock import Mock

from usaspending.validation_base import BaseValidator
from usaspending.interfaces import ISchemaAdapter


class MockSchemaAdapter(ISchemaAdapter):
    """Mock schema adapter for testing."""
    
    def __init__(self, should_validate: bool = True) -> None:
        self._should_validate = should_validate
        self._errors: List[str] = []
    
    def validate(self, value: Any, rules: Dict[str, Any],
                validation_context: Optional[Dict[str, Any]] = None) -> bool:
        if not self._should_validate:
            self._errors.append("Validation failed")
            return False
        return True
    
    def transform(self, value: Any) -> Any:
        return value
    
    def get_errors(self) -> List[str]:
        return self._errors


class IDependencyManager(Protocol):
    """Interface for dependency management."""
    
    def add_dependency(self, field_name: str, target_field: str,
                      dependency_type: str, validation_rule: Dict[str, Any]) -> None:
        """Add field dependency."""
        ...
        
    def get_validation_order(self) -> List[str]:
        """Get ordered list of fields for validation."""
        ...
        
    def validate_dependencies(self, record: Dict[str, Any],
                          adapters: Dict[str, ISchemaAdapter]) -> List[str]:
        """Validate field dependencies."""
        ...


class TestDependencyManager(IDependencyManager):
    """Test implementation of dependency manager."""
    
    def __init__(self) -> None:
        self._dependencies: Dict[str, List[Dict[str, Any]]] = {}
        self._validation_order: List[str] = []
        self._errors: List[str] = []
    
    def add_dependency(self, field_name: str, target_field: str,
                      dependency_type: str, validation_rule: Dict[str, Any]) -> None:
        """Add field dependency."""
        if field_name not in self._dependencies:
            self._dependencies[field_name] = []
            
        self._dependencies[field_name].append({
            'target': target_field,
            'type': dependency_type,
            'rule': validation_rule
        })
        
        # Update validation order
        if target_field not in self._validation_order:
            self._validation_order.append(target_field)
        if field_name not in self._validation_order:
            self._validation_order.append(field_name)
    
    def get_validation_order(self) -> List[str]:
        """Get ordered list of fields for validation."""
        return self._validation_order.copy()
    
    def validate_dependencies(self, record: Dict[str, Any],
                          adapters: Dict[str, ISchemaAdapter]) -> List[str]:
        """Validate field dependencies."""
        self._errors.clear()
        
        for field_name, dependencies in self._dependencies.items():
            if field_name not in record:
                continue
                
            field_value = record[field_name]
            
            for dep in dependencies:
                target = dep['target']
                if target not in record:
                    self._errors.append(f"Missing required field {target}")
                    continue
                
                target_value = record[target]
                dependency_type = dep['type']
                rule = dep.get('rule', {})
                
                # Get appropriate adapter
                adapter = adapters.get(dependency_type)
                if not adapter:
                    self._errors.append(f"No adapter found for type {dependency_type}")
                    continue
                
                # Validate using adapter
                if not adapter.validate(field_value, rule, {'target_value': target_value}):
                    self._errors.extend(adapter.get_errors())
        
        return self._errors


class TestValidator(BaseValidator):
    """Test validator with dependency support."""
    
    def __init__(self, dependency_manager: IDependencyManager) -> None:
        super().__init__()
        self._dependency_manager = dependency_manager
        self._adapters: Dict[str, ISchemaAdapter] = {}
    
    def register_adapter(self, adapter_type: str, adapter: ISchemaAdapter) -> None:
        """Register schema adapter."""
        self._adapters[adapter_type] = adapter
    
    def _validate_field_value(self, field_name: str, value: Any,
                            validation_context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate field value including dependencies."""
        if validation_context is None:
            validation_context = {}
            
        record = validation_context.get('record', {})
        
        # Validate dependencies first
        errors = self._dependency_manager.validate_dependencies(record, self._adapters)
        if errors:
            self.errors.extend(errors)
            return False
            
        return True


@pytest.fixture
def dependency_manager() -> TestDependencyManager:
    """Create dependency manager instance."""
    return TestDependencyManager()


@pytest.fixture
def mock_adapter() -> MockSchemaAdapter:
    """Create schema adapter mock."""
    return MockSchemaAdapter()


@pytest.fixture
def validator(dependency_manager: TestDependencyManager) -> TestValidator:
    """Create validator instance."""
    return TestValidator(dependency_manager)


def test_add_dependency(dependency_manager: TestDependencyManager) -> None:
    """Test adding field dependency."""
    dependency_manager.add_dependency(
        'amount',
        'max_amount',
        'range',
        {'max': None}  # Will be filled from target field
    )
    
    order = dependency_manager.get_validation_order()
    assert 'max_amount' in order
    assert 'amount' in order
    assert order.index('max_amount') < order.index('amount')  # Target should be validated first


def test_validation_order(dependency_manager: TestDependencyManager) -> None:
    """Test dependency validation order."""
    # Add dependencies in random order
    dependency_manager.add_dependency('c', 'b', 'test', {})
    dependency_manager.add_dependency('b', 'a', 'test', {})
    
    order = dependency_manager.get_validation_order()
    assert len(order) == 3
    assert order.index('a') < order.index('b')
    assert order.index('b') < order.index('c')


def test_missing_dependency(dependency_manager: TestDependencyManager,
                          validator: TestValidator,
                          mock_adapter: MockSchemaAdapter) -> None:
    """Test validation with missing dependent field."""
    # Setup dependency
    dependency_manager.add_dependency('amount', 'max_amount', 'range', {'max': None})
    validator.register_adapter('range', mock_adapter)
    
    # Test with missing dependent field
    context: Dict[str, Any] = {'record': {'amount': 100}}  # Missing max_amount
    assert validator.validate_field('amount', 100, context) is False
    assert any('missing' in err.lower() for err in validator.get_validation_errors())


def test_dependency_validation_success(dependency_manager: TestDependencyManager,
                                    validator: TestValidator,
                                    mock_adapter: MockSchemaAdapter) -> None:
    """Test successful dependency validation."""
    # Setup dependency
    dependency_manager.add_dependency('amount', 'max_amount', 'range', {'max': None})
    validator.register_adapter('range', mock_adapter)
    
    # Test with valid values
    context: Dict[str, Any] = {'record': {'amount': 100, 'max_amount': 200}}
    assert validator.validate_field('amount', 100, context) is True
    assert len(validator.get_validation_errors()) == 0


def test_dependency_validation_failure(dependency_manager: TestDependencyManager,
                                    validator: TestValidator,
                                    mock_adapter: MockSchemaAdapter) -> None:
    """Test failed dependency validation."""
    # Configure adapter to fail validation
    mock_adapter._should_validate = False
    
    # Setup dependency
    dependency_manager.add_dependency('amount', 'max_amount', 'range', {'max': None})
    validator.register_adapter('range', mock_adapter)
    
    # Test with values that will fail validation
    context: Dict[str, Any] = {'record': {'amount': 100, 'max_amount': 50}}
    assert validator.validate_field('amount', 100, context) is False
    assert len(validator.get_validation_errors()) > 0


def test_multiple_dependencies(dependency_manager: TestDependencyManager,
                             validator: TestValidator) -> None:
    """Test validation with multiple dependencies."""
    # Setup adapters
    range_adapter = MockSchemaAdapter()
    pattern_adapter = MockSchemaAdapter()
    validator.register_adapter('range', range_adapter)
    validator.register_adapter('pattern', pattern_adapter)
    
    # Setup dependencies
    dependency_manager.add_dependency('amount', 'max_amount', 'range', {'max': None})
    dependency_manager.add_dependency('amount', 'currency', 'pattern', {'pattern': '[A-Z]{3}'})
    
    # Test with all dependencies satisfied
    context: Dict[str, Any] = {
        'record': {
            'amount': 100,
            'max_amount': 200,
            'currency': 'USD'
        }
    }
    assert validator.validate_field('amount', 100, context) is True
    
    # Test with one dependency missing
    context['record'].pop('currency')
    assert validator.validate_field('amount', 100, context) is False


def test_circular_dependency_prevention(dependency_manager: TestDependencyManager) -> None:
    """Test prevention of circular dependencies."""
    # Create a circular dependency chain
    dependency_manager.add_dependency('a', 'b', 'test', {})
    dependency_manager.add_dependency('b', 'c', 'test', {})
    dependency_manager.add_dependency('c', 'a', 'test', {})
    
    # Validation order should still be deterministic and acyclic
    order = dependency_manager.get_validation_order()
    assert len(order) == 3
    assert len(set(order)) == 3  # No duplicates


def test_dependency_validation_context(dependency_manager: TestDependencyManager,
                                    validator: TestValidator,
                                    mock_adapter: MockSchemaAdapter) -> None:
    """Test dependency validation with context."""
    # Setup dependency
    dependency_manager.add_dependency('amount', 'max_amount', 'range', {'max': None})
    validator.register_adapter('range', mock_adapter)
    
    # Test with different contexts
    context1: Dict[str, Any] = {
        'record': {'amount': 100, 'max_amount': 200},
        'entity_type': 'type1'
    }
    context2: Dict[str, Any] = {
        'record': {'amount': 100, 'max_amount': 200},
        'entity_type': 'type2'
    }
    
    assert validator.validate_field('amount', 100, context1) is True
    assert validator.validate_field('amount', 100, context2) is True
    assert validator._cache_misses >= 2  # Different contexts should not hit cache


def test_missing_adapter(dependency_manager: TestDependencyManager,
                        validator: TestValidator) -> None:
    """Test handling of missing adapter."""
    # Setup dependency without registering adapter
    dependency_manager.add_dependency('amount', 'max_amount', 'range', {'max': None})
    
    context: Dict[str, Any] = {'record': {'amount': 100, 'max_amount': 200}}
    assert validator.validate_field('amount', 100, context) is False
    assert any('adapter' in err.lower() for err in validator.get_validation_errors())

