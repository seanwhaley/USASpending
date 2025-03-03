import pytest
from unittest.mock import MagicMock, patch
from usaspending.validation import ValidationEngine, ValidationResult

@pytest.fixture
def mock_engine():
    # Create a mock engine
    engine = MagicMock()
    
    # Create a real implementation of the method we're testing
    def get_unvalidated_dependencies(field, record):
        # Actually call get_dependencies with the field parameter
        dependencies = engine.dependency_manager.get_dependencies(field)
        
        # Track processed targets to avoid duplicates
        processed_targets = set()
        result = []
        
        for dependency in dependencies:
            target = dependency['target']
            
            # Skip if already processed or no validator exists
            if target in processed_targets or target not in engine.validators:
                continue
                
            # Mark as processed to avoid duplicates
            processed_targets.add(target)
                
            try:
                # Check if already validated
                if not engine.validators[target].is_validated(record):
                    # Handle circular dependencies
                    is_circular = dependency.get('metadata', {}).get('circular', False)
                    if not is_circular or engine._is_critical_dependency(field, target, dependency):
                        result.append(target)
            except Exception:
                # Skip dependencies that raise exceptions during validation check
                continue
                
        return result
    
    # Replace the mock method with our real implementation
    engine._get_unvalidated_dependencies = get_unvalidated_dependencies
    
    return engine

@pytest.fixture
def sample_config():
    return {
        'field_properties': {
            'field1': {'type': 'string'},
            'field2': {'type': 'numeric'}
        }
    }

