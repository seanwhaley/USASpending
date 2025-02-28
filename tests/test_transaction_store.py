"""Test cases for transaction store parent award handling."""
import pytest
from usaspending.transaction_store import TransactionStore

@pytest.fixture
def sample_config():
    return {
        'contracts': {
            'entity_separation': {
                'entities': {
                    'transaction': {
                        'key_fields': ['contract_transaction_unique_key'],
                        'field_mappings': {
                            'parent_award_agency_id': 'parent_agency_id',
                            'parent_award_agency_name': 'parent_agency_name'
                        }
                    }
                }
            }
        }
    }

def test_extract_parent_agency_reference(sample_config):
    """Test extracting parent agency reference from row."""
    store = TransactionStore('test_path', 'transaction', sample_config)
    
    row_data = {
        'contract_transaction_unique_key': 'TRANS_001',
        'parent_award_agency_id': 'PAR_001',
        'parent_award_agency_name': 'Parent Agency'
    }
    
    result = store.extract_entity_data(row_data)
    
    assert result is not None
    assert 'parent_award_agency' in result
    assert result['parent_award_agency']['id'] == 'PAR_001'
    assert result['parent_award_agency']['name'] == 'Parent Agency'

def test_update_parent_agency_reference(sample_config):
    """Test updating parent agency reference after resolution."""
    store = TransactionStore('test_path', 'transaction', sample_config)
    
    # Add transaction with unresolved parent
    trans_data = {
        'contract_transaction_unique_key': 'TRANS_001',
        'parent_award_agency': {
            'id': 'PAR_001',
            'name': 'Parent Agency'
        }
    }
    trans_key = store.add_entity(trans_data)
    
    # Update with resolved reference
    store.update_parent_agency_reference(trans_key, 'department', 'AGENCY_001')
    
    # Verify update
    updated_trans = store.cache[trans_key]
    assert updated_trans['parent_award_agency']['level'] == 'department'
    assert updated_trans['parent_award_agency']['agency_id'] == 'AGENCY_001'
    assert (trans_key, 'department', 'AGENCY_001') in store.parent_agency_refs
