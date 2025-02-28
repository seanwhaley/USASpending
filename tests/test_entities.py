"""Test entity processing functionality."""
import pytest
from pathlib import Path
import json
from typing import Any, Dict, Callable, Set, List, Tuple, Optional, TypeVar, cast
from queue import Queue
import threading
import errno

# Update imports to use src module
from src.usaspending.entity_store import EntityStore
from src.usaspending.types import EntityStats

# Type aliases for improved readability
QueueResult = Tuple[str, int, Optional[str]]  # For worker results
JsonDict = Dict[str, Any]

@pytest.fixture
def entity_store(tmp_path: Path, sample_config: JsonDict) -> EntityStore:
    """Create a test entity store."""
    return EntityStore(str(tmp_path / "test"), "recipient", sample_config)

@pytest.fixture
def sample_recipient_data() -> Dict[str, Any]:
    """Provide sample recipient data for testing."""
    return {
        "uei": "ABC123DEF456",
        "name": "Test Company",
        "address": "123 Test St",
        "city": "Testville",
        "state": "TS",
        "zip": "12345"
    }

@pytest.fixture
def sample_agency_data() -> Dict[str, Any]:
    """Provide sample hierarchical agency data for testing."""
    return {
        'department': {
            'key': 'DEPT_001',
            'data': {
                'agency_code': '001',
                'agency_name': 'Test Department',
                'unique_id': 'DEPT_001'
            }
        },
        'agency': {
            'key': 'AGCY_001_01',
            'data': {
                'agency_code': '001',
                'subagency_code': '01',
                'agency_name': 'Test Agency',
                'unique_id': 'AGCY_001_01'
            }
        },
        'office': {
            'key': 'OFFC_001_01_001',
            'data': {
                'agency_code': '001',
                'subagency_code': '01',
                'office_code': '001',
                'office_name': 'Test Office',
                'unique_id': 'OFFC_001_01_001'
            }
        }
    }

@pytest.fixture
def sample_config() -> Dict[str, Any]:
    """Provide sample configuration for testing."""
    return {
        "global": {
            "encoding": "utf-8"
        },
        "contracts": {
            "output": {
                "indent": 2
            },
            "type_conversion": {
                "boolean_true_values": ["Y", "YES", "TRUE", "1"]
            },
            "entity_separation": {
                "entities": {
                    "recipient": {
                        "field_mappings": {
                            "recipient_name": "name",
                            "recipient_address": "address"
                        },
                        "business_characteristics": {
                            "woman_owned": "is_woman_owned",
                            "veteran_owned": "is_veteran_owned"
                        }
                    },
                    "agency": {
                        "levels": {
                            "department": {
                                "field_mappings": {
                                    "agency_name": "name",
                                    "agency_code": "code"
                                },
                                "key_fields": ["code"]
                            },
                            "agency": {
                                "field_mappings": {
                                    "subagency_name": "name",
                                    "subagency_code": "code"
                                },
                                "key_fields": ["code"]
                            },
                            "office": {
                                "field_mappings": {
                                    "office_name": "name",
                                    "office_code": "code"
                                },
                                "key_fields": ["unique_id"]
                            }
                        },
                        "relationships": {
                            "hierarchical": [
                                {
                                    "from_level": "department",
                                    "to_level": "agency",
                                    "type": "supervises",
                                    "inverse": "belongs_to"
                                },
                                {
                                    "from_level": "agency",
                                    "to_level": "office",
                                    "type": "supervises",
                                    "inverse": "belongs_to"
                                }
                            ]
                        }
                    }
                }
            }
        }
    }

@pytest.fixture
def sample_agency_row_data() -> Dict[str, Any]:
    """Provide sample row data for agency entity extraction."""
    return {
        "awarding_agency_code": "001",
        "awarding_subagency_code": "01",
        "awarding_office_code": "001",
        "awarding_agency_name": "Test Department",
        "awarding_subagency_name": "Test Agency",
        "awarding_office_name": "Test Office",
        "funding_agency_code": "002",
        "funding_subagency_code": "02",
        "funding_office_code": "002"
    }

def test_entity_store_initialization(entity_store: EntityStore) -> None:
    """Test that EntityStore initializes correctly."""
    assert entity_store.entity_type == "recipient"
    assert isinstance(entity_store.stats, EntityStats)
    assert entity_store.cache == {}
    assert entity_store.relationships == {}

def test_add_entity(entity_store: EntityStore, sample_recipient_data: Dict[str, Any]) -> None:
    """Test adding an entity to the store."""
    key = entity_store.add_entity(sample_recipient_data)
    assert key == sample_recipient_data["uei"]
    assert entity_store.stats.total == 1
    assert entity_store.stats.unique == 1
    assert key in entity_store.cache