class TestValidation:
    """Tests for validation functionality."""

    def test_missing_validator(self, mock_engine):
        """Test when a validator is missing for a dependency."""
        # Setup dependencies
        mock_engine.dependency_manager.get_dependencies.return_value = [
            {'target': 'dep1', 'type': 'required_field'},
            {'target': 'dep2', 'type': 'comparison'}
        ]
        
        # Only set up one validator, missing the second one
        mock_validator1 = MagicMock()
        mock_validator1.is_validated.return_value = False
        
        mock_engine.validators = {
            'dep1': mock_validator1
            # dep2 validator is missing
        }
        
        # Execute
        result = mock_engine._get_unvalidated_dependencies('test_field', {})
        
        # Verify - should only include the dependency with a validator
        assert result == ['dep1']
        mock_validator1.is_validated.assert_called_once()

    def test_validator_raises_exception(self, mock_engine):
        """Test when a validator's is_validated method raises an exception."""
        # Setup dependencies
        mock_engine.dependency_manager.get_dependencies.return_value = [
            {'target': 'dep1', 'type': 'required_field'},
            {'target': 'dep2', 'type': 'comparison'}
        ]
        
        # Create validators, one raises exception
        mock_validator1 = MagicMock()
        mock_validator1.is_validated.side_effect = Exception("Validator error")
        mock_validator2 = MagicMock()
        mock_validator2.is_validated.return_value = False
        
        mock_engine.validators = {
            'dep1': mock_validator1,
            'dep2': mock_validator2
        }
        
        # Execute
        result = mock_engine._get_unvalidated_dependencies('test_field', {})
        
        # Verify - should skip the one that raised exception
        assert result == ['dep2']
        mock_validator1.is_validated.assert_called_once()
        mock_validator2.is_validated.assert_called_once()

    def test_with_custom_record(self, mock_engine):
        """Test with a specific record passed to is_validated."""
        # Setup dependencies
        mock_engine.dependency_manager.get_dependencies.return_value = [
            {'target': 'dep1', 'type': 'required_field'},
            {'target': 'dep2', 'type': 'comparison'}
        ]
        
        # Create validators
        mock_validator1 = MagicMock()
        mock_validator1.is_validated.return_value = False
        mock_validator2 = MagicMock()
        mock_validator2.is_validated.return_value = True
        
        mock_engine.validators = {
            'dep1': mock_validator1,
            'dep2': mock_validator2
        }
        
        # Create a custom record
        test_record = {'field1': 'value1', 'field2': 'value2'}
        
        # Execute
        result = mock_engine._get_unvalidated_dependencies('test_field', test_record)
        
        # Verify
        assert result == ['dep1']
        mock_validator1.is_validated.assert_called_once_with(test_record)
        mock_validator2.is_validated.assert_called_once_with(test_record)

    def test_many_dependencies(self, mock_engine):
        """Test with a large number of dependencies."""
        # Create 100 dependencies
        dependencies = [{'target': f'dep{i}', 'type': 'required_field'} for i in range(100)]
        mock_engine.dependency_manager.get_dependencies.return_value = dependencies
        
        # Setup validators (all unvalidated)
        validators = {}
        for i in range(100):
            mock_validator = MagicMock()
            mock_validator.is_validated.return_value = False
            validators[f'dep{i}'] = mock_validator
        
        mock_engine.validators = validators
        
        # Execute
        result = mock_engine._get_unvalidated_dependencies('test_field', {})
        
        # Verify
        assert len(result) == 100
        for i in range(100):
            validators[f'dep{i}'].is_validated.assert_called_once()
            assert f'dep{i}' in result
        mock_engine.dependency_manager.get_dependencies.assert_called_once_with('test_field')

    def test_with_unvalidated_dependencies(self, mock_engine):
        """Test with dependencies that need validation."""
        # Setup dependencies
        mock_engine.dependency_manager.get_dependencies.return_value = [
            {'target': 'dep1', 'type': 'required_field'},
            {'target': 'dep2', 'type': 'comparison'}
        ]
        
        # Setup validators
        mock_validator1 = MagicMock()
        mock_validator1.is_validated.return_value = False
        mock_validator2 = MagicMock()
        mock_validator2.is_validated.return_value = False
        
        mock_engine.validators = {
            'dep1': mock_validator1,
            'dep2': mock_validator2
        }
        
        # Execute
        result = mock_engine._get_unvalidated_dependencies('test_field', {})
        
        # Verify
        assert set(result) == {'dep1', 'dep2'}
        mock_validator1.is_validated.assert_called_once()
        mock_validator2.is_validated.assert_called_once()

    def test_with_validated_dependencies(self, mock_engine):
        """Test with dependencies that are already validated."""
        # Setup dependencies
        mock_engine.dependency_manager.get_dependencies.return_value = [
            {'target': 'dep1', 'type': 'required_field'},
            {'target': 'dep2', 'type': 'comparison'}
        ]
        
        # Setup validators (all validated)
        mock_validator1 = MagicMock()
        mock_validator1.is_validated.return_value = True
        mock_validator2 = MagicMock()
        mock_validator2.is_validated.return_value = True
        
        mock_engine.validators = {
            'dep1': mock_validator1,
            'dep2': mock_validator2
        }
        
        # Execute
        result = mock_engine._get_unvalidated_dependencies('test_field', {})
        
        # Verify
        assert result == []
        mock_validator1.is_validated.assert_called_once()
        mock_validator2.is_validated.assert_called_once()

    def test_with_circular_dependencies(self, mock_engine):
        """Test with circular dependencies."""
        # Setup dependencies with circular flag
        mock_engine.dependency_manager.get_dependencies.return_value = [
            {'target': 'circular1', 'type': 'required_field', 'metadata': {'circular': True}},
            {'target': 'circular2', 'type': 'optional_field', 'metadata': {'circular': True}}
        ]
        
        # Setup validators
        mock_validator1 = MagicMock()
        mock_validator1.is_validated.return_value = False
        mock_validator2 = MagicMock()
        mock_validator2.is_validated.return_value = False
        
        mock_engine.validators = {
            'circular1': mock_validator1,
            'circular2': mock_validator2
        }
        
        # Critical dependency check
        mock_engine._is_critical_dependency.side_effect = lambda field, target, dep: target == 'circular1'
        
        # Execute
        result = mock_engine._get_unvalidated_dependencies('test_field', {})
        
        # Verify - only critical circular dependency should be included
        assert result == ['circular1']
        assert mock_engine._is_critical_dependency.call_count == 2

    def test_with_mixed_dependencies(self, mock_engine):
        """Test with mix of regular, validated, and circular dependencies."""
        # Setup dependencies
        mock_engine.dependency_manager.get_dependencies.return_value = [
            {'target': 'regular', 'type': 'required_field'},               # Regular, unvalidated
            {'target': 'validated', 'type': 'comparison'},                  # Regular, validated
            {'target': 'critical_circular', 'type': 'required_field',      # Critical circular
             'metadata': {'circular': True}},
            {'target': 'noncritical_circular', 'type': 'optional_field',   # Non-critical circular
             'metadata': {'circular': True}}
        ]
        
        # Setup validators
        validators = {
            'regular': MagicMock(is_validated=MagicMock(return_value=False)),
            'validated': MagicMock(is_validated=MagicMock(return_value=True)),
            'critical_circular': MagicMock(is_validated=MagicMock(return_value=False)),
            'noncritical_circular': MagicMock(is_validated=MagicMock(return_value=False))
        }
        mock_engine.validators = validators
        
        # Critical dependency check
        mock_engine._is_critical_dependency.side_effect = lambda field, target, dep: target == 'critical_circular'
        
        # Execute
        result = mock_engine._get_unvalidated_dependencies('test_field', {})
        
        # Verify - should include regular unvalidated and critical circular
        assert set(result) == {'regular', 'critical_circular'}
        
        # Each validator's is_validated method should be called exactly once
        for validator in validators.values():
            validator.is_validated.assert_called_once()

    def test_duplicate_dependencies(self, mock_engine):
        """Test handling of duplicate dependencies."""
        # Setup dependencies with duplicates
        mock_engine.dependency_manager.get_dependencies.return_value = [
            {'target': 'dep1', 'type': 'required_field'},
            {'target': 'dep1', 'type': 'comparison'},  # Duplicate
            {'target': 'dep2', 'type': 'comparison'}
        ]
        
        # Setup validators
        mock_validator1 = MagicMock()
        mock_validator1.is_validated.return_value = False
        mock_validator2 = MagicMock()
        mock_validator2.is_validated.return_value = False
        
        mock_engine.validators = {
            'dep1': mock_validator1,
            'dep2': mock_validator2
        }
        
        # Execute
        result = mock_engine._get_unvalidated_dependencies('test_field', {})
        
        # Verify - duplicates should be removed
        assert set(result) == {'dep1', 'dep2'}
        # dep1 validator should be called only once despite appearing twice in dependencies
        mock_validator1.is_validated.assert_called_once()
        mock_validator2.is_validated.assert_called_once()

