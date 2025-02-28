"""Test base entity store functionality."""
import pytest
from pathlib import Path
import json
from collections import defaultdict
from typing import Dict, Any, Optional, Set, DefaultDict
from usaspending.base_entity_store import BaseEntityStore
from usaspending.types import EntityStats

class TestEntityStore(BaseEntityStore):
    """Test implementation of BaseEntityStore."""
    def extract_entity_data(self, row_data):
        return row_data
        
    def add_entity(self, entity_data):
        if entity_data is None:
            self.stats.skipped["invalid_data"] += 1
            return None
        self.stats.total += 1
        key = str(entity_data.get("id", ""))
        if key:
            self.cache[key] = entity_data
            self.stats.unique += 1
        return key
        
    def save(self):
        try:
            from datetime import datetime
            
            # Prepare output data
            output_data = {
                "metadata": {
                    "entity_type": self.entity_type,
                    "total_references": self.stats.total,
                    "unique_entities": self.stats.unique,
                    "relationship_counts": dict(self.stats.relationships),
                    "skipped_entities": dict(self.stats.skipped),
                    "natural_keys_used": self.stats.natural_keys_used,
                    "hash_keys_used": self.stats.hash_keys_used,
                    "generated_date": datetime.now().isoformat()
                },
                "entities": self.cache,
                "relationships": {
                    rel_type: {from_key: list(to_keys) 
                              for from_key, to_keys in rel_map.items()}
                    for rel_type, rel_map in self.relationships.items()
                }
            }
            
            # Write to temp file first
            with open(self.temp_file_path, 'w', encoding=self._get_encoding()) as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            # Atomic replace
            Path(self.temp_file_path).replace(self.file_path)
            
        except Exception as e:
            self._cleanup_temp_files()
            raise

@pytest.fixture
def base_store(tmp_path: Path, sample_config: Dict[str, Any]) -> BaseEntityStore:
    """Create a test entity store."""
    return TestEntityStore(str(tmp_path / "test"), "test", sample_config)

def test_base_store_initialization(base_store: BaseEntityStore) -> None:
    """Test that BaseEntityStore initializes correctly."""
    assert base_store.entity_type == "test"
    assert isinstance(base_store.stats, EntityStats)
    assert base_store.cache == {}
    assert base_store.relationships == {}

def test_relationship_handling(base_store: BaseEntityStore) -> None:
    """Test adding and retrieving relationships."""
    base_store.add_relationship("A", "related_to", "B")
    base_store.add_relationship("A", "related_to", "C")
    
    assert "related_to" in base_store.relationships
    assert "A" in base_store.relationships["related_to"]
    assert base_store.relationships["related_to"]["A"] == {"B", "C"}
    assert base_store.stats.relationships["related_to"] == 2

def test_save_and_load(base_store: BaseEntityStore) -> None:
    """Test saving and loading entities."""
    # Add test data
    base_store.add_entity({"id": "1", "name": "Test"})
    base_store.add_relationship("1", "related_to", "2")
    base_store.save()
    
    # Create new store and verify loaded data
    new_store = TestEntityStore(base_store.base_path, "test", base_store.config)
    assert "1" in new_store.cache
    assert new_store.cache["1"]["name"] == "Test"
    assert "related_to" in new_store.relationships
    assert "1" in new_store.relationships["related_to"]
    assert "2" in new_store.relationships["related_to"]["1"]

def test_invalid_initialization() -> None:
    """Test invalid initialization parameters."""
    with pytest.raises(ValueError, match="base_path must be a non-empty string"):
        TestEntityStore("", "test", {})
    with pytest.raises(ValueError, match="entity_type must be a non-empty string"):
        TestEntityStore("/test", "", {})
    with pytest.raises(ValueError, match="config must be a dictionary"):
        TestEntityStore("/test", "test", None)

def test_cleanup_temp_files(base_store: BaseEntityStore, tmp_path: Path) -> None:
    """Test cleanup of temporary files."""
    # Create temp files
    temp_files = [
        base_store.temp_file_path,
        f"{base_store.file_path}.rel1.tmp",
        f"{base_store.file_path}.rel2.tmp"
    ]
    for file in temp_files:
        Path(file).touch()
    
    base_store._cleanup_temp_files()
    
    # Verify files are removed
    for file in temp_files:
        assert not Path(file).exists()

def test_metadata_in_saved_file(base_store: BaseEntityStore) -> None:
    """Test that metadata is correctly included in saved files."""
    base_store.add_entity({"id": "1", "name": "Test"})
    base_store.save()
    
    with open(base_store.file_path, 'r', encoding='utf-8') as f:
        saved_data = json.load(f)
    
    assert "metadata" in saved_data
    metadata = saved_data["metadata"]
    assert metadata["entity_type"] == "test"
    assert metadata["total_references"] == 1
    assert metadata["unique_entities"] == 1
    assert "generated_date" in metadata
    assert "skipped_entities" in metadata
    assert "relationship_counts" in metadata