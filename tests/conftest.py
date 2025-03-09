from unittest.mock import Mock
import pytest
import shutil
import yaml
from pathlib import Path
from enum import Enum

from usaspending.schema_adapters import (
    StringAdapter,
    NumericAdapter,
    DateAdapter,
    CompositeFieldAdapter,
)

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

"""Shared test fixtures and configuration."""
class TestEnum(Enum):
    """Test enum for adapter testing."""
    OPTION_A = "a"
    OPTION_B = "b"

@pytest.fixture
def string_adapter():
    """Create string adapter for testing."""
    return StringAdapter(min_length=2, max_length=5, pattern=r'^[a-z]+$')

@pytest.fixture
def numeric_adapter():
    """Create numeric adapter for testing."""
    return NumericAdapter(min_value=0, max_value=100)

@pytest.fixture
def date_adapter():
    """Create date adapter for testing."""
    return DateAdapter(formats=['%Y-%m-%d', '%d/%m/%Y'])

@pytest.fixture
def composite_adapter():
    """Create composite adapter for testing."""
    return CompositeFieldAdapter('test_field', [str.strip, str.upper])

"""Shared test fixtures and mock classes."""
import pytest
from typing import Dict, Any, Optional, List, Protocol
from unittest.mock import Mock

from usaspending.interfaces import (
    IConfigurationProvider, IValidationMediator, IEntityFactory, 
    IEntityStore, ISchemaAdapter, IFieldValidator, IValidatable
)


class MockConfigProvider(IConfigurationProvider):
    """Mock configuration provider for testing."""
    
    def __init__(self, config: Dict[str, Any]) -> None:
        self._config = config
        self._errors: List[str] = []
    
    def get_config(self, section: Optional[str] = None) -> Dict[str, Any]:
        if not section:
            return self._config
        return self._config.get(section, {})
    
    def get_validation_errors(self) -> List[str]:
        return self._errors.copy()
    
    def validate_config(self) -> bool:
        return True


class MockValidationMediator(IValidationMediator):
    """Mock validation mediator for testing."""
    
    def __init__(self, should_validate: bool = True) -> None:
        self._should_validate = should_validate
        self._errors: List[str] = []
        self._last_context: Optional[Dict[str, Any]] = None
    
    def validate_entity(self, entity_type: str, data: Dict[str, Any]) -> bool:
        if not self._should_validate:
            self._errors.append(f"Entity validation failed for {entity_type}")
            return False
        return True
    
    def validate_field(self, field_name: str, value: Any, entity_type: Optional[str] = None) -> bool:
        self._last_context = {'field': field_name, 'value': value, 'entity_type': entity_type}
        if not self._should_validate:
            self._errors.append(f"Field validation failed for {field_name}")
            return False
        return True
    
    def get_validation_errors(self) -> List[str]:
        return self._errors.copy()


class MockEntityFactory(IEntityFactory):
    """Mock entity factory for testing."""
    
    def __init__(self, should_create: bool = True) -> None:
        self._should_create = should_create
        self._created_entities = {}
        
    def create_entity(self, entity_type: str, data: Dict[str, Any]) -> Optional[Any]:
        if not self._should_create:
            return None
            
        entity = Mock()
        entity.entity_type = entity_type
        entity.data = data
        self._created_entities[entity_type] = entity
        return entity
        
    def get_entity_types(self) -> list[str]:
        return list(self._created_entities.keys())


class MockEntityStore(IEntityStore):
    """Mock entity store for testing."""
    
    def __init__(self, should_save: bool = True) -> None:
        self._should_save = should_save
        self._entities = {}
        
    def save(self, entity_type: str, entity: Any) -> str:
        if not self._should_save:
            return ""
            
        entity_id = f"{entity_type}-{len(self._entities) + 1}"
        self._entities[entity_id] = (entity_type, entity)
        return entity_id
        
    def get(self, entity_type: str, entity_id: str) -> Optional[Any]:
        if (entity_type, entity_id) in self._entities:
            return self._entities[entity_id][1]
        return None
        
    def delete(self, entity_type: str, entity_id: str) -> bool:
        if (entity_type, entity_id) in self._entities:
            del self._entities[entity_id]
            return True
        return False
        
    def list(self, entity_type: str):
        return (entity for _, (t, entity) in self._entities.items() if t == entity_type)
        
    def count(self, entity_type: str) -> int:
        return sum(1 for _, (t, _) in self._entities.items() if t == entity_type)


