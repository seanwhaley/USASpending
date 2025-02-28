"""Tests for the field_selector module."""
import pytest
from typing import Dict, Any, List, Set

from usaspending.field_selector import FieldSelector

@pytest.mark.unit
class TestFieldSelector:
    """Test suite for the FieldSelector class."""
    
    @pytest.fixture
    def sample_config(self) -> Dict[str, Any]:
        """Provide sample configuration for testing."""
        return {
            "contracts": {
                "field_selection": {
                    "enabled": True,
                    "strategy": "priority",
                    "essential_fields": ["id", "name", "amount"],
                    "important_fields": ["date", "description"],
                    "optional_fields": []
                }
            }
        }
        
    @pytest.fixture
    def explicit_config(self) -> Dict[str, Any]:
        """Provide configuration with explicit strategy."""
        return {
            "contracts": {
                "field_selection": {
                    "enabled": True,
                    "strategy": "explicit",
                    "essential_fields": ["id", "name"],
                    "important_fields": ["amount"],
                    "optional_fields": ["date"]
                }
            }
        }
    
    @pytest.fixture
    def all_config(self) -> Dict[str, Any]:
        """Provide configuration with 'all' strategy."""
        return {
            "contracts": {
                "field_selection": {
                    "enabled": True,
                    "strategy": "all",
                    "essential_fields": ["id", "name"],
                    "important_fields": ["amount"],
                    "optional_fields": ["date"]
                }
            }
        }
        
    @pytest.fixture
    def disabled_config(self) -> Dict[str, Any]:
        """Provide configuration with disabled field selection."""
        return {
            "contracts": {
                "field_selection": {
                    "enabled": False,
                    "strategy": "priority",
                    "essential_fields": ["id", "name"],
                    "important_fields": ["amount"],
                    "optional_fields": ["date"]
                }
            }
        }
    
    def test_initialization(self, sample_config: Dict[str, Any]) -> None:
        """Test FieldSelector initialization."""
        selector = FieldSelector(sample_config)
        
        assert selector.strategy == "priority"
        assert selector.essential_fields == {"id", "name", "amount"}
        assert selector.important_fields == {"date", "description"}
        assert selector.optional_fields == set()
        
    def test_get_field_priority(self, sample_config: Dict[str, Any]) -> None:
        """Test retrieving field priority levels."""
        selector = FieldSelector(sample_config)
        
        assert selector.get_field_priority("id") == "essential"
        assert selector.get_field_priority("date") == "important"
        assert selector.get_field_priority("other_field") == "optional"
    
    def test_get_selected_fields_priority(self, sample_config: Dict[str, Any]) -> None:
        """Test field selection with priority strategy."""
        selector = FieldSelector(sample_config)
        all_fields = ["id", "name", "amount", "date", "description", "other1", "other2"]
        
        selected = selector.get_selected_fields(all_fields)
        
        # Should include all fields with priority strategy when optional_fields is empty
        assert selected == set(all_fields)
    
    def test_get_selected_fields_explicit(self, explicit_config: Dict[str, Any]) -> None:
        """Test field selection with explicit strategy."""
        selector = FieldSelector(explicit_config)
        all_fields = ["id", "name", "amount", "date", "description", "other1", "other2"]
        
        selected = selector.get_selected_fields(all_fields)
        
        # Should only include explicitly mentioned fields
        assert selected == {"id", "name", "amount", "date"}
        assert "description" not in selected
        assert "other1" not in selected
    
    def test_get_selected_fields_all(self, all_config: Dict[str, Any]) -> None:
        """Test field selection with 'all' strategy."""
        selector = FieldSelector(all_config)
        all_fields = ["id", "name", "amount", "date", "other1"]
        
        selected = selector.get_selected_fields(all_fields)
        
        # Should include all fields
        assert selected == set(all_fields)
    
    def test_get_selected_fields_disabled(self, disabled_config: Dict[str, Any]) -> None:
        """Test field selection when disabled."""
        selector = FieldSelector(disabled_config)
        all_fields = ["id", "name", "amount", "date", "other1"]
        
        selected = selector.get_selected_fields(all_fields)
        
        # Should include all fields when disabled
        assert selected == set(all_fields)
    
    def test_filter_record_priority(self, sample_config: Dict[str, Any]) -> None:
        """Test record filtering with priority strategy."""
        selector = FieldSelector(sample_config)
        record = {
            "id": "123", 
            "name": "Test",
            "amount": 100.0,
            "date": "2024-01-01",
            "description": "Test description",
            "other_field": "value"
        }
        
        filtered = selector.filter_record(record)
        
        # Should keep all fields with priority strategy
        assert filtered == record
    
    def test_filter_record_explicit(self, explicit_config: Dict[str, Any]) -> None:
        """Test record filtering with explicit strategy."""
        selector = FieldSelector(explicit_config)
        record = {
            "id": "123", 
            "name": "Test",
            "amount": 100.0,
            "date": "2024-01-01",
            "description": "Test description",
            "other_field": "value"
        }
        
        filtered = selector.filter_record(record)
        
        # Should only keep explicitly mentioned fields
        assert filtered == {
            "id": "123", 
            "name": "Test",
            "amount": 100.0,
            "date": "2024-01-01"
        }
        assert "description" not in filtered
        assert "other_field" not in filtered
    
    def test_filter_record_disabled(self, disabled_config: Dict[str, Any]) -> None:
        """Test record filtering when disabled."""
        selector = FieldSelector(disabled_config)
        record = {
            "id": "123", 
            "name": "Test",
            "amount": 100.0,
            "date": "2024-01-01",
            "other_field": "value"
        }
        
        filtered = selector.filter_record(record)
        
        # Should keep all fields when disabled
        assert filtered == record