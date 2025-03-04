"""Performance tests for batched operations."""
import pytest
import time
import os
import csv
import json
import shutil
import yaml
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

from usaspending.processor import convert_csv_to_json
from usaspending.entity_store import EntityStore
from usaspending.config import ConfigManager
from usaspending.chunked_writer import ChunkedWriter
from usaspending.validation import ValidationEngine

# Test data directory setup
PERF_DATA_DIR = Path(__file__).parent / "perf_data"
PERF_DATA_DIR.mkdir(exist_ok=True)

@pytest.fixture
def sample_config():
    """Return a sample configuration for validation testing."""
    return {
        'field_properties': {
            'field1': {'type': 'string'},
            'field2': {'type': 'numeric'}
        }
    }

def create_temp_config_file(config_data):
    """Create a temporary config file with the provided data"""
    temp_config_path = PERF_DATA_DIR / "temp_test_config.yaml"
    with open(temp_config_path, 'w') as f:
        yaml.dump(config_data, f)
    return temp_config_path

def generate_test_data(num_records: int) -> List[Dict[str, str]]:
    """Generate test transaction data."""
    records = []
    recipient_cycle = 20  # Reuse recipients to test deduplication
    
    for i in range(num_records):
        recipient_num = (i % recipient_cycle) + 1
        amount = (i + 1) * 1000
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 12, 31)
        
        record = {
            "contract_id": f"C{i+1:06d}",
            "contract_description": f"Performance Test Contract {i+1}",
            "contract_amount": str(amount),
            "period_of_performance_start": start_date.strftime("%Y-%m-%d"),
            "period_of_performance_end": end_date.strftime("%Y-%m-%d"),
            "recipient_id": f"R{recipient_num:04d}",
            "recipient_name": f"Test Recipient {recipient_num}",
            "recipient_address": f"{recipient_num} Test Street",
            "recipient_city": "Test City",
            "recipient_state": "TX",
            "recipient_zip": f"{75001 + (recipient_num % 100):05d}"
        }
        records.append(record)
    
    return records

def write_test_csv(records: List[Dict[str, str]], file_path: Path) -> None:
    """Write test records to CSV file."""
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        if records:
            writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
            writer.writeheader()
            writer.writerows(records)

class PerformanceConfig:
    """Performance test configuration factory."""
    
    @staticmethod
    def create(
        batch_size: int = 1000,
        chunk_size: int = 5000,
        skip_validation: bool = False
    ) -> Dict[str, Any]:
        """Create test configuration with specified parameters."""
        return {
            "key_fields": ["contract_id", "recipient_id"],
            "field_mappings": {
                "direct": {
                    "contract_id": {"field": "contract_id"},
                    "recipient_id": {"field": "recipient_id"}
                }
            },
            "entity_processing": {
                "enabled": True,
                "processing_order": 1
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
                        }
                    },
                    "entity_processing": {
                        "enabled": True,
                        "processing_order": 1
                    }
                },
                "recipient": {
                    "enabled": True,
                    "key_fields": ["recipient_id"],
                    "field_mappings": {
                        "direct": {
                            "id": {"field": "recipient_id"},
                            "name": {"field": "recipient_name"}
                        }
                    },
                    "entity_processing": {
                        "enabled": True,
                        "processing_order": 2
                    }
                }
            },
            "global": {
                "processing": {
                    "records_per_chunk": chunk_size,
                    "max_chunk_size_mb": 10
                },
                "encoding": "utf-8",
                "datetime_format": "%Y-%m-%d %H:%M:%S",
                "formats": {
                    "csv": {
                        "encoding": "utf-8",
                        "delimiter": ",",
                        "quotechar": '"'
                    },
                    "json": {
                        "indent": None,
                        "ensure_ascii": False
                    }
                }
            },
            "formats": {
                "csv": {
                    "encoding": "utf-8",
                    "delimiter": ",",
                    "quotechar": '"'
                },
                "json": {
                    "indent": None,
                    "ensure_ascii": False
                }
            },
            "error_handling": {
                "log_errors": True,
                "stop_on_error": False,
                "max_errors": 100,
                "error_log_path": str(PERF_DATA_DIR / "errors.log")
            },
            "system": {
                "processing": {
                    "max_workers": 4,
                    "queue_size": 1000,
                    "create_index": True,
                    "entity_save_frequency": 100,
                    "incremental_save": True,
                    "log_frequency": 50,
                    "records_per_chunk": chunk_size  # Added required parameter
                },
                "io": {
                    "input": {
                        "file": str(PERF_DATA_DIR / "transactions.csv"),
                        "batch_size": batch_size,
                        "validate_input": not skip_validation,
                        "skip_invalid_rows": True
                    },
                    "output": {
                        "directory": str(PERF_DATA_DIR / "output"),
                        "entities_subfolder": "entities",
                        "transaction_base_name": "transactions",
                        "chunk_size": chunk_size
                    }
                }
            }
        }

