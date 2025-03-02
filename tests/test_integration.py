"""Integration tests for entity processing pipeline."""
import pytest
import os
import json
import shutil
from pathlib import Path
from datetime import datetime

from usaspending.processor import convert_csv_to_json
from usaspending.entity_store import EntityStore
from usaspending.config import ConfigManager

# Test data directory setup
TEST_DATA_DIR = Path(__file__).parent / "data"
TEST_DATA_DIR.mkdir(exist_ok=True)

# Test configuration
TEST_CONFIG = {
    "global": {
        "encoding": "utf-8",
        "datetime_format": "%Y-%m-%d %H:%M:%S",
        "io": {
            "input": {
                "file": str(TEST_DATA_DIR / "test_transactions.csv"),
                "batch_size": 100,
                "validate_input": True,
                "skip_invalid_rows": False
            },
            "output": {
                "directory": str(TEST_DATA_DIR / "output"),
                "entities_subfolder": "entities",
                "transaction_base_name": "transactions",
                "chunk_size": 1000
            }
        },
        "formats": {
            "csv": {
                "encoding": "utf-8-sig",
                "delimiter": ",",
                "quotechar": '"'
            },
            "json": {
                "indent": 2,
                "ensure_ascii": False
            }
        }
    },
    "validation_types": {
        "numeric": {
            "money": {"strip_characters": "$,."},
            "decimal": {"strip_characters": ",."},
            "integer": {"strip_characters": ","}
        },
        "date": {
            "standard": {"format": "%Y-%m-%d"}
        },
        "custom": {
            "zip": {
                "validator": "zip",
                "args": {"pattern": r"^\d{5}(?:-\d{4})?$"}
            }
        }
    },
    "entities": {
        "contract": {
            "enabled": True,
            "key_fields": ["contract_id"],
            "field_mappings": {
                "direct": {
                    "id": {"field": "contract_id"},
                    "description": {"field": "contract_description"},
                    "amount": {
                        "field": "contract_amount",
                        "transformation": {
                            "type": "money",
                            "pre": [{"operation": "strip", "characters": "$,"}]
                        }
                    }
                },
                "object": {
                    "period": {
                        "fields": {
                            "start_date": {
                                "field": "period_of_performance_start",
                                "transformation": {"type": "date"}
                            },
                            "end_date": {
                                "field": "period_of_performance_end",
                                "transformation": {"type": "date"}
                            }
                        }
                    }
                },
                "reference": {
                    "recipient": {
                        "entity_type": "recipient",
                        "fields": {
                            "id": {"field": "recipient_id"},
                            "name": {"field": "recipient_name"}
                        }
                    }
                }
            }
        },
        "recipient": {
            "enabled": True,
            "key_fields": ["recipient_id"],
            "field_mappings": {
                "direct": {
                    "id": {"field": "recipient_id"},
                    "name": {"field": "recipient_name"}
                },
                "object": {
                    "address": {
                        "fields": {
                            "street": {"field": "recipient_address"},
                            "city": {"field": "recipient_city"},
                            "state": {"field": "recipient_state"},
                            "zip": {
                                "field": "recipient_zip",
                                "transformation": {"type": "zip"}
                            }
                        }
                    }
                }
            }
        }
    }
}

@pytest.fixture(scope="module")
def test_data_setup():
    """Create test data CSV file."""
    csv_data = [
        "contract_id,contract_description,contract_amount,period_of_performance_start,period_of_performance_end,"
        "recipient_id,recipient_name,recipient_address,recipient_city,recipient_state,recipient_zip",
        "C0001,Test Contract 1,$100000.00,2024-01-01,2024-12-31,R0001,Test Recipient 1,123 Main St,Springfield,IL,62701",
        "C0002,Test Contract 2,$200000.00,2024-02-01,2024-11-30,R0001,Test Recipient 1,123 Main St,Springfield,IL,62701",
        "C0003,Test Contract 3,$300000.00,2024-03-01,2024-10-31,R0002,Test Recipient 2,456 Oak Ave,Chicago,IL,60601"
    ]
    
    csv_path = TEST_DATA_DIR / "test_transactions.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        f.write("\n".join(csv_data))
    
    # Clean output directory
    output_dir = TEST_DATA_DIR / "output"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    
    yield
    
    # Cleanup after tests
    if csv_path.exists():
        csv_path.unlink()
    if output_dir.exists():
        shutil.rmtree(output_dir)

