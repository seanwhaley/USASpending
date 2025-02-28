"""Test configuration and fixtures for USASpending tests.

This module provides common fixtures and configuration for all tests.
Type checking is enabled for all test files.
"""
from __future__ import annotations

import pytest
from pathlib import Path
import yaml
from typing import Dict, Any

@pytest.fixture
def sample_config() -> Dict[str, Any]:
    """Provide a minimal valid configuration for testing."""
    return {
        "global": {
            "encoding": "utf-8",
            "date_format": "%Y-%m-%d",
            "datetime_format": "%Y-%m-%dT%H:%M:%S"
        },
        "data_dictionary": {
            "input": {
                "file": "test_dictionary.csv",
                "required_columns": [
                    "Element",
                    "Definition"
                ]
            },
            "output": {
                "file": "test_dictionary.json",
                "indent": 2,
                "ensure_ascii": False
            },
            "parsing": {
                "preserve_newlines_for": ["Definition"]
            }
        },
        "contracts": {
            "input": {
                "file": "test_data.csv",
                "batch_size": 1000
            },
            "output": {
                "main_file": "contracts.json",
                "indent": 2,
                "ensure_ascii": False
            },
            "chunking": {
                "enabled": True,
                "records_per_chunk": 10000,
                "create_index": True
            },
            "type_conversion": {
                "date_fields": ["action_date", "last_modified_date"],
                "numeric_fields": ["total_obligation", "base_and_exercised_options_value"],
                "boolean_true_values": ["Y", "YES", "TRUE", "1"],
                "boolean_false_values": ["N", "NO", "FALSE", "0"]
            },
            "entity_separation": {
                "enabled": True,
                "entities": {
                    "recipient": {
                        "key_fields": ["recipient_uei"],
                        "field_mappings": {
                            "recipient_uei": "uei",
                            "recipient_name": "name",
                            "recipient_parent_uei": "parent_uei"
                        }
                    }
                }
            },
            "field_categories": {
                "transaction_info": [
                    "contract_transaction_unique_key",
                    "action_date",
                    "federal_action_obligation"
                ]
            }
        },
        "type_conversion": {
            "date_fields": ["action_date", "period_of_performance_start_date", "period_of_performance_current_end_date"],
            "numeric_fields": ["federal_action_obligation", "base_exercised_options_value", "base_and_all_options_value"],
            "boolean_fields": ["is_fpds"],
            "value_mapping": {
                "true_values": ["true", "yes", "y", "1", "t"],
                "false_values": ["false", "no", "n", "0", "f"]
            },
            "value_validation": {
                "numeric": {
                    "decimal_places": 2,
                    "validation_rules": []
                },
                "date": {
                    "validation_rules": []
                }
            }
        },
        "domain_value_mapping": {
            "action_type": {
                "A": "BPA Call",
                "B": "Purchase Order",
                "C": "Delivery Order"
            }
        },
        "validation_matrix": {
            "code_fields": {
                "rules": {
                    "uei": {
                        "pattern": "^[A-Z0-9]{12}$"
                    }
                }
            }
        },
        "contracts": {
            "chunking": {
                "enabled": True,
                "records_per_chunk": 10000,
                "create_index": True
            },
            "entity_separation": {
                "enabled": True,
                "entities": {
                    "transaction": {
                        "validation_rules": {
                            "required_fields": [
                                {
                                    "field": "action_date",
                                    "rules": [{"type": "required"}]
                                },
                                {
                                    "field": "federal_action_obligation",
                                    "rules": [
                                        {"type": "required"},
                                        {"type": "type", "value": "numeric"},
                                        {"type": "decimal", "precision": 2}
                                    ]
                                }
                            ]
                        }
                    },
                    "recipient": {
                        "validation_rules": {
                            "business_characteristics": {
                                "ownership": {
                                    "rules": [
                                        {
                                            "type": "mutually_exclusive",
                                            "fields": [
                                                "minority_owned_business",
                                                "asian_pacific_american_owned_business",
                                                "black_american_owned_business"
                                            ]
                                        }
                                    ]
                                }
                            }
                        }
                    }
                }
            }
        }
    }

@pytest.fixture
def test_data_dir(tmp_path: Path) -> Path:
    """Create and return a temporary directory for test data."""
    data_dir = tmp_path / "test_data"
    data_dir.mkdir(exist_ok=True)
    return data_dir

@pytest.fixture
def sample_entity_data() -> Dict[str, Any]:
    """Provide sample entity data for testing."""
    return {
        "uei": "TEST123456789",
        "name": "Test Company Inc.",
        "parent_uei": "PARENT987654321"
    }

@pytest.fixture
def sample_csv_data(test_data_dir: Path) -> Path:
    """Create a sample CSV file for testing."""
    csv_file = test_data_dir / "test_data.csv"
    csv_file.write_text(
        "recipient_uei,recipient_name,recipient_parent_uei,action_date,federal_action_obligation\n"
        "TEST123,Test Inc,PARENT456,2024-01-01,1000000.00\n"
    )
    return csv_file