"""Tests for relationship management functionality."""
import pytest
from src.usaspending.core.relationships import RelationshipManager
from src.usaspending.core.types import EntityType, RelationType

@pytest.fixture
def relationship_manager():
    return RelationshipManager()

def test_add_relationship(relationship_manager):
    """Test adding a relationship between entities."""
    relationship_manager.add_relationship(
        source_entity='contract',
        target_entity='vendor',
        relationship_type=RelationType.MANY_TO_ONE,
        source_fields=['vendor_id'],
        target_fields=['id']
    )
    
    relationships = relationship_manager.get_relationships('contract')
    assert len(relationships) == 1
    assert relationships[0].target_entity == 'vendor'

def test_validate_relationship(relationship_manager):
    """Test relationship validation."""
    relationship_manager.add_relationship(
        source_entity='contract',
        target_entity='vendor',
        relationship_type=RelationType.MANY_TO_ONE,
        source_fields=['vendor_id'],
        target_fields=['id']
    )
    
    # Valid relationship data
    assert relationship_manager.validate_relationship(
        'contract',
        'vendor',
        {'vendor_id': '123'},
        {'id': '123'}
    )
    
    # Invalid relationship data
    assert not relationship_manager.validate_relationship(
        'contract',
        'vendor',
        {'vendor_id': '123'},
        {'id': '456'}
    )

def test_get_related_entities(relationship_manager):
    """Test getting related entities."""
    relationship_manager.add_relationship(
        source_entity='contract',
        target_entity='vendor',
        relationship_type=RelationType.MANY_TO_ONE,
        source_fields=['vendor_id'],
        target_fields=['id']
    )
    
    related = relationship_manager.get_related_entities('contract')
    assert 'vendor' in related
    assert related['vendor'].relationship_type == RelationType.MANY_TO_ONE

def test_get_relationship_path(relationship_manager):
    """Test finding path between entities."""
    relationship_manager.add_relationship(
        source_entity='contract',
        target_entity='vendor',
        relationship_type=RelationType.MANY_TO_ONE,
        source_fields=['vendor_id'],
        target_fields=['id']
    )
    relationship_manager.add_relationship(
        source_entity='vendor',
        target_entity='address',
        relationship_type=RelationType.ONE_TO_ONE,
        source_fields=['address_id'],
        target_fields=['id']
    )
    
    path = relationship_manager.get_relationship_path('contract', 'address')
    assert len(path) == 2
    assert path[0].target_entity == 'vendor'
    assert path[1].target_entity == 'address'