def test_save_and_load(entity_store: EntityStore, sample_recipient_data: Dict[str, Any]) -> None:
    """Test saving and loading entities."""
    # Add and save entity
    key = entity_store.add_entity(sample_recipient_data)
    entity_store.save()
    
    # Create new store and verify loaded data
    new_store = EntityStore(entity_store.base_path, "recipient", entity_store.config)
    assert key in new_store.cache
    assert new_store.cache[key] == sample_recipient_data
    assert new_store.stats.unique == 1

def test_duplicate_entity(entity_store: EntityStore, sample_recipient_data: Dict[str, Any]) -> None:
    """Test adding the same entity twice."""
    key1 = entity_store.add_entity(sample_recipient_data)
    key2 = entity_store.add_entity(sample_recipient_data)
    
    assert key1 == key2
    assert entity_store.stats.total == 2  # Total references increases
    assert entity_store.stats.unique == 1  # Unique entities stays the same

def test_relationship_handling(entity_store: EntityStore) -> None:
    """Test adding and retrieving relationships."""
    entity_store.add_relationship("A", "parent_of", "B")
    entity_store.add_relationship("A", "parent_of", "C")
    
    assert "parent_of" in entity_store.relationships
    assert isinstance(entity_store.relationships["parent_of"], set)
    assert "A:B" in entity_store.relationships["parent_of"]
    assert "A:C" in entity_store.relationships["parent_of"]
    assert entity_store.stats.relationships["parent_of"] == 2

def test_invalid_entity_data(entity_store: EntityStore) -> None:
    """Test handling of invalid entity data."""
    key = entity_store.add_entity(None)
    assert key is None
    assert entity_store.stats.skipped["invalid_data"] == 1

def test_cleanup_temp_files(entity_store: EntityStore, tmp_path: Path) -> None:
    """Test cleanup of temporary files."""
    # Create some temp files
    temp_files = [
        entity_store.temp_file_path,
        f"{entity_store.file_path}.rel1.tmp",
        f"{entity_store.file_path}.rel2.tmp"
    ]
    for file in temp_files:
        Path(file).touch()
    
    entity_store._cleanup_temp_files()
    
    # Verify files are removed
    for file in temp_files:
        assert not Path(file).exists()

@pytest.mark.parametrize("missing_field", ["base_path", "entity_type"])
def test_entity_store_invalid_init(tmp_path: Path, sample_config: Dict[str, Any], missing_field: str) -> None:
    """Test EntityStore initialization with invalid parameters."""
    kwargs = {
        "base_path": str(tmp_path / "test"),
        "entity_type": "recipient",
        "config": sample_config
    }
    kwargs[missing_field] = ""  # Empty string should raise error
    
    with pytest.raises(ValueError, match=f"{missing_field} must be a non-empty string"):
        EntityStore(**kwargs)

def test_hierarchical_relationships(tmp_path: Path, sample_config: Dict[str, Any], sample_agency_data: Dict[str, Any]) -> None:
    """Test handling of hierarchical agency relationships."""
    store = EntityStore(str(tmp_path / "test"), "agency", sample_config)
    
    # Add hierarchical entity
    result = store.add_entity(sample_agency_data)
    
    assert isinstance(result, dict)
    assert set(result.keys()) == {"department", "agency", "office"}
    
    # Verify relationships were created
    assert "supervises" in store.relationships
    assert "belongs_to" in store.relationships
    
    dept_key = sample_agency_data["department"]["key"]
    agency_key = sample_agency_data["agency"]["key"]
    
    # Check department supervises agency
    assert agency_key in store.relationships["supervises"][dept_key]
    # Check agency belongs to department
    assert dept_key in store.relationships["belongs_to"][agency_key]

def test_recipient_parent_child(entity_store: EntityStore) -> None:
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
    child_key = entity_store.add_entity(child_data)
    assert child_key == "CHILD456"
    assert "PARENT123" in entity_store.cache
    
    # Verify parent was created
    parent = entity_store.cache["PARENT123"]
    assert parent["uei"] == "PARENT123"
    assert "CHILD456" in parent["subsidiaries"]
    
    # Add parent data to update it
    parent_key = entity_store.add_entity(parent_data)
    assert parent_key == "PARENT123"
    assert entity_store.cache[parent_key]["name"] == "Parent Company"
    assert "CHILD456" in entity_store.cache[parent_key]["subsidiaries"]

def test_entity_extraction_error_handling(entity_store: EntityStore) -> None:
    """Test error handling in entity data extraction."""
    # Test with invalid row data type
    result = entity_store.extract_entity_data([])  # Pass list instead of dict
    assert result is None
    
    # Test with missing required fields
    result = entity_store.extract_entity_data({"some_field": "value"})
    assert result is None
    
    # Test with invalid field values
    result = entity_store.extract_entity_data({"uei": ""})  # Empty UEI
    assert result is None