def safe_remove_dir(path: Path) -> None:
    """Safely remove a directory and its contents."""
    if not path.exists():
        return
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            shutil.rmtree(path)
            break
        except (PermissionError, OSError):
            if attempt < max_retries - 1:
                time.sleep(0.1 * (attempt + 1))
            else:
                print(f"Warning: Could not remove directory {path}")

@pytest.fixture(scope="function")
def perf_data_setup():
    """Setup and cleanup for performance tests."""
    try:
        if PERF_DATA_DIR.exists():
            safe_remove_dir(PERF_DATA_DIR)
        PERF_DATA_DIR.mkdir(exist_ok=True)
        (PERF_DATA_DIR / "output" / "entities").mkdir(parents=True)
        
        yield
    finally:
        time.sleep(0.1)  # Allow for file handles to be released
        if PERF_DATA_DIR.exists():
            safe_remove_dir(PERF_DATA_DIR)

class TestBatchSizes:
    """Tests for batch size performance impact."""
    
    @pytest.mark.parametrize("num_records", [1000])
    def test_batch_size_impact(self, perf_data_setup, num_records):
        """Test the impact of different batch sizes on processing performance."""
        # Generate test data
        records = generate_test_data(num_records)
        csv_path = PERF_DATA_DIR / "transactions.csv"
        write_test_csv(records, csv_path)
        
        # Test with various batch sizes
        batch_sizes = [100, 500, 1000]
        processing_times = []
        
        for batch_size in batch_sizes:
            # Create config with specific batch size
            config = PerformanceConfig.create(batch_size=batch_size)
            config_path = create_temp_config_file(config)
            config_manager = ConfigManager(str(config_path))
            
            # Process with current batch size and measure performance
            start_time = time.time()
            convert_csv_to_json(config_manager)
            processing_time = time.time() - start_time
            processing_times.append(processing_time)
            
            # Clean output directory for next run
            output_dir = PERF_DATA_DIR / "output"
            if output_dir.exists():
                safe_remove_dir(output_dir)
            output_dir.mkdir(exist_ok=True)
            (output_dir / "entities").mkdir(exist_ok=True)
        
        # Assert that larger batch sizes are generally more efficient
        # (with some reasonable flexibility for test environment variations)
        for i in range(1, len(processing_times)):
            # Each larger batch size should be no more than 20% slower than the previous
            assert processing_times[i] <= processing_times[i-1] * 1.2, \
                f"Batch size {batch_sizes[i]} should not be significantly slower than {batch_sizes[i-1]}"

class TestValidationPerformance:
    """Tests for validation performance impact."""
    
    @pytest.mark.parametrize("num_records", [1000])
    def test_validation_impact(self, perf_data_setup, num_records):
        """Test the performance impact of data validation during processing."""
        # Generate test data
        records = generate_test_data(num_records)
        csv_path = PERF_DATA_DIR / "transactions.csv"
        write_test_csv(records, csv_path)
        
        # Test with and without validation
        config_with_validation = PerformanceConfig.create(skip_validation=False)
        config_without_validation = PerformanceConfig.create(skip_validation=True)
        
        # Process with validation
        config_path_with = create_temp_config_file(config_with_validation)
        config_manager = ConfigManager(str(config_path_with))
        
        start_time = time.time()
        convert_csv_to_json(config_manager)
        with_validation_time = time.time() - start_time
        
        # Clean output directory
        output_dir = PERF_DATA_DIR / "output"
        if output_dir.exists():
            safe_remove_dir(output_dir)
        output_dir.mkdir(exist_ok=True)
        (output_dir / "entities").mkdir(exist_ok=True)
        
        # Process without validation
        config_path_without = create_temp_config_file(config_without_validation)
        config_manager = ConfigManager(str(config_path_without))
        
        start_time = time.time()
        convert_csv_to_json(config_manager)
        without_validation_time = time.time() - start_time
        
        # Assert that validation adds reasonable overhead (typically 20-100%)
        validation_overhead = (with_validation_time / without_validation_time) - 1
        assert validation_overhead <= 1.0, \
            f"Validation overhead should be reasonable (currently {validation_overhead*100:.1f}%)"

