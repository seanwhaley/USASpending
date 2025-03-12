"""Configure pytest environment and provide shared test fixtures."""
import os
from pathlib import Path
import pytest
from typing import Dict, Any, Optional, List, Generator, Union, Sequence, Type
from unittest.mock import Mock
from decimal import Decimal

# Core interfaces
from usaspending.core.interfaces import (
    IConfigurationProvider,
    IConfigurable,
    IValidator,
    IValidationService,
    IValidationMediator,
    IEntityFactory,
    IEntityStore,
    IEntityMapper,
    IProcessor,
    ICache,
    ITransformer,
    IRelationshipManager,
    IEntitySerializer
)

# Core types
from usaspending.core.types import (
    EntityData,
    EntityKey,
    ValidationResult,
    ValidationRule,
    TransformationRule,
    ComponentConfig,
    EntityType,
    RuleSet
)

# Core base implementations
from usaspending.core.entity_base import (
    BaseEntityFactory,
    BaseEntityStore,
    BaseEntityMapper,
    BaseEntityMediator
)

# Core adapters
from usaspending.core.adapters import (
    StringAdapter,
    NumericAdapter,
    DateAdapter,
    MoneyAdapter,
    BooleanAdapter,
    EnumAdapter,
    CompositeFieldAdapter
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
    output_dir.mkdir(exist_ok=True)
    return output_dir

@pytest.fixture(scope="session")
def entities_dir(output_dir):
    """Create and return the entities directory for test data."""
    entities_dir = output_dir / "entities"
    entities_dir.mkdir(exist_ok=True)
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
        # Edge cases
        "C0003,Minimum Amount,$1.00,2024-01-01,2024-12-31,R0001,Test Recipient 1,123 Main St,Springfield,IL,62701",
        "C0004,Zero Amount Contract,$0.00,2024-01-01,2024-12-31,R0002,Test Recipient 2,456 Oak Ave,Chicago,IL,60601",
        "C0005,Large Amount,$9999999.99,2024-01-01,2024-12-31,R0003,Test Recipient 3,789 Pine St,Boston,MA,02108"
    ]
    
    csv_path = test_data_dir / "test_transactions.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        f.write("\n".join(csv_data))
    
    def cleanup():
        if csv_path.exists():
            csv_path.unlink()
    request.addfinalizer(cleanup)
    return csv_path

@pytest.fixture(scope="session")
def sample_config() -> Dict[str, Any]:
    """Return a basic test configuration."""
    return {
        'paths': {
            'data': 'data',
            'output': 'output'
        },
        'components': {
            'test_component': {
                'class_path': 'test.MockComponent',
                'settings': {
                    'option1': 'value1'
                }
            }
        },
        'entities': {
            'test_entity': {
                'key_fields': ['id'],
                'field_mappings': {
                    'direct': {
                        'target': 'source'
                    }
                }
            }
        }
    }

# Mock class fixtures
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

@pytest.fixture
def mock_config_provider(sample_config: Dict[str, Any]) -> MockConfigProvider:
    """Create configuration provider mock."""
    return MockConfigProvider(sample_config)

class MockEntityStore(IEntityStore):
    """Mock entity store for testing."""
    def __init__(self, should_save: bool = True) -> None:
        self._should_save = should_save
        self._entities = {}
    
    def save_entity(self, entity_type: EntityType, entity: EntityData) -> str:
        if not self._should_save:
            return ""
        entity_id = f"{entity_type}-{len(self._entities) + 1}"
        self._entities[entity_id] = (str(entity_type), entity)
        return entity_id
    
    def get_entity(self, entity_type: EntityType, entity_id: str) -> Optional[EntityData]:
        if entity_id in self._entities:
            return self._entities[entity_id][1]
        return None
    
    def delete_entity(self, entity_type: EntityType, entity_id: str) -> bool:
        if entity_id in self._entities:
            del self._entities[entity_id]
            return True
        return False
    
    def list_entities(self, entity_type: EntityType) -> Generator[EntityData, None, None]:
        for _, (t, entity) in self._entities.items():
            if t == str(entity_type):
                yield entity
    
    def count_entities(self, entity_type: EntityType) -> int:
        return sum(1 for _, (t, _) in self._entities.items() if t == str(entity_type))
    
    def cleanup(self) -> None:
        self._entities.clear()

@pytest.fixture
def mock_entity_store() -> MockEntityStore:
    """Create entity store mock."""
    return MockEntityStore()

