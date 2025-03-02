"""Integration tests for entity processing pipeline."""
import pytest
import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
import csv
import tempfile
from unittest.mock import patch, Mock

from usaspending.processor import convert_csv_to_json
from usaspending.entity_store import EntityStore
from usaspending.config import ConfigManager

# Test data directory setup
TEST_DATA_DIR = Path(__file__).parent / "data"
TEST_DATA_DIR.mkdir(exist_ok=True)

@pytest.fixture(scope="module")
def test_config():
    """Return a copy of test configuration."""
    return {
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
        }
    }

@pytest.fixture(scope="module")
def mock_config_manager(test_config):
    """Create a mock config manager instance."""
    mock_manager = Mock()
    mock_manager.get_config.return_value = test_config
    mock_manager.get_input_file_path.return_value = str(TEST_DATA_DIR / "test_transactions.csv")
    mock_manager.get_output_directory.return_value = str(TEST_DATA_DIR / "output")
    
    # Fix for __iter__ error
    mock_manager.__iter__ = Mock(return_value=iter([]))
    return mock_manager

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

def test_end_to_end_processing(test_data_setup, mock_config_manager):
    """Test end-to-end processing pipeline."""
    assert convert_csv_to_json(mock_config_manager) is True
    output_dir = TEST_DATA_DIR / "output"
    entities_dir = output_dir / "entities"
    assert output_dir.exists()
    assert entities_dir.exists()
    contract_store = EntityStore(str(entities_dir), "contract", mock_config_manager)
    contract_data = contract_store.load()
    assert len(contract_data) == 3
    c1 = next(c for c in contract_data.values() if c["id"] == "C0001")
    assert c1["amount"] == 100000.0
    assert c1["period"]["start_date"] == "2024-01-01"
    assert c1["recipient"]["type"] == "recipient"
    assert c1["recipient"]["data"]["id"] == "R0001"
    recipient_store = EntityStore(str(entities_dir), "recipient", mock_config_manager)
    recipient_data = recipient_store.load()
    assert len(recipient_data) == 2
    r1 = next(r for r in recipient_data.values() if r["id"] == "R0001")
    assert r1["name"] == "Test Recipient 1"
    assert r1["address"]["zip"] == "62701"
    assert len([c for c in contract_data.values() if c["recipient"]["data"]["id"] == "R0001"]) == 2

def test_invalid_data_handling(test_data_setup, test_config):
    """Test handling of invalid data."""
    csv_path = TEST_DATA_DIR / "test_transactions.csv"
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        f.write("\nC0004,Invalid Contract,invalid_amount,2024-01-01,2024-12-31,R0003,Test Recipient 3,789 Pine St,Boston,MA,invalid_zip")
    modified_config = {**test_config}
    modified_config["global"] = {**test_config["global"]}
    modified_config["global"]["io"] = {**test_config["global"]["io"]}
    modified_config["global"]["io"]["input"] = {**test_config["global"]["io"]["input"], "skip_invalid_rows": True}
    config_manager = ConfigManager(modified_config)
    assert convert_csv_to_json(config_manager) is True
    contract_store = EntityStore(str(TEST_DATA_DIR / "output" / "entities"), "contract", config_manager)
    contract_data = contract_store.load()
    assert len(contract_data) == 3

def test_relationship_integrity(test_data_setup, mock_config_manager):
    """Test entity relationship integrity."""
    assert convert_csv_to_json(mock_config_manager) is True
    contract_store = EntityStore(str(TEST_DATA_DIR / "output" / "entities"), "contract", mock_config_manager)
    recipient_store = EntityStore(str(TEST_DATA_DIR / "output" / "entities"), "recipient", mock_config_manager)
    contract_data = contract_store.load()
    recipient_data = recipient_store.load()
    for contract in contract_data.values():
        recipient_id = contract["recipient"]["data"]["id"]
        assert recipient_id in recipient_data
        recipient = recipient_data[recipient_id]
        ref_recipient = contract["recipient"]["data"]
        assert recipient["name"] == ref_recipient["name"]

def test_transformation_pipeline(test_data_setup, mock_config_manager):
    """Test data transformation pipeline."""
    assert convert_csv_to_json(mock_config_manager) is True
    contract_store = EntityStore(str(TEST_DATA_DIR / "output" / "entities"), "contract", mock_config_manager)
    contract_data = contract_store.load()
    amounts = [c["amount"] for c in contract_data.values()]
    assert all(isinstance(amount, float) for amount in amounts)
    assert sorted(amounts) == [100000.0, 200000.0, 300000.0]
    for contract in contract_data.values():
        assert "period" in contract
        assert datetime.strptime(contract["period"]["start_date"], "%Y-%m-%d")
        assert datetime.strptime(contract["period"]["end_date"], "%Y-%m-%d")
    recipient_store = EntityStore(str(TEST_DATA_DIR / "output" / "entities"), "recipient", mock_config_manager)
    recipient_data = recipient_store.load()
    zip_codes = [r["address"]["zip"] for r in recipient_data.values()]
    assert all(len(code) == 5 and code.isdigit() for code in zip_codes)