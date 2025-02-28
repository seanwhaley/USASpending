"""Test recipient entity store functionality."""
import pytest
from pathlib import Path
import json
from typing import Dict, Any
from usaspending.recipient_store import RecipientEntityStore

@pytest.fixture
def recipient_store(tmp_path: Path, sample_config: Dict[str, Any]) -> RecipientEntityStore:
    """Create a test recipient store."""
    return RecipientEntityStore(str(tmp_path / "test"), "recipient", sample_config)

@pytest.fixture
def sample_recipient_data() -> Dict[str, Any]:
    """Provide sample recipient data."""
    return {
        "uei": "TEST123",
        "name": "Test Company",
        "dba_name": "Test Co",
        "address_line1": "123 Test St",
        "city": "Testville",
        "state": "TS",
        "zip": "12345"
    }

def test_recipient_entity_extraction(recipient_store: RecipientEntityStore) -> None:
    """Test extraction of recipient data from row data."""
    row_data = {
        "recipient_uei": "TEST123",
        "recipient_name": "Test Company",
        "woman_owned": "Y",
        "veteran_owned": "1",
        "minority_owned": "YES"
    }
    
    result = recipient_store.extract_entity_data(row_data)
    assert result is not None
    assert result["uei"] == "TEST123"
    assert result["name"] == "Test Company"
    assert "characteristics" in result
    assert result["characteristics"]["woman_owned"] is True
    assert result["characteristics"]["veteran_owned"] is True
    assert result["characteristics"]["minority_owned"] is True

def test_parent_child_relationship(recipient_store: RecipientEntityStore) -> None:
    """Test recipient parent-child relationship handling."""
    parent_data = {
        "uei": "PARENT123",
        "name": "Parent Company"
    }
    child_data = {
        "uei": "CHILD456",
        "name": "Child Company",
        "parent_uei": "PARENT123"
    }
    
    # Add child first to test parent creation
    child_key = recipient_store.add_entity(child_data)
    assert child_key == "CHILD456"
    assert "PARENT123" in recipient_store.cache
    
    # Verify parent was created
    parent = recipient_store.cache["PARENT123"]
    assert parent["uei"] == "PARENT123"
    assert "CHILD456" in parent["subsidiaries"]
    
    # Add parent data to update it
    parent_key = recipient_store.add_entity(parent_data)
    assert parent_key == "PARENT123"
    assert recipient_store.cache[parent_key]["name"] == "Parent Company"
    assert "CHILD456" in recipient_store.cache[parent_key]["subsidiaries"]

def test_circular_reference_prevention(recipient_store: RecipientEntityStore) -> None:
    """Test handling of circular parent-child relationships."""
    # Create circular reference
    entity1 = {
        "uei": "UEI1",
        "name": "Company 1",
        "parent_uei": "UEI2"
    }
    entity2 = {
        "uei": "UEI2",
        "name": "Company 2",
        "parent_uei": "UEI1"
    }
    
    # Add entities
    recipient_store.add_entity(entity1)
    recipient_store.add_entity(entity2)
    
    # Verify only one parent-child relationship was established
    assert len(recipient_store.cache["UEI1"].get("subsidiaries", [])) == 0
    assert "UEI2" in recipient_store.cache
    assert len(recipient_store.cache["UEI2"].get("subsidiaries", [])) == 1

def test_nested_recipient_structure(recipient_store: RecipientEntityStore) -> None:
    """Test creation and saving of nested recipient structure."""
    # Create a three-level hierarchy
    entities = [
        {"uei": "PARENT", "name": "Parent Corp"},
        {"uei": "CHILD1", "name": "Child 1", "parent_uei": "PARENT"},
        {"uei": "CHILD2", "name": "Child 2", "parent_uei": "PARENT"},
        {"uei": "GRANDCHILD1", "name": "Grandchild 1", "parent_uei": "CHILD1"}
    ]
    
    # Add entities in mixed order
    for entity in entities:
        recipient_store.add_entity(entity)
    
    # Save and verify structure
    recipient_store.save()
    
    # Load new store and verify structure
    new_store = RecipientEntityStore(recipient_store.base_path, "recipient", recipient_store.config)
    
    # Verify parent has all children
    parent = new_store.cache["PARENT"]
    assert len(parent["subsidiaries"]) == 2
    
    # Verify child has grandchild
    child1 = new_store.cache["CHILD1"]
    assert len(child1["subsidiaries"]) == 1
    assert "GRANDCHILD1" in child1["subsidiaries"]

def test_business_characteristics(recipient_store: RecipientEntityStore) -> None:
    """Test handling of business characteristics."""
    data = {
        "uei": "TEST123",
        "name": "Test Company",
        "woman_owned": "Y",
        "veteran_owned": "1",
        "minority_owned": "YES",
        "small_business": "N",
        "foreign_owned": "FALSE"
    }
    
    key = recipient_store.add_entity(data)
    assert key == "TEST123"
    
    entity = recipient_store.cache[key]
    assert "characteristics" in entity
    assert entity["characteristics"]["woman_owned"] is True
    assert entity["characteristics"]["veteran_owned"] is True
    assert entity["characteristics"]["minority_owned"] is True
    assert entity["characteristics"]["small_business"] is False
    assert entity["characteristics"]["foreign_owned"] is False