def test_relationship_validation(entity_store: EntityStore) -> None:
    """Test relationship validation and error handling."""
    # Test with invalid keys
    entity_store.add_relationship("", "parent_of", "B")
    assert "parent_of" not in entity_store.relationships
    
    # Test with invalid relationship type
    entity_store.add_relationship("A", "", "B")
    assert entity_store.relationships == {}
    
    # Test with valid data
    entity_store.add_relationship("A", "parent_of", "B")
    assert "parent_of" in entity_store.relationships
    assert "A" in entity_store.relationships["parent_of"]

def test_save_with_large_dataset(entity_store: EntityStore, tmp_path: Path) -> None:
    """Test saving functionality with a larger dataset."""
    # Add multiple entities and relationships
    for i in range(100):
        entity_data = {
            "uei": f"UEI{i:03d}",
            "name": f"Company {i}"
        }
        entity_store.add_entity(entity_data)
        
        if i > 0:
            # Create some relationships
            entity_store.add_relationship(f"UEI{i:03d}", "partner_of", f"UEI{i-1:03d}")
    
    # Save and verify
    entity_store.save()
    
    # Load in new store and verify
    new_store = EntityStore(entity_store.base_path, "recipient", entity_store.config)
    assert len(new_store.cache) == 100
    assert "partner_of" in new_store.relationships
    assert len(new_store.relationships["partner_of"]) == 99  # One less than entities

def test_batch_relationship_processing(entity_store: EntityStore, tmp_path: Path) -> None:
    """Test batch processing of relationships during save."""
    # Create a large number of relationships
    for i in range(2000):  # More than the batch size
        entity_store.add_relationship(
            f"FROM_{i}", 
            "related_to", 
            f"TO_{i}"
        )
    
    # Save and verify
    entity_store.save()
    
    # Check temporary files were created and cleaned up
    temp_file = f"{entity_store.file_path}.related_to.tmp"
    assert not Path(temp_file).exists()
    
    # Load and verify relationships were saved correctly
    new_store = EntityStore(entity_store.base_path, entity_store.entity_type, entity_store.config)
    assert "related_to" in new_store.relationships
    assert len(new_store.relationships["related_to"]) == 2000

