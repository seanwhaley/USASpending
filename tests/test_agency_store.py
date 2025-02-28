"""Test agency entity store functionality."""
import pytest
from pathlib import Path
import json
from typing import Dict, Any
from usaspending.agency_store import AgencyEntityStore
from usaspending.types import ParentAgencyReference

@pytest.fixture
def agency_store(tmp_path: Path, sample_config: Dict[str, Any]) -> AgencyEntityStore:
    """Create a test agency store."""
    return AgencyEntityStore(str(tmp_path / "test"), "agency", sample_config)

@pytest.fixture
def sample_agency_data() -> Dict[str, Any]:
    """Provide sample hierarchical agency data."""
    return {
        "department": {
            "key": "DEPT_001",
            "data": {
                "code": "001",
                "name": "Test Department"
            }
        },
        "agency": {
            "key": "AGCY_001_01",
            "data": {
                "code": "01",
                "name": "Test Agency"
            }
        },
        "office": {
            "key": "OFFC_001_01_001",
            "data": {
                "code": "001",
                "name": "Test Office",
                "unique_id": "001_01_001"
            }
        }
    }

@pytest.fixture
def sample_agency_row_data() -> Dict[str, Any]:
    """Provide sample row data for agency extraction."""
    return {
        "awarding_agency_code": "001",
        "awarding_agency_name": "Test Department",
        "awarding_subagency_code": "01",
        "awarding_subagency_name": "Test Agency",
        "awarding_office_code": "001",
        "awarding_office_name": "Test Office"
    }

def test_agency_data_extraction(agency_store: AgencyEntityStore, sample_agency_row_data: Dict[str, Any]) -> None:
    """Test extraction of agency data from row data."""
    result = agency_store.extract_entity_data(sample_agency_row_data)
    assert result is not None
    assert "department" in result
    assert "agency" in result
    assert "office" in result
    
    dept = result["department"]
    assert dept["data"]["code"] == "001"
    assert dept["data"]["name"] == "Test Department"
    
    agency = result["agency"]
    assert agency["data"]["code"] == "01"
    assert agency["data"]["name"] == "Test Agency"

def test_hierarchical_relationships(agency_store: AgencyEntityStore, sample_agency_data: Dict[str, Any]) -> None:
    """Test handling of hierarchical agency relationships."""
    result = agency_store.add_entity(sample_agency_data)
    
    assert isinstance(result, dict)
    assert set(result.keys()) == {"department", "agency", "office"}
    
    # Verify relationships were created
    assert "HAS_SUBAGENCY" in agency_store.relationships
    assert "BELONGS_TO_AGENCY" in agency_store.relationships
    
    dept_key = sample_agency_data["department"]["key"]
    agency_key = sample_agency_data["agency"]["key"]
    office_key = sample_agency_data["office"]["key"]
    
    # Check department supervises agency
    assert agency_key in agency_store.relationships["HAS_SUBAGENCY"][dept_key]
    # Check agency belongs to department
    assert dept_key in agency_store.relationships["BELONGS_TO_AGENCY"][agency_key]
    # Check agency has office
    assert office_key in agency_store.relationships["HAS_OFFICE"][agency_key]
    # Check office belongs to agency
    assert agency_key in agency_store.relationships["BELONGS_TO_SUBAGENCY"][office_key]

def test_agency_funding_fallback(agency_store: AgencyEntityStore) -> None:
    """Test fallback to funding fields when awarding fields are missing."""
    row_data = {
        "funding_agency_code": "002",
        "funding_agency_name": "Test Department 2",
        "funding_subagency_code": "02",
        "funding_subagency_name": "Test Agency 2"
    }
    
    result = agency_store.extract_entity_data(row_data)
    assert result is not None
    assert "department" in result
    assert "agency" in result
    
    dept = result["department"]
    assert dept["data"]["code"] == "002"
    assert dept["data"]["name"] == "Test Department 2"
    
    agency = result["agency"]
    assert agency["data"]["code"] == "02"
    assert agency["data"]["name"] == "Test Agency 2"

def test_office_unique_id_handling(agency_store: AgencyEntityStore) -> None:
    """Test handling of office entities with unique IDs."""
    office_data = {
        "office": {
            "data": {
                "unique_id": "OFF_001",
                "name": "Test Office",
                "code": "001"
            }
        }
    }
    
    result = agency_store.add_entity(office_data)
    assert result is not None
    assert "office" in result
    assert isinstance(result["office"], str)
    assert office_data["office"]["data"]["unique_id"] in result["office"]