def test_end_to_end_processing(test_data_setup):
    """Test end-to-end processing pipeline."""
    # Process data
    config_manager = ConfigManager(TEST_CONFIG)
    assert convert_csv_to_json(config_manager) is True
    
    # Verify output structure
    output_dir = TEST_DATA_DIR / "output"
    entities_dir = output_dir / "entities"
    assert output_dir.exists()
    assert entities_dir.exists()
    
    # Check contract entities
    contract_store = EntityStore(str(entities_dir), "contract", config_manager)
    contract_data = contract_store.load()
    assert len(contract_data) == 3
    
    # Verify contract details
    c1 = next(c for c in contract_data.values() if c["id"] == "C0001")
    assert c1["amount"] == 100000.0
    assert c1["period"]["start_date"] == "2024-01-01"
    assert c1["recipient"]["type"] == "recipient"
    assert c1["recipient"]["data"]["id"] == "R0001"
    
    # Check recipient entities
    recipient_store = EntityStore(str(entities_dir), "recipient", config_manager)
    recipient_data = recipient_store.load()
    assert len(recipient_data) == 2  # Should be deduplicated
    
    # Verify recipient details
    r1 = next(r for r in recipient_data.values() if r["id"] == "R0001")
    assert r1["name"] == "Test Recipient 1"
    assert r1["address"]["zip"] == "62701"
    assert len([c for c in contract_data.values() if c["recipient"]["data"]["id"] == "R0001"]) == 2

def test_invalid_data_handling(test_data_setup):
    """Test handling of invalid data."""
    # Add invalid row to test data
    csv_path = TEST_DATA_DIR / "test_transactions.csv"
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        f.write("\nC0004,Invalid Contract,invalid_amount,2024-01-01,2024-12-31,R0003,Test Recipient 3,789 Pine St,Boston,MA,invalid_zip")
    
    # Process with skip_invalid_rows=True
    config = TEST_CONFIG.copy()
    config["global"]["io"]["input"]["skip_invalid_rows"] = True
    config_manager = ConfigManager(config)
    
    assert convert_csv_to_json(config_manager) is True
    
    # Verify valid records were processed
    contract_store = EntityStore(str(TEST_DATA_DIR / "output" / "entities"), "contract", config_manager)
    contract_data = contract_store.load()
    assert len(contract_data) == 3  # Invalid record should be skipped

def test_relationship_integrity(test_data_setup):
    """Test entity relationship integrity."""
    config_manager = ConfigManager(TEST_CONFIG)
    assert convert_csv_to_json(config_manager) is True
    
    contract_store = EntityStore(str(TEST_DATA_DIR / "output" / "entities"), "contract", config_manager)
    recipient_store = EntityStore(str(TEST_DATA_DIR / "output" / "entities"), "recipient", config_manager)
    
    contract_data = contract_store.load()
    recipient_data = recipient_store.load()
    
    # Verify all contracts have valid recipient references
    for contract in contract_data.values():
        recipient_id = contract["recipient"]["data"]["id"]
        assert recipient_id in recipient_data
        
        # Verify recipient data consistency
        recipient = recipient_data[recipient_id]
        ref_recipient = contract["recipient"]["data"]
        assert recipient["name"] == ref_recipient["name"]

def test_transformation_pipeline(test_data_setup):
    """Test data transformation pipeline."""
    config_manager = ConfigManager(TEST_CONFIG)
    assert convert_csv_to_json(config_manager) is True
    
    contract_store = EntityStore(str(TEST_DATA_DIR / "output" / "entities"), "contract", config_manager)
    contract_data = contract_store.load()
    
    # Verify money transformations
    amounts = [c["amount"] for c in contract_data.values()]
    assert all(isinstance(amount, float) for amount in amounts)
    assert sorted(amounts) == [100000.0, 200000.0, 300000.0]
    
    # Verify date transformations
    for contract in contract_data.values():
        assert "period" in contract
        assert datetime.strptime(contract["period"]["start_date"], "%Y-%m-%d")
        assert datetime.strptime(contract["period"]["end_date"], "%Y-%m-%d")
    
    # Verify ZIP code transformations
    recipient_store = EntityStore(str(TEST_DATA_DIR / "output" / "entities"), "recipient", config_manager)
    recipient_data = recipient_store.load()
    zip_codes = [r["address"]["zip"] for r in recipient_data.values()]
    assert all(len(code) == 5 and code.isdigit() for code in zip_codes)