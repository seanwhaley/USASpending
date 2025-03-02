"""Performance tests for batched operations."""
import pytest
import time
import os
import csv
import json
import shutil
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

from usaspending.processor import convert_csv_to_json
from usaspending.entity_store import EntityStore
from usaspending.config import ConfigManager
from usaspending.chunked_writer import ChunkedWriter

# Test data directory setup
PERF_DATA_DIR = Path(__file__).parent / "perf_data"
PERF_DATA_DIR.mkdir(exist_ok=True)

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
            "contract_amount": f"${amount:,.2f}",
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
            "global": {
                "encoding": "utf-8",
                "datetime_format": "%Y-%m-%d %H:%M:%S",
                "processing": {
                    "max_workers": 4,
                    "queue_size": 1000
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
                },
                "formats": {
                    "csv": {
                        "encoding": "utf-8-sig",
                        "delimiter": ",",
                        "quotechar": '"'
                    },
                    "json": {
                        "indent": None,  # Disable pretty printing for performance
                        "ensure_ascii": False
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
def perf_data_setup():
    """Setup and cleanup for performance tests."""
    if PERF_DATA_DIR.exists():
        shutil.rmtree(PERF_DATA_DIR)
    PERF_DATA_DIR.mkdir()
    
    yield
    
    if PERF_DATA_DIR.exists():
        shutil.rmtree(PERF_DATA_DIR)

class TestBatchProcessing:
    """Test batch processing performance."""
    
    def measure_processing_time(self, records: List[Dict[str, str]], config: Dict[str, Any]) -> float:
        """Measure processing time for given records and config."""
        csv_path = PERF_DATA_DIR / "transactions.csv"
        write_test_csv(records, csv_path)
        
        start_time = time.time()
        config_manager = ConfigManager(config)
        success = convert_csv_to_json(config_manager)
        end_time = time.time()
        
        assert success is True
        return end_time - start_time
    
    def test_batch_size_impact(self, perf_data_setup):
        """Test impact of different batch sizes."""
        num_records = 10000
        records = generate_test_data(num_records)
        
        batch_sizes = [100, 500, 1000, 5000]
        timings = {}
        
        for batch_size in batch_sizes:
            config = PerformanceConfig.create(batch_size=batch_size)
            processing_time = self.measure_processing_time(records, config)
            timings[batch_size] = processing_time
            
            # Cleanup between runs
            if (PERF_DATA_DIR / "output").exists():
                shutil.rmtree(PERF_DATA_DIR / "output")
        
        # Verify processing completed
        assert len(timings) == len(batch_sizes)
        
        # Log performance results
        print("\nBatch Size Performance Results:")
        for batch_size, time_taken in timings.items():
            print(f"Batch Size: {batch_size:5d} | Time: {time_taken:.2f}s | Rate: {num_records/time_taken:.0f} records/s")
    
    def test_validation_impact(self, perf_data_setup):
        """Test impact of validation on processing speed."""
        num_records = 5000
        records = generate_test_data(num_records)
        
        # Test with validation
        config_with_validation = PerformanceConfig.create(skip_validation=False)
        time_with_validation = self.measure_processing_time(records, config_with_validation)
        
        if (PERF_DATA_DIR / "output").exists():
            shutil.rmtree(PERF_DATA_DIR / "output")
        
        # Test without validation
        config_without_validation = PerformanceConfig.create(skip_validation=True)
        time_without_validation = self.measure_processing_time(records, config_without_validation)
        
        # Log results
        print("\nValidation Performance Impact:")
        print(f"With Validation    | Time: {time_with_validation:.2f}s | Rate: {num_records/time_with_validation:.0f} records/s")
        print(f"Without Validation | Time: {time_without_validation:.2f}s | Rate: {num_records/time_without_validation:.0f} records/s")
    
    def test_chunk_size_impact(self, perf_data_setup):
        """Test impact of different output chunk sizes."""
        num_records = 20000
        records = generate_test_data(num_records)
        
        chunk_sizes = [1000, 5000, 10000]
        timings = {}
        
        for chunk_size in chunk_sizes:
            config = PerformanceConfig.create(chunk_size=chunk_size)
            processing_time = self.measure_processing_time(records, config)
            timings[chunk_size] = processing_time
            
            # Verify chunk files
            output_dir = PERF_DATA_DIR / "output" / "entities"
            contract_files = list(output_dir.glob("contract_*.json"))
            expected_chunks = -(-num_records // chunk_size)  # Ceiling division
            assert len(contract_files) >= expected_chunks
            
            if output_dir.exists():
                shutil.rmtree(output_dir)
        
        # Log results
        print("\nChunk Size Performance Results:")
        for chunk_size, time_taken in timings.items():
            print(f"Chunk Size: {chunk_size:5d} | Time: {time_taken:.2f}s | Rate: {num_records/time_taken:.0f} records/s")