def test_agency_save_and_load(agency_store: AgencyEntityStore, sample_agency_data: Dict[str, Any]) -> None:
    """Test saving and loading agency hierarchy."""
    # Add and save agency structure
    agency_store.add_entity(sample_agency_data)
    agency_store.save()
    
    # Load in new store
    new_store = AgencyEntityStore(agency_store.base_path, "agency", agency_store.config)
    
    # Verify all entities were loaded
    dept_key = sample_agency_data["department"]["key"]
    agency_key = sample_agency_data["agency"]["key"]
    office_key = sample_agency_data["office"]["key"]
    
    assert dept_key in new_store.cache
    assert agency_key in new_store.cache
    assert office_key in new_store.cache
    
    # Verify relationships were preserved
    assert "HAS_SUBAGENCY" in new_store.relationships
    assert agency_key in new_store.relationships["HAS_SUBAGENCY"][dept_key]
    assert "BELONGS_TO_AGENCY" in new_store.relationships
    assert dept_key in new_store.relationships["BELONGS_TO_AGENCY"][agency_key]

def test_invalid_hierarchical_data(agency_store: AgencyEntityStore) -> None:
    """Test handling of invalid hierarchical data."""
    # Test with missing key fields
    invalid_data = {
        "department": {
            "data": {
                "name": "Test Department"
                # Missing code field
            }
        }
    }
    result = agency_store.add_entity(invalid_data)
    assert result is None
    
    # Test with invalid level name
    invalid_data = {
        "invalid_level": {
            "data": {
                "code": "001",
                "name": "Test"
            }
        }
    }
    result = agency_store.add_entity(invalid_data)
    assert result is None

@pytest.fixture
def sample_config():
    return {
        'contracts': {
            'entity_separation': {
                'entities': {
                    'agency': {
                        'levels': {
                            'department': {
                                'key_fields': ['code'],
                                'field_mappings': {
                                    'code': ['agency_code'],
                                    'name': ['agency_name']
                                }
                            },
                            'sub_agency': {
                                'key_fields': ['code'],
                                'field_mappings': {
                                    'code': ['sub_agency_code'],
                                    'name': ['sub_agency_name']
                                }
                            }
                        }
                    }
                }
            }
        }
    }

def test_resolve_known_parent_agency(sample_config):
    """Test resolving parent agency that exists in regular hierarchy."""
    store = AgencyEntityStore('test_path', 'agency', sample_config)
    
    # Add regular agency first
    dept_data = {
        'department': {
            'data': {'code': '123', 'name': 'Test Department'},
            'key': 'AGENCY_DEPT_123'
        }
    }
    store.add_entity(dept_data)
    
    # Try to resolve parent reference matching existing agency
    level, agency_id = store.resolve_parent_agency('123', 'Test Department')
    
    assert level == 'department'
    assert agency_id == 'AGENCY_DEPT_123'

def test_resolve_unknown_parent_agency(sample_config):
    """Test handling of unknown parent agency."""
    store = AgencyEntityStore('test_path', 'agency', sample_config)
    
    # Try to resolve unknown parent
    level, agency_id = store.resolve_parent_agency('999', 'Unknown Agency')
    
    assert level == 'pending'
    assert agency_id == '999'
    assert '999' in store.pending_parents

def test_parent_agency_resolution_after_regular_add(sample_config):
    """Test parent agency gets resolved when matching agency added later."""
    store = AgencyEntityStore('test_path', 'agency', sample_config)
    
    # First reference unknown parent
    level1, agency_id1 = store.resolve_parent_agency('456', 'Later Agency')
    assert level1 == 'pending'
    
    # Then add matching agency normally
    dept_data = {
        'department': {
            'data': {'code': '456', 'name': 'Later Agency'},
            'key': 'AGENCY_DEPT_456'
        }
    }
    store.add_entity(dept_data)
    
    # Resolve again - should now match
    level2, agency_id2 = store.resolve_parent_agency('456', 'Later Agency')
    assert level2 == 'department'
    assert agency_id2 == 'AGENCY_DEPT_456'

def test_finalize_parent_agencies(sample_config):
    """Test finalizing unresolved parent agencies."""
    store = AgencyEntityStore('test_path', 'agency', sample_config)
    
    # Add some unresolved parents
    store.resolve_parent_agency('888', 'Pending Agency 1')
    store.resolve_parent_agency('999', 'Pending Agency 2')
    
    # Finalize
    store.finalize_parent_agencies()
    
    # Check they were added as department level
    assert any(a.get('code') == '888' for a in store.cache.values())
    assert any(a.get('code') == '999' for a in store.cache.values())
    
    # Verify mappings
    assert store.parent_mappings['888']['level'] == 'department'
    assert store.parent_mappings['999']['level'] == 'department'