class TestChunkingPerformance:
    """Tests for chunk size performance impact."""
    
    @pytest.mark.parametrize("num_records", [5000])
    def test_chunk_size_impact(self, perf_data_setup, num_records):
        """Test how different chunk sizes affect processing performance and memory usage."""
        # Generate larger test data set
        records = generate_test_data(num_records)
        csv_path = PERF_DATA_DIR / "transactions.csv"
        write_test_csv(records, csv_path)
        
        # Test with various chunk sizes
        chunk_sizes = [100, 1000, 5000]
        processing_times = []
        
        for chunk_size in chunk_sizes:
            # Create config with specific chunk size
            config = PerformanceConfig.create(chunk_size=chunk_size)
            config_path = create_temp_config_file(config)
            config_manager = ConfigManager(str(config_path))
            
            # Process with current chunk size and measure performance
            start_time = time.time()
            convert_csv_to_json(config_manager)
            processing_time = time.time() - start_time
            processing_times.append(processing_time)
            
            # Clean output directory for next run
            output_dir = PERF_DATA_DIR / "output"
            if output_dir.exists():
                safe_remove_dir(output_dir)
            output_dir.mkdir(exist_ok=True)
            (output_dir / "entities").mkdir(exist_ok=True)
        
        # Check for optimal chunk size (medium is often best)
        # The smallest and largest chunk sizes are typically less efficient
        assert processing_times[1] <= processing_times[0] * 1.2, \
            "Medium chunk size should not be significantly slower than small chunk size"
        
        # Very large chunks might not always be more efficient due to memory constraints
        # So we use a more permissive assertion here
        assert processing_times[2] <= processing_times[1] * 1.5, \
            "Large chunk size should not be dramatically slower than medium chunk size"

class TestEntityStorePerformance:
    """Tests for entity store performance."""
    
    @pytest.mark.parametrize("num_records,entity_save_frequency", [
        (1000, 100), 
        (1000, 500)
    ])
    def test_entity_save_frequency(self, perf_data_setup, num_records, entity_save_frequency):
        """Test the impact of entity save frequency on performance."""
        # Generate test data
        records = generate_test_data(num_records)
        csv_path = PERF_DATA_DIR / "transactions.csv"
        write_test_csv(records, csv_path)
        
        # Create configuration with specified save frequency
        config = PerformanceConfig.create()
        config["system"]["processing"]["entity_save_frequency"] = entity_save_frequency
        
        # Set up config and process
        config_path = create_temp_config_file(config)
        config_manager = ConfigManager(str(config_path))
        
        start_time = time.time()
        convert_csv_to_json(config_manager)
        processing_time = time.time() - start_time
        
        # We're not making assertions here, just collecting performance data
        print(f"Entity save frequency {entity_save_frequency}: {processing_time:.3f} seconds")

@pytest.mark.parametrize("num_records", [1000])
def test_validation_impact_basic(sample_config, num_records):
    """Test the performance impact of validation."""
    engine = ValidationEngine(sample_config)
    record = {'field1': 'value1', 'field2': 123}
    entity_stores = {}  # Provide an empty entity_stores dictionary
    
    # Measure processing time without validation
    start_time = time.time()
    for _ in range(num_records):
        pass  # Simulate processing without validation
    no_validation_time = time.time() - start_time
    
    # Measure processing time with validation
    start_time = time.time()
    for _ in range(num_records):
        engine.validate_record(record, entity_stores)
    validation_time = time.time() - start_time
    
    # Calculate validation overhead
    overhead = validation_time / no_validation_time
    assert overhead <= 2.0, f"Validation overhead should be reasonable (currently {overhead:.1f}x)"