class MockValidator(IValidator):
    """Mock validator for testing."""
    def __init__(self) -> None:
        self._errors: List[str] = []
        self._rules: Dict[str, ValidationRule] = {}
    
    def validate(self, entity_type: str, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> bool:
        return True
    
    def get_validation_errors(self) -> List[str]:
        return self._errors.copy()
    
    def add_validation_rule(self, rule: ValidationRule) -> None:
        self._rules[rule.field_name] = rule
    
    def remove_validation_rule(self, field_name: str, rule_type: str) -> bool:
        if field_name in self._rules:
            del self._rules[field_name]
            return True
        return False

@pytest.fixture
def mock_validator() -> MockValidator:
    """Create validator mock."""
    return MockValidator()

class MockMapper(IEntityMapper):
    """Mock entity mapper for testing."""
    def __init__(self) -> None:
        self._errors: List[str] = []
    
    def map_entity(self, entity_type: EntityType, data: Dict[str, Any]) -> Dict[str, Any]:
        return data
    
    def register_calculation_function(self, name: str, func: Any) -> None:
        pass
    
    def validate(self, entity_type: str, data: Dict[str, Any]) -> bool:
        return True
    
    def get_errors(self) -> List[str]:
        return self._errors.copy()

@pytest.fixture
def mock_mapper() -> MockMapper:
    """Create mapper mock."""
    return MockMapper()

class MockFactory(IEntityFactory):
    """Mock entity factory for testing."""
    def __init__(self) -> None:
        self._entities: Dict[str, Dict[str, Any]] = {}
    
    def create_entity(self, entity_type: EntityType, data: EntityData) -> Optional[EntityData]:
        return data
    
    def register_entity(self, entity_type: EntityType, config: Dict[str, Any]) -> None:
        self._entities[str(entity_type)] = config
    
    def register_type(self, type_name: str, type_class: Type) -> None:
        pass
    
    def get_entity_types(self) -> List[EntityType]:
        return [EntityType(t) for t in self._entities.keys()]

@pytest.fixture
def mock_factory() -> MockFactory:
    """Create factory mock."""
    return MockFactory()

class MockValidationService(IValidationService):
    """Mock validation service for testing."""
    def __init__(self) -> None:
        self._errors: List[str] = []
        self._custom_validators: Dict[str, Any] = {}
    
    def validate_field(self, entity_type: str, field_name: str, value: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        return True
    
    def validate_fields(self, entity_type: str, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        return ValidationResult(is_valid=True, errors=[])
    
    def register_custom_validator(self, name: str, validator: Any) -> None:
        self._custom_validators[name] = validator

    def validate(self, entity_type: str, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> bool:
        return True
    
    def get_validation_errors(self) -> List[str]:
        return self._errors.copy()
    
    def add_validation_rule(self, rule: ValidationRule) -> None:
        pass
    
    def remove_validation_rule(self, field_name: str, rule_type: str) -> bool:
        return True

@pytest.fixture
def mock_validation_service() -> MockValidationService:
    """Create validation service mock."""
    return MockValidationService()

class MockValidationMediator(IValidationMediator):
    """Mock validation mediator for testing."""
    def __init__(self) -> None:
        self._errors: List[str] = []
        self._validators: Dict[str, IValidator] = {}
        self._rules: Dict[str, List[ValidationRule]] = {}
        self._stats: Dict[str, int] = {
            'validated_fields': 0,
            'validation_errors': 0
        }
    
    def validate(self, entity_type: Union[EntityType, str], data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> bool:
        return True
    
    def validate_entity(self, entity_type: str, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> bool:
        return True
    
    def validate_field(self, field_name: str, value: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        return True
    
    def get_validation_errors(self) -> List[str]:
        return self._errors.copy()
    
    def register_validator(self, entity_type: Union[EntityType, str], validator: IValidator) -> None:
        self._validators[str(entity_type)] = validator
    
    def register_rules(self, field_name: str, rules: Sequence[ValidationRule]) -> None:
        self._rules[field_name] = list(rules)
    
    def clear_errors(self) -> None:
        self._errors.clear()
    
    def get_stats(self) -> Dict[str, int]:
        return self._stats.copy()

@pytest.fixture
def mock_validation_mediator() -> MockValidationMediator:
    """Create validation mediator mock."""
    return MockValidationMediator()

class MockProcessor(IProcessor):
    """Mock processor for testing."""
    def __init__(self) -> None:
        self._errors: List[str] = []
        self._stats: Dict[str, int] = {
            'processed': 0,
            'failed': 0,
            'skipped': 0
        }
    
    def process(self, entity_type: EntityType, data: Dict[str, Any]) -> bool:
        self._stats['processed'] += 1
        return True
    
    def process_batch(self, entity_type: EntityType, batch: List[Dict[str, Any]]) -> List[bool]:
        self._stats['processed'] += len(batch)
        return [True] * len(batch)
    
    def get_errors(self) -> List[str]:
        return self._errors.copy()
    
    def get_stats(self) -> Dict[str, int]:
        return self._stats.copy()
    
    def cleanup(self) -> None:
        self._errors.clear()
        self._stats = {
            'processed': 0,
            'failed': 0,
            'skipped': 0
        }

@pytest.fixture
def mock_processor() -> MockProcessor:
    """Create processor mock."""
    return MockProcessor()