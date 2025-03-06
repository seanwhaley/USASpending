"""Integration tests for entity processing pipeline and transaction management and chunked writer."""
import pytest
import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
import csv

from usaspending.processor import convert_csv_to_json
from usaspending.entity_store import EntityStore

def test_end_to_end_processing(test_data_setup, mock_config_manager):
    """Test end-to-end processing pipeline using centralized fixtures."""
    entities_dir = test_data_setup["entities_dir"]
    
    # Make sure the entities directory exists
    entities_dir.mkdir(parents=True, exist_ok=True)
    
    assert convert_csv_to_json(mock_config_manager) is True
    
    # Verify output files were created
    assert (test_data_setup["output_dir"] / "contracts.json").exists()
    assert (entities_dir / "contract").exists()
    assert (entities_dir / "recipient").exists()

def test_invalid_data_handling(test_data_setup, mock_config_manager, test_csv_path):
    """Test handling of invalid data."""
    # Add an invalid row to the test CSV
    with open(test_csv_path, "a", newline="", encoding="utf-8") as f:
        f.write("\nC0008,Invalid Contract,invalid_amount,2024-01-01,2024-12-31,R0003,Test Recipient 3,789 Pine St,Boston,MA,invalid_zip")

    # Configure system to skip invalid rows
    mock_config_manager.config["system"]["io"]["input"]["skip_invalid_rows"] = True
    
    # Make sure the entities directory exists
    entities_dir = test_data_setup["entities_dir"]
    entities_dir.mkdir(parents=True, exist_ok=True)

    assert convert_csv_to_json(mock_config_manager) is True
    
    # Reset the skip_invalid_rows flag for other tests
    mock_config_manager.config["system"]["io"]["input"]["skip_invalid_rows"] = False

def test_relationship_integrity(test_data_setup, mock_config_manager):
    """Test entity relationship integrity."""
    entities_dir = test_data_setup["entities_dir"]
    entities_dir.mkdir(parents=True, exist_ok=True)

    assert convert_csv_to_json(mock_config_manager) is True
    
    # Check relationship integrity by loading entities
    entity_store = EntityStore()
    
    # Load contract entities
    contract_file = entities_dir / "contract" / "entities.json"
    assert contract_file.exists()
    
    with open(contract_file, "r") as f:
        contracts = json.load(f)
    
    # Load recipient entities
    recipient_file = entities_dir / "recipient" / "entities.json"
    assert recipient_file.exists()
    
    with open(recipient_file, "r") as f:
        recipients = json.load(f)
    
    # Verify relationships
    for contract in contracts.values():
        if "recipient" in contract and "id" in contract["recipient"]:
            recipient_id = contract["recipient"]["id"]
            assert recipient_id in recipients, f"Recipient {recipient_id} not found in entities"

def test_transformation_pipeline(test_data_setup, mock_config_manager):
    """Test data transformation pipeline."""
    entities_dir = test_data_setup["entities_dir"]
    entities_dir.mkdir(parents=True, exist_ok=True)

    assert convert_csv_to_json(mock_config_manager) is True
    
    # Verify transformations were applied correctly
    contract_file = entities_dir / "contract" / "entities.json"
    with open(contract_file, "r") as f:
        contracts = json.load(f)
    
    # Check numeric transformation (money)
    for contract_id, contract in contracts.items():
        if "amount" in contract:
            assert isinstance(contract["amount"], (int, float)), f"Contract {contract_id} amount not properly transformed to number"
    
    # Check date transformations
    for contract_id, contract in contracts.items():
        if "period" in contract:
            if "start_date" in contract["period"]:
                # The exact format depends on the serialization, but it should be a valid date string
                assert isinstance(contract["period"]["start_date"], str)
            if "end_date" in contract["period"]:
                assert isinstance(contract["period"]["end_date"], str)

def test_incremental_processing(test_data_setup, mock_config_manager):
    """Test incremental processing capability."""
    entities_dir = test_data_setup["entities_dir"]
    entities_dir.mkdir(parents=True, exist_ok=True)
    
    # First processing run
    assert convert_csv_to_json(mock_config_manager) is True
    
    # Get timestamp of first run output
    contract_file = entities_dir / "contract" / "entities.json"
    first_run_time = os.path.getmtime(contract_file)
    
    # Wait a moment to ensure timestamps will differ
    import time
    time.sleep(1)
    
    # Second run with same data
    assert convert_csv_to_json(mock_config_manager) is True
    
    # Get timestamp of second run output
    second_run_time = os.path.getmtime(contract_file)
    
    # Files should be updated even with the same data (incremental_save is True)
    assert second_run_time > first_run_time, "Files not updated in incremental run"

def test_processing_with_different_config(test_data_setup, mock_config_manager):
    """Test processing with modified configuration."""
    entities_dir = test_data_setup["entities_dir"]
    entities_dir.mkdir(parents=True, exist_ok=True)
    
    # Modify configuration to exclude recipient entity
    original_recipient_config = mock_config_manager.config["entities"]["recipient"].copy()
    mock_config_manager.config["entities"]["recipient"]["enabled"] = False
    
    # Process with modified config
    assert convert_csv_to_json(mock_config_manager) is True
    
    # Verify recipient entities were not created
    recipient_dir = entities_dir / "recipient"
    assert not recipient_dir.exists() or not any(recipient_dir.iterdir()), "Recipient entities were created despite being disabled"
    
    # Restore original config for other tests
    mock_config_manager.config["entities"]["recipient"] = original_recipient_config