def test_error_recovery_during_save(entity_store: EntityStore, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test error recovery during save operation."""
    # Add some test data
    entity_store.add_entity({"uei": "TEST123", "name": "Test Entity"})
    
    # Simulate an error during write
    def mock_dump(*args: Any, **kwargs: Any) -> None:
        raise IOError("Simulated write error")
    
    monkeypatch.setattr(json, "dump", mock_dump)
    
    # Attempt save and verify error handling
    with pytest.raises(Exception):
        entity_store.save()
    
    # Verify temp files were cleaned up
    assert not Path(entity_store.temp_file_path).exists()
    for rel_type in entity_store.relationships:
        temp_file = f"{entity_store.file_path}.{rel_type}.tmp"
        assert not Path(temp_file).exists()

def test_business_characteristics(entity_store: EntityStore) -> None:
    """Test handling of business characteristics for recipients."""
    data = {
        "uei": "TEST123",
        "name": "Test Company",
        "woman_owned": "Y",
        "veteran_owned": "1",
        "minority_owned": "YES"
    }
    
    key = entity_store.add_entity(data)
    assert key == "TEST123"
    
    entity = entity_store.cache[key]
    assert "characteristics" in entity
    assert entity["characteristics"]["woman_owned"] is True
    assert entity["characteristics"]["veteran_owned"] is True

def test_metadata_in_saved_file(entity_store: EntityStore, sample_recipient_data: Dict[str, Any]) -> None:
    """Test that metadata is correctly included in saved files."""
    # Add some test data
    entity_store.add_entity(sample_recipient_data)
    entity_store.save()
    
    # Read the saved file directly
    with open(entity_store.file_path, 'r', encoding='utf-8') as f:
        saved_data = json.load(f)
    
    # Verify metadata structure
    assert "metadata" in saved_data
    metadata = saved_data["metadata"]
    assert metadata["entity_type"] == "recipient"
    assert metadata["total_references"] == 1
    assert metadata["unique_entities"] == 1
    assert "generated_date" in metadata
    assert "skipped_entities" in metadata
    assert "relationship_counts" in metadata

def test_concurrent_modification_safety(tmp_path: Path, sample_config: Dict[str, Any]) -> None:
    """Test that file operations are atomic and safe for concurrent access."""
    store1 = EntityStore(str(tmp_path / "test"), "recipient", sample_config)
    store2 = EntityStore(str(tmp_path / "test"), "recipient", sample_config)
    
    # Add data to both stores
    store1.add_entity({"uei": "TEST1", "name": "Test 1"})
    store2.add_entity({"uei": "TEST2", "name": "Test 2"})
    
    # Save both (simulating concurrent access)
    store1.save()
    store2.save()
    
    # Load in new store and verify data integrity
    final_store = EntityStore(str(tmp_path / "test"), "recipient", sample_config)
    assert "TEST1" in final_store.cache or "TEST2" in final_store.cache
    assert len(final_store.cache) == 1  # Only one should have succeeded

def test_agency_data_extraction(tmp_path: Path, sample_config: Dict[str, Any]) -> None:
    """Test extraction of agency data from row data."""
    store = EntityStore(str(tmp_path / "test"), "agency", sample_config)
    row_data = {
        "awarding_agency_code": "001",
        "awarding_agency_name": "Test Department",
        "awarding_subagency_code": "01",
        "awarding_subagency_name": "Test Agency"
    }
    
    entity_data = store.extract_entity_data(row_data)
    assert entity_data is not None
    assert "department" in entity_data
    assert "agency" in entity_data
    assert entity_data["department"]["data"]["code"] == "001"
    assert entity_data["agency"]["data"]["code"] == "01"

def test_agency_funding_fallback(tmp_path: Path, sample_config: Dict[str, Any], sample_agency_row_data: Dict[str, Any]) -> None:
    """Test fallback to funding fields when awarding fields are missing."""
    store = EntityStore(str(tmp_path / "test"), "agency", sample_config)
    
    # Remove awarding fields
    test_data = sample_agency_row_data.copy()
    for key in list(test_data.keys()):
        if key.startswith("awarding_"):
            del test_data[key]
    
    entity_data = store.extract_entity_data(test_data)
    assert entity_data is not None
    assert entity_data["department"]["data"]["code"] == "002"
    assert entity_data["agency"]["data"]["code"] == "02"

def test_encoding_handling(tmp_path: Path, sample_config: Dict[str, Any]) -> None:
    """Test handling of different file encodings."""
    # Create store with UTF-8 encoding
    store_utf8 = EntityStore(str(tmp_path / "test_utf8"), "recipient", {
        **sample_config,
        "global": {"encoding": "utf-8"}
    })
    
    # Add entity with non-ASCII characters
    data_utf8 = {
        "uei": "TEST123",
        "name": "Test Company 株式会社"
    }
    store_utf8.add_entity(data_utf8)
    store_utf8.save()
    
    # Read back and verify
    new_store = EntityStore(str(tmp_path / "test_utf8"), "recipient", {
        **sample_config,
        "global": {"encoding": "utf-8"}
    })
    assert new_store.cache["TEST123"]["name"] == "Test Company 株式会社"

def test_office_unique_id_handling(tmp_path: Path, sample_config: Dict[str, Any]) -> None:
    """Test handling of office entities with unique IDs."""
    store = EntityStore(str(tmp_path / "test"), "agency", sample_config)
    
    office_data = {
        "office": {
            "data": {
                "unique_id": "OFF_001",
                "name": "Test Office",
                "code": "001"
            }
        }
    }
    
    result = store.add_entity(office_data)
    assert result is not None
    assert "office" in result
    assert result["office"] == "OFF_001"

def test_invalid_entity_type(tmp_path: Path, sample_config: Dict[str, Any]) -> None:
    """Test handling of invalid entity types."""
    store = EntityStore(str(tmp_path / "test"), "invalid_type", sample_config)
    
    # Should still initialize but with empty entity config
    assert store.entity_config == {}
    
    # Adding entity should handle gracefully
    result = store.add_entity({"some": "data"})
    assert result is None

def test_relationship_cycles(entity_store: EntityStore) -> None:
    """Test handling of cyclic relationships."""
    # Create a cycle A -> B -> C -> A
    for pair in [("A", "B"), ("B", "C"), ("C", "A")]:
        entity_store.add_relationship(pair[0], "related_to", pair[1])
    
    # Verify all relationships were added
    assert len(entity_store.relationships["related_to"]) == 3
    assert "A" in entity_store.relationships["related_to"]
    assert "B" in entity_store.relationships["related_to"]
    assert "C" in entity_store.relationships["related_to"]

def test_entity_data_validation(entity_store: EntityStore) -> None:
    """Test validation of entity data before adding."""
    # Test with empty data
    assert entity_store.add_entity({}) is None
    
    # Test with None values
    data: Dict[str, Any] = {
        "uei": None,
        "name": None
    }
    assert entity_store.add_entity(data) is None
    
    # Test with invalid types
    data = {
        "uei": str(12345),  # Convert to string
        "name": "Test"
    }
    assert entity_store.add_entity(data) is not None
    
    # Test with valid data
    data = {
        "uei": "12345",
        "name": "Test"
    }
    assert entity_store.add_entity(data) is not None

def test_stats_accuracy(entity_store: EntityStore) -> None:
    """Test that entity statistics are accurately maintained."""
    # Add valid entity
    entity_store.add_entity({"uei": "TEST1", "name": "Test 1"})
    assert entity_store.stats.total == 1
    assert entity_store.stats.unique == 1
    
    # Add duplicate entity
    entity_store.add_entity({"uei": "TEST1", "name": "Test 1"})
    assert entity_store.stats.total == 2  # Total increases
    assert entity_store.stats.unique == 1  # Unique stays same
    
    # Add invalid entity
    entity_store.add_entity(None)
    assert entity_store.stats.total == 2  # Shouldn't increase
    assert entity_store.stats.unique == 1
    assert entity_store.stats.skipped["invalid_data"] == 1

def test_process_relationships_error_handling(entity_store: EntityStore) -> None:
    """Test error handling in relationship processing."""
    # Test with invalid entity data type
    entity_store.process_relationships([], {})  # Should not raise exception
    
    # Test with missing configuration
    entity_store.process_relationships({"some": "data"}, {})  # Should handle gracefully
    
    # Test with invalid relationship configuration
    config = entity_store.config.copy()
    config['contracts']['entity_separation']['entities']['recipient']['relationships'] = None
    store = EntityStore(entity_store.base_path, "recipient", config)
    store.process_relationships({"uei": "TEST1"}, {})  # Should handle gracefully

def test_hierarchical_key_generation(tmp_path: Path, sample_config: Dict[str, Any]) -> None:
    """Test key generation for hierarchical entities."""
    store = EntityStore(str(tmp_path / "test"), "agency", sample_config)
    
    # Test department level
    dept_data = {
        "agency_code": "001",
        "agency_name": "Test Department"
    }
    dept_key = store._get_level_key("department", dept_data, 
                                  sample_config['contracts']['entity_separation']['entities']['agency'])
    assert dept_key is not None
    assert "001" in dept_key
    
    # Test office level with unique_id
    office_data = {
        "unique_id": "OFF_001",
        "office_name": "Test Office"
    }
    office_key = store._get_level_key("office", office_data,
                                    sample_config['contracts']['entity_separation']['entities']['agency'])
    assert office_key == "OFF_001"

def test_file_load_error_handling(tmp_path: Path, sample_config: Dict[str, Any]) -> None:
    """Test handling of various file loading errors."""
    file_path = tmp_path / "test_recipient"
    
    # Test with invalid JSON
    with open(f"{file_path}_recipient.json", "w") as f:
        f.write("invalid json content")
    
    store = EntityStore(str(file_path), "recipient", sample_config)
    assert store.cache == {}  # Empty cache on invalid JSON
    
    # Test with valid JSON but invalid structure
    with open(f"{file_path}_recipient.json", "w") as f:
        json.dump(["not a dict"], f)
    
    store = EntityStore(str(file_path), "recipient", sample_config)
    assert store.cache == {}  # Empty cache on invalid structure

def test_parent_child_circular_reference(entity_store: EntityStore) -> None:
    """Test handling of circular parent-child relationships in recipients."""
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
    entity_store.add_entity(entity1)
    entity_store.add_entity(entity2)
    
    # Verify only one parent-child relationship was established
    assert len(entity_store.cache["UEI1"].get("subsidiaries", [])) == 0
    assert "UEI2" in entity_store.cache
    assert len(entity_store.cache["UEI2"].get("subsidiaries", [])) == 1

def test_process_hierarchical_relationships_full(tmp_path: Path, sample_config: Dict[str, Any]) -> None:
    """Test full hierarchical relationship processing for agencies."""
    store = EntityStore(str(tmp_path / "test"), "agency", sample_config)
    
    # Create a full agency hierarchy
    entities = {
        "department": {
            "key": "DEPT_001",
            "data": {"code": "001", "name": "Test Department"}
        },
        "agency": {
            "key": "AGCY_001_01",
            "data": {"code": "01", "name": "Test Agency"}
        },
        "office": {
            "key": "OFFC_001_01_001",
            "data": {"code": "001", "name": "Test Office"}
        }
    }
    
    store._process_hierarchical_relationships(entities)
    
    # Check department -> agency relationship
    assert "supervises" in store.relationships
    assert "DEPT_001" in store.relationships["supervises"]
    assert "AGCY_001_01" in store.relationships["supervises"]["DEPT_001"]
    
    # Check agency -> office relationship
    assert "AGCY_001_01" in store.relationships["supervises"]
    assert "OFFC_001_01_001" in store.relationships["supervises"]["AGCY_001_01"]
    
    # Check inverse relationships
    assert "belongs_to" in store.relationships
    assert "AGCY_001_01" in store.relationships["belongs_to"]
    assert "DEPT_001" in store.relationships["belongs_to"]["AGCY_001_01"]
    assert "OFFC_001_01_001" in store.relationships["belongs_to"]
    assert "AGCY_001_01" in store.relationships["belongs_to"]["OFFC_001_01_001"]

def test_save_regular_entities_with_batching(tmp_path: Path, sample_config: Dict[str, Any]) -> None:
    """Test saving regular entities with relationship batching."""
    store = EntityStore(str(tmp_path / "test"), "agency", sample_config)
    
    # Add multiple entities and relationships exceeding batch size
    for i in range(2500):  # More than batch size (1000)
        entity_key = f"DEPT_{i:04d}"
        store.cache[entity_key] = {"code": str(i), "name": f"Department {i}"}
        
        if i > 0:
            # Create relationships that will need batching
            store.add_relationship(f"DEPT_{i:04d}", "reports_to", f"DEPT_{i-1:04d}")
    
    # Save and verify no temporary files remain
    store.save()
    
    base_path = str(tmp_path / "test")
    temp_files = [
        f"{base_path}_agency.json.tmp",
        f"{base_path}_agency.json.reports_to.tmp"
    ]
    
    for temp_file in temp_files:
        assert not Path(temp_file).exists()
    
    # Load saved file and verify relationships
    with open(f"{base_path}_agency.json", 'r', encoding='utf-8') as f:
        saved_data = json.load(f)
        
    assert len(saved_data["entities"]) == 2500
    assert "relationships" in saved_data
    assert "reports_to" in saved_data["relationships"]
    assert len(saved_data["relationships"]["reports_to"]) == 2499  # One less than total

def test_relationship_batch_recovery(tmp_path: Path, sample_config: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """Test recovery from errors during relationship batch processing."""
    store = EntityStore(str(tmp_path / "test"), "agency", sample_config)
    
    # Add test relationships
    for i in range(10):
        store.add_relationship(f"A{i}", "related_to", f"B{i}")
    
    # Simulate error during batch write
    error_count = 0
    original_dump = json.dump
    
    def mock_dump(*args: Any, **kwargs: Any) -> None:
        nonlocal error_count
        if error_count == 0:
            error_count += 1
            raise IOError("Simulated batch write error")
        return original_dump(*args, **kwargs)
    
    monkeypatch.setattr(json, "dump", mock_dump)
    
    # Save should raise the error but clean up temp files
    with pytest.raises(Exception):
        store.save()
    
    # Verify temp files were cleaned up
    base_path = str(tmp_path / "test")
    temp_files = [
        f"{base_path}_agency.json.tmp",
        f"{base_path}_agency.json.related_to.tmp"
    ]
    
    for temp_file in temp_files:
        assert not Path(temp_file).exists()

def test_nested_recipient_structure(entity_store: EntityStore) -> None:
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
        entity_store.add_entity(entity)
    
    # Save and reload to verify structure
    entity_store.save()
    
    new_store = EntityStore(entity_store.base_path, "recipient", entity_store.config)
    
    # Verify parent has all children
    parent = new_store.cache["PARENT"]
    assert len(parent["subsidiaries"]) == 2
    assert "CHILD1" in parent["subsidiaries"]
    assert "CHILD2" in parent["subsidiaries"]
    
    # Verify child has grandchild
    child1 = new_store.cache["CHILD1"]
    assert len(child1["subsidiaries"]) == 1
    assert "GRANDCHILD1" in child1["subsidiaries"]

def test_recipient_tree_build(entity_store: EntityStore) -> None:
    """Test the recursive build_entity_tree function for recipients."""
    # Add a parent with multiple children
    parent_data = {"uei": "P1", "name": "Parent", "type": "Corporation"}
    child1_data = {"uei": "C1", "name": "Child 1", "parent_uei": "P1"}
    child2_data = {"uei": "C2", "name": "Child 2", "parent_uei": "P1"}
    
    entity_store.add_entity(child1_data)  # Add children first to test parent creation
    entity_store.add_entity(child2_data)
    entity_store.add_entity(parent_data)
    
    # Save to test tree building
    entity_store.save()
    
    # Load and verify the tree structure
    with open(entity_store.file_path, 'r', encoding='utf-8') as f:
        saved_data = json.load(f)
    
    # Verify the nested structure
    parent = saved_data["entities"]["P1"]
    assert parent["name"] == "Parent"
    assert parent["type"] == "Corporation"
    assert len(parent["subsidiaries"]) == 2
    
    # Verify children are fully expanded, not just references
    subsidiaries = parent["subsidiaries"]
    assert any(s["uei"] == "C1" and s["name"] == "Child 1" for s in subsidiaries)
    assert any(s["uei"] == "C2" and s["name"] == "Child 2" for s in subsidiaries)

def test_save_with_invalid_config(tmp_path: Path, sample_config: Dict[str, Any]) -> None:
    """Test saving with invalid configuration."""
    invalid_config = sample_config.copy()
    del invalid_config['contracts']['output']['indent']
    
    store = EntityStore(str(tmp_path / "test"), "recipient", invalid_config)
    store.add_entity({"uei": "TEST1", "name": "Test"})
    
    # Should use default indent
    store.save()
    
    with open(f"{str(tmp_path / 'test')}_recipient.json", 'r') as f:
        content = f.read()
        assert '\n' in content  # Verify some form of formatting exists

def test_mixed_relationship_types(entity_store: EntityStore) -> None:
    """Test handling of different relationship type configurations."""
    # Add some hierarchical relationships
    entity_store.add_relationship("DEPT1", "supervises", "OFFICE1")
    entity_store.add_relationship("OFFICE1", "belongs_to", "DEPT1")
    
    # Add some transactional relationships
    entity_store.add_relationship("AWARD1", "awarded_to", "RECIP1")
    entity_store.add_relationship("RECIP1", "received", "AWARD1")
    
    # Save and verify both types are preserved
    entity_store.save()
    
    with open(entity_store.file_path, 'r', encoding='utf-8') as f:
        saved_data = json.load(f)
    
    relationships = saved_data.get("relationships", {})
    assert "supervises" in relationships
    assert "belongs_to" in relationships
    assert "awarded_to" in relationships
    assert "received" in relationships

def test_relationship_stats_accuracy(entity_store: EntityStore) -> None:
    """Test that relationship statistics are accurately maintained."""
    # Add relationships of different types
    relationships = [
        ("A", "type1", "B"),
        ("A", "type1", "C"),  # Same type
        ("X", "type2", "Y"),  # Different type
        ("X", "type2", "Y"),  # Duplicate (should not increase count)
    ]
    
    for from_key, rel_type, to_key in relationships:
        entity_store.add_relationship(from_key, rel_type, to_key)
    
    # Verify counts
    assert entity_store.stats.relationships["type1"] == 2
    assert entity_store.stats.relationships["type2"] == 1

def test_encoding_error_handling(tmp_path: Path, sample_config: Dict[str, Any]) -> None:
    """Test handling of encoding errors during file operations."""
    # Create store with invalid encoding
    invalid_config = sample_config.copy()
    invalid_config['global']['encoding'] = 'invalid-encoding'
    
    store = EntityStore(str(tmp_path / "test"), "recipient", invalid_config)
    store.add_entity({"uei": "TEST1", "name": "Test 株式会社"})
    
    # Should fall back to UTF-8
    store.save()
    
    # Verify content was saved
    with open(f"{str(tmp_path / 'test')}_recipient.json", 'r', encoding='utf-8') as f:
        data = json.load(f)
        assert "TEST1" in data["entities"]
        assert data["entities"]["TEST1"]["name"] == "Test 株式会社"

def test_concurrent_file_access(tmp_path: Path, sample_config: JsonDict) -> None:
    """Test concurrent file access patterns."""
    import threading
    import time
    from queue import Queue
    
    result_queue: Queue[Tuple[str, int, Optional[str]]] = Queue()
    base_path = str(tmp_path / "test")
    
    def worker(worker_id: int) -> None:
        try:
            store = EntityStore(base_path, "recipient", sample_config)
            store.add_entity({
                "uei": f"TEST{worker_id}",
                "name": f"Test Entity {worker_id}"
            })
            store.save()
            result_queue.put(("success", worker_id, None))
        except Exception as e:
            result_queue.put(("error", worker_id, str(e)))
    
    # Start multiple threads to simulate concurrent access
    threads: List[threading.Thread] = []
    for i in range(5):
        thread = threading.Thread(target=worker, args=(i,))
        thread.start()
        threads.append(thread)
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    # Check results
    results: List[Tuple[str, int, Optional[str]]] = []
    while not result_queue.empty():
        results.append(result_queue.get())
    
    # Verify only one thread succeeded
    success_count = sum(1 for r in results if r[0] == "success")
    assert success_count >= 1, "At least one save operation should succeed"
    
    # Load final state
    final_store = EntityStore(base_path, "recipient", sample_config)
    assert len(final_store.cache) > 0, "Final store should contain data"

def test_missing_config_sections(tmp_path: Path) -> None:
    """Test EntityStore behavior with missing configuration sections."""
    minimal_config: Dict[str, Any] = {
        "global": {
            "encoding": "utf-8"
        },
        "contracts": {
            "output": {
                "indent": 2
            }
        }
    }
    
    # Should initialize with empty entity config
    store = EntityStore(str(tmp_path / "test"), "recipient", minimal_config)
    
    # Basic operations should still work
    key = store.add_entity({"uei": "TEST1", "name": "Test"})
    assert key == "TEST1"
    
    # Save should work with default settings
    store.save()
    assert Path(store.file_path).exists()

def test_invalid_field_mappings(tmp_path: Path, sample_config: Dict[str, Any]) -> None:
    """Test handling of invalid field mappings in configuration."""
    config = sample_config.copy()
    config['contracts']['entity_separation']['entities']['recipient']['field_mappings'] = None
    
    store = EntityStore(str(tmp_path / "test"), "recipient", config)
    
    # Should still process entity without mapped fields
    data = {"uei": "TEST1", "unmapped_field": "value"}
    key = store.add_entity(data)
    
    assert key == "TEST1"
    assert "unmapped_field" in store.cache[key]

def test_file_permission_handling(tmp_path: Path, sample_config: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """Test handling of file permission errors."""
    import errno
    
    store = EntityStore(str(tmp_path / "test"), "recipient", sample_config)
    store.add_entity({"uei": "TEST1", "name": "Test"})
    
    def mock_open(*args: Any, **kwargs: Any) -> None:
        raise PermissionError(errno.EACCES, "Permission denied")
    
    monkeypatch.setattr("builtins.open", mock_open)
    
    with pytest.raises(Exception) as exc_info:
        store.save()
    assert "Permission denied" in str(exc_info.value)

def test_nested_relationship_handling(tmp_path: Path, sample_config: Dict[str, Any]) -> None:
    """Test handling of deeply nested relationships."""
    store = EntityStore(str(tmp_path / "test"), "recipient", sample_config)
    
    # Create a deep chain of relationships
    entities = []
    relationships = []
    
    for i in range(10):  # Create 10 levels deep
        entity = {
            "uei": f"E{i}",
            "name": f"Entity {i}",
            "level": i
        }
        entities.append(entity)
        
        if i > 0:
            relationships.append((f"E{i}", "reports_to", f"E{i-1}"))
    
    # Add entities and relationships
    for entity in entities:
        store.add_entity(entity)
    
    for from_key, rel_type, to_key in relationships:
        store.add_relationship(from_key, rel_type, to_key)
    
    # Save and verify
    store.save()
    
    # Load and check structure
    with open(store.file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
        # Verify all entities exist
        assert len(data["entities"]) == 10
        
        # Verify relationship chain
        rels = data["relationships"]["reports_to"]
        assert len(rels) == 9  # Should have n-1 relationships
        
        # Verify chain is complete
        for i in range(1, 10):
            assert f"E{i}" in rels
            assert f"E{i-1}" in rels[f"E{i}"]

def test_corrupted_relationship_recovery(tmp_path: Path, sample_config: Dict[str, Any]) -> None:
    """Test recovery from corrupted relationship data."""
    store = EntityStore(str(tmp_path / "test"), "recipient", sample_config)
    
    # Add some valid relationships
    store.add_relationship("A", "related_to", "B")
    store.add_relationship("B", "related_to", "C")
    
    # Save initial state
    store.save()
    
    # Corrupt the file by writing invalid relationship data
    file_path = store.file_path
    with open(file_path, 'r+', encoding='utf-8') as f:
        data = json.load(f)
        data["relationships"]["related_to"]["B"] = None  # Invalid relationship data
        f.seek(0)
        f.truncate()
        json.dump(data, f)
    
    # Create new store - should handle corrupted relationships gracefully
    new_store = EntityStore(str(tmp_path / "test"), "recipient", sample_config)
    
    # Verify valid relationships were preserved
    assert "A" in new_store.relationships.get("related_to", {})
    assert "B" in new_store.relationships.get("related_to", {}).get("A", set())

def test_atomic_file_operations(tmp_path: Path, sample_config: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """Test atomicity of file operations."""
    store = EntityStore(str(tmp_path / "test"), "recipient", sample_config)
    store.add_entity({"uei": "TEST1", "name": "Test"})
    
    # Mock os.replace to fail
    def mock_replace(*args: Any, **kwargs: Any) -> None:
        raise OSError("Simulated replace error")
    
    monkeypatch.setattr("os.replace", mock_replace)
    
    # Attempt save - should fail but clean up temp files
    with pytest.raises(OSError):
        store.save()
    
    # Verify temp file was cleaned up
    assert not Path(store.temp_file_path).exists()
    
    # Original file should not exist since this is a new store
    assert not Path(store.file_path).exists()

def test_batch_save_monitoring(entity_store: EntityStore, tmp_path: Path) -> None:
    """Test batch saving with transaction monitoring."""
    # Add a large number of entities to test batch processing
    batch_size = 500
    for i in range(batch_size):
        entity_data = {
            "uei": f"UEI{i:05d}",
            "name": f"Entity {i}",
            "batch": "test_batch"
        }
        entity_store.add_entity(entity_data)
        
        # Add some relationships
        if i > 0:
            entity_store.add_relationship(f"UEI{i:05d}", "follows", f"UEI{i-1:05d}")
    
    # Save and verify
    entity_store.save()
    
    # Verify the file exists and has correct data
    assert Path(entity_store.file_path).exists()
    
    # Load in new store and verify data integrity
    new_store = EntityStore(entity_store.base_path, "recipient", entity_store.config)
    assert len(new_store.cache) == batch_size
    assert new_store.stats.total == batch_size
    assert new_store.stats.unique == batch_size
    assert len(new_store.relationships["follows"]) == batch_size - 1  # One less relationship than entities
    
    # Verify relationship integrity
    for i in range(1, batch_size):
        rel_key = f"UEI{i:05d}:UEI{i-1:05d}"
        assert rel_key in new_store.relationships["follows"]