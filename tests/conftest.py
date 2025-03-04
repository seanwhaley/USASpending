from unittest.mock import Mock
import pytest
import shutil
import csv
import yaml
from pathlib import Path
import os

# Test data directory setup
TEST_DATA_DIR = Path(__file__).parent / "data"
TEST_DATA_DIR.mkdir(exist_ok=True)

@pytest.fixture(scope="session")
def test_data_dir():
    """Return the path to the test data directory."""
    return TEST_DATA_DIR

@pytest.fixture(scope="session")
def output_dir(test_data_dir):
    """Create and return the output directory for test data."""
    output_dir = test_data_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    yield output_dir
    # Clean up after all tests
    if output_dir.exists():
        shutil.rmtree(output_dir)

@pytest.fixture(scope="session")
def entities_dir(output_dir):
    """Create and return the entities directory for test data."""
    entities_dir = output_dir / "entities"
    entities_dir.mkdir(parents=True, exist_ok=True)
    return entities_dir

@pytest.fixture(scope="session")
def test_csv_path(test_data_dir, request):
    """Create test data CSV file with comprehensive test cases."""
    csv_data = [
        "contract_id,contract_description,contract_amount,period_of_performance_start,period_of_performance_end,"
        "recipient_id,recipient_name,recipient_address,recipient_city,recipient_state,recipient_zip",
        # Standard valid cases
        "C0001,Test Contract 1,$100000.00,2024-01-01,2024-12-31,R0001,Test Recipient 1,123 Main St,Springfield,IL,62701",
        "C0002,Test Contract 2,$200000.00,2024-02-01,2024-11-30,R0001,Test Recipient 1,123 Main St,Springfield,IL,62701",
        "C0003,Test Contract 3,$300000.00,2024-03-01,2024-10-31,R0002,Test Recipient 2,456 Oak Ave,Chicago,IL,60601",
        # Edge cases
        "C0004,Zero Amount Contract,$0.00,2024-01-01,2024-12-31,R0002,Test Recipient 2,456 Oak Ave,Chicago,IL,60601",
        "C0005,Large Amount,$9999999.99,2024-01-01,2024-12-31,R0003,Test Recipient 3,789 Pine St,Boston,MA,02108",
        # Date edge cases
        "C0006,Same Day Contract,$50000.00,2024-06-01,2024-06-01,R0003,Test Recipient 3,789 Pine St,Boston,MA,02108",
        "C0007,Year End Contract,$75000.00,2024-12-31,2024-12-31,R0001,Test Recipient 1,123 Main St,Springfield,IL,62701"
    ]
    
    # Create test CSV file
    csv_path = test_data_dir / "test_transactions.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        f.write("\n".join(csv_data))
    
    def cleanup():
        """Clean up test file."""
        if csv_path.exists():
            try:
                csv_path.unlink()
            except Exception as e:
                print(f"Failed to clean up test CSV: {e}")
    
    request.addfinalizer(cleanup)
    return csv_path

@pytest.fixture(scope="session")
def create_temp_config_file():
    """Returns a function to create a temporary config file."""
    def _create_file(config_data):
        """Create a temporary config file with the provided data"""
        temp_config_path = TEST_DATA_DIR / "temp_test_config.yaml"
        with open(temp_config_path, 'w') as f:
            yaml.dump(config_data, f)
        return temp_config_path
    return _create_file

@pytest.fixture(scope="session")
def test_config(test_data_dir):
    """Return a comprehensive test configuration."""
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
                "entity_processing": {
                    "enabled": True,
                    "processing_order": 1
                },
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
                "entity_processing": {
                    "enabled": True,
                    "processing_order": 2
                },
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
        },
        "system": {
            # Global processing settings
            "processing": {
                "records_per_chunk": 100,
                "create_index": True,
                "max_chunk_size_mb": 10,
                "entity_save_frequency": 100,
                "incremental_save": True,
                "log_frequency": 50,
                'max_workers': 4,
                'queue_size': 1000
            },
            
            # Input/output settings
            "io": {
                "input": {
                    "file": str(test_data_dir / "test_transactions.csv"),
                    "batch_size": 100,
                    "validate_input": True,
                    "skip_invalid_rows": False,
                    "field_pattern_exceptions": []
                },
                
                "output": {
                    "directory": str(test_data_dir / "output"),
                    "transaction_file": "contracts.json",
                    "entities_subfolder": "entities",
                    "transaction_base_name": "transactions",
                    "indent": 2,
                    "ensure_ascii": False
                }
            },
            'error_handling': {
                'log_errors': True,
                'stop_on_error': False
            }
        },
        "global": {
            "processing": {
                "records_per_chunk": 100,
                "max_chunk_size_mb": 10
            },
            "encoding": "utf-8",
            "datetime_format": "%Y-%m-%d %H:%M:%S",
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

@pytest.fixture(scope="session")
def mock_config_manager(test_config, create_temp_config_file, test_data_dir):
    """Create a mock config manager instance with comprehensive functionality."""
    # Create a real config file
    config_path = create_temp_config_file(test_config)
    
    # Create a mock that behaves like a ConfigManager
    mock_manager = Mock()
    mock_manager.get_config.return_value = test_config
    mock_manager.get_input_file_path.return_value = str(test_data_dir / "test_transactions.csv")
    mock_manager.get_output_directory.return_value = str(test_data_dir / "output")
    
    # Set config attribute
    mock_manager.config = test_config
    mock_manager.config_path = config_path
    
    # Make the mock manager behave like a dict
    mock_manager.items.return_value = test_config.items()
    mock_manager.__iter__ = Mock(return_value=iter(test_config.items()))
    mock_manager.__getitem__ = Mock(side_effect=test_config.__getitem__)
    mock_manager.get = Mock(side_effect=test_config.get)
    
    # Add additional required methods
    mock_manager.get_section = Mock(side_effect=lambda section: test_config.get(section, {}))
    mock_manager.get_system_config = Mock(return_value=test_config["system"])
    mock_manager.get_global_config = Mock(return_value=test_config.get("global", {}))
    mock_manager.get_entity_configs = Mock(return_value=test_config.get("entities", {}))
    
    return mock_manager

@pytest.fixture(scope="session")
def test_data_setup(test_csv_path, output_dir, entities_dir):
    """Setup test data and directories for all tests."""
    return {
        "csv_path": test_csv_path,
        "output_dir": output_dir,
        "entities_dir": entities_dir
    }