class MockSchemaAdapter(ISchemaAdapter):
    """Mock schema adapter for testing."""
    
    def __init__(self, should_validate: bool = True) -> None:
        self._should_validate = should_validate
        self._errors: List[str] = []
    
    def validate(self, value: Any, rules: Dict[str, Any],
                validation_context: Optional[Dict[str, Any]] = None) -> bool:
        if not self._should_validate:
            self._errors.append("Validation failed")
            return False
        return True
    
    def transform(self, value: Any) -> Any:
        return value
    
    def get_errors(self) -> List[str]:
        return self._errors


class MockFieldValidator(IFieldValidator):
    """Mock field validator for testing."""
    
    def __init__(self) -> None:
        self.errors: List[str] = []
    
    def validate_field(self, field_name: str, value: Any, 
                      validation_context: Optional[Dict[str, Any]] = None) -> bool:
        if value == 'invalid':
            self.errors.append(f"Invalid value for {field_name}")
            return False
        return True
    
    def get_validation_errors(self) -> List[str]:
        return self.errors


class MockValidatable(IValidatable):
    """Mock validatable entity for testing."""
    
    def __init__(self, should_validate: bool = True) -> None:
        self._should_validate = should_validate
        self._errors: List[str] = []
    
    def validate(self) -> bool:
        if not self._should_validate:
            self._errors.append("Validation failed")
            return False
        return True
    
    def get_validation_errors(self) -> List[str]:
        return self._errors


# Common fixtures
@pytest.fixture
def valid_config() -> Dict[str, Any]:
    """Create valid test configuration."""
    return {
        'validation_types': {
            'string': [
                {'type': 'pattern', 'pattern': '[A-Za-z0-9\\s]+'},
                {'type': 'length', 'min': 1, 'max': 100}
            ],
            'number': [
                {'type': 'range', 'min': 0, 'max': 1000000}
            ],
            'date': [
                {'type': 'date', 'format': '%Y-%m-%d'}
            ],
            'code': [
                {'type': 'pattern', 'pattern': '[A-Z0-9]+'},
                {'type': 'length', 'min': 2, 'max': 10}
            ]
        },
        'field_types': {
            'name': 'string',
            'amount': 'number',
            'code_*': 'string',
            'contract_number': 'code',
            'award_amount': 'number',
            'award_date': 'date',
            'description': 'string',
            'agency_code': 'code',
            'vendor_name': 'string',
            '*_amount': 'number',
            '*_date': 'date'
        },
        'field_dependencies': {
            'end_date': {
                'fields': ['start_date'],
                'validation': {
                    'type': 'date_range',
                    'min_field': 'start_date'
                }
            },
            'sub_amount': {
                'fields': ['total_amount'],
                'validation': {
                    'type': 'range',
                    'max_field': 'total_amount'
                }
            }
        },
        'entities': {
            'test_entity': {
                'field_mappings': {
                    'direct': {
                        'id': 'source_id',
                        'name': 'source_name'
                    }
                }
            },
            'contract': {
                'key_fields': ['contract_number'],
                'required_fields': ['contract_number', 'award_amount', 'award_date'],
                'field_mappings': {
                    'direct': {
                        'id': 'contract_number',
                        'amount': 'award_amount',
                        'date': 'award_date',
                        'description': 'description'
                    }
                }
            },
            'agency': {
                'key_fields': ['agency_code'],
                'required_fields': ['agency_code', 'agency_name'],
                'field_mappings': {
                    'direct': {
                        'id': 'agency_code',
                        'name': 'agency_name'
                    }
                }
            }
        }
    }


@pytest.fixture
def mock_config_provider(valid_config: Dict[str, Any]) -> MockConfigProvider:
    """Create configuration provider mock."""
    return MockConfigProvider(valid_config)


@pytest.fixture
def mock_validation_mediator() -> MockValidationMediator:
    """Create validation mediator mock."""
    return MockValidationMediator()


@pytest.fixture
def mock_entity_factory() -> MockEntityFactory:
    """Create entity factory mock."""
    return MockEntityFactory()


@pytest.fixture
def mock_entity_store() -> MockEntityStore:
    """Create entity store mock."""
    return MockEntityStore()


@pytest.fixture
def mock_field_validator() -> MockFieldValidator:
    """Create field validator mock."""
    return MockFieldValidator()


@pytest.fixture
def mock_schema_adapter() -> MockSchemaAdapter:
    """Create schema adapter mock."""
    return MockSchemaAdapter()