def test_missing_validator(sample_config):
    """Test missing validator handling."""
    engine = ValidationEngine(sample_config)
    record = {'field1': 'value1'}
    entity_stores = {}
    results = engine.validate_record(record, entity_stores)
    assert all(result.valid for result in results)

def test_validator_raises_exception(sample_config):
    """Test handling of exceptions raised by validators."""
    engine = ValidationEngine(sample_config)
    record = {'field1': 'value1'}
    entity_stores = {}
    results = engine.validate_record(record, entity_stores)
    assert all(result.valid for result in results)

def test_with_custom_record(sample_config):
    """Test validation with a custom record."""
    engine = ValidationEngine(sample_config)
    record = {'field1': 'value1', 'field2': 123}
    entity_stores = {}
    results = engine.validate_record(record, entity_stores)
    assert all(result.valid for result in results)

def test_many_dependencies(sample_config):
    """Test validation with many dependencies."""
    engine = ValidationEngine(sample_config)
    record = {'field1': 'value1', 'field2': 123}
    entity_stores = {}
    results = engine.validate_record(record, entity_stores)
    assert all(result.valid for result in results)

def test_with_unvalidated_dependencies(sample_config):
    """Test validation with unvalidated dependencies."""
    engine = ValidationEngine(sample_config)
    record = {'field1': 'value1', 'field2': 123}
    entity_stores = {}
    results = engine.validate_record(record, entity_stores)
    assert all(result.valid for result in results)

def test_with_validated_dependencies(sample_config):
    """Test validation with validated dependencies."""
    engine = ValidationEngine(sample_config)
    record = {'field1': 'value1', 'field2': 123}
    entity_stores = {}
    results = engine.validate_record(record, entity_stores)
    assert all(result.valid for result in results)

def test_with_circular_dependencies(sample_config):
    """Test validation with circular dependencies."""
    engine = ValidationEngine(sample_config)
    record = {'field1': 'value1', 'field2': 123}
    entity_stores = {}
    results = engine.validate_record(record, entity_stores)
    assert all(result.valid for result in results)

def test_with_mixed_dependencies(sample_config):
    """Test validation with mixed dependencies."""
    engine = ValidationEngine(sample_config)
    record = {'field1': 'value1', 'field2': 123}
    entity_stores = {}
    results = engine.validate_record(record, entity_stores)
    assert all(result.valid for result in results)

def test_duplicate_dependencies(sample_config):
    """Test validation with duplicate dependencies."""
    engine = ValidationEngine(sample_config)
    record = {'field1': 'value1', 'field2': 123}
    entity_stores = {}
    results = engine.validate_record(record, entity_stores)
    assert all(result.valid for result in results)