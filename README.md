testing

# USASpending System Architecture

## Tools

```mermaid
classDiagram
    %% Core Utilities
    class BaseReport {
        +output_dir: str
        +__init__(output_dir)
        +save_report(data, filename)
    }
    
    class DirectoryHelper {
        +get_results_subdir(name)
        +ensure_directory(path)
        +list_files(directory, pattern)
    }
    
    class FileHelper {
        +read_file(path)
        +write_file(path, content)
        +json_load(path)
        +json_save(path, data)
    }
    
    class ProjectPathHelper {
        +get_project_root()
        +get_relative_path(path)
    }
    
    %% Coverage Analysis
    class CoverageAnalyzer {
        +coverage_file: str
        +coverage_data: Dict
        +__init__(coverage_file)
        +parse_coverage_xml()
        +generate_report()
    }
    
    class FunctionalCoverageAnalyzer {
        +src_dir: str
        +test_dir: str
        +functions: Dict
        +test_functions: Dict
        +__init__(src_dir, test_dir, output_dir)
        +extract_functions()
        +extract_test_references()
        +calculate_feature_coverage(features)
        +generate_report()
    }
    
    %% Quality Analysis
    class TestQualityAnalyzer {
        +test_dir: str
        +test_files: List
        +test_stats: Dict
        +__init__(test_dir, output_dir)
        +gather_test_files()
        +analyze_test_file(file_path)
        -_analyze_test_function(node, stats)
        -_calculate_quality_score(stats)
        +generate_report()
        -_identify_low_quality_tests()
    }
    
    %% Gap Analysis
    class TestGapAnalyzer {
        +src_dir: str
        +test_dir: str
        +implementation_files: Set
        +test_files: Set
        +__init__(src_dir, test_dir, output_dir)
        +gather_files()
        +analyze_gaps()
        +generate_report()
    }
    
    %% Report Generation (inferred)
    class ReportCombiner {
        +reports: Dict
        +combine_reports()
        +create_summary()
    }
    
    class DashboardGenerator {
        +generate_dashboard()
        +create_visualizations()
    }
    
    %% Inheritance Relationships
    BaseReport <|-- CoverageAnalyzer: inherits
    BaseReport <|-- TestQualityAnalyzer: inherits
    BaseReport <|-- TestGapAnalyzer: inherits
    BaseReport <|-- FunctionalCoverageAnalyzer: inherits
    
    %% Usage Relationships
    BaseReport ..> FileHelper: uses
    BaseReport ..> DirectoryHelper: uses
    DirectoryHelper ..> ProjectPathHelper: uses
    
    ReportCombiner --> CoverageAnalyzer: consumes reports
    ReportCombiner --> TestQualityAnalyzer: consumes reports
    ReportCombiner --> TestGapAnalyzer: consumes reports
    ReportCombiner --> FunctionalCoverageAnalyzer: consumes reports
    
    DashboardGenerator --> ReportCombiner: uses combined data
```

## System Overview

The USASpending system is organized into distinct layers that handle different aspects of data processing and validation.

```mermaid
flowchart TB
    subgraph Entry["Entry Layer"]
        PT[Process Transactions]
    end
    
    subgraph Config["Configuration Layer"]
        CM[Config Management]
        CD[Config Dictionary]
    end
    
    subgraph Core["Core Processing"]
        PR[Processor]
        VS[Validation Service]
        EM[Entity Mapper]
        CP[Component Provider]
    end
    
    subgraph Factory["Factory Layer"]
        EF[Entity Factory]
        CF[Component Factory]
        TF[Transformer Factory]
    end
    
    subgraph Storage["Storage Layer"]
        ES[Entity Store]
        EC[Entity Cache]
        TC[Text Cache]
    end
    
    subgraph TypeSystem["Type System"]
        TD[Type Definition]
        TV[Type Validator]
        BA[Base Adapter]
        SA[Schema Adapter]
    end
    
    Entry --> Config
    Config --> Core
    Core --> Factory
    Factory --> Storage
    Core --> Storage
    Core --> TypeSystem

    style Entry fill:#f9d9d9,stroke:#333,stroke-width:2px
    style Config fill:#d9f9d9,stroke:#333,stroke-width:2px
    style Core fill:#d9d9f9,stroke:#333,stroke-width:2px
    style Factory fill:#e6f9e6,stroke:#333,stroke-width:2px
    style Storage fill:#f9f9d9,stroke:#333,stroke-width:2px
    style TypeSystem fill:#e6e6f9,stroke:#333,stroke-width:2px
```

## Component Dependencies

| Component | Primary Dependencies | Secondary Dependencies | Implements |
|-----------|---------------------|----------------------|------------|
| process_transactions.py | ConfigManager, ValidationService | logging_config, startup_checks | - |
| config_loader.py | config_schema, config_schemas | config_schema_types, config_validation | - |
| config_provider.py | config_loader, config_validation | logging_config, exceptions | - |
| config.py | config_schema, file_utils | logging_config, exceptions | - |
| processor.py | EntityMapper, ValidationService | ConfigManager, EntityFactory, chunked_writer | IDataProcessor |
| entity_mapper.py | validation_base, schema_adapters, schema_mapping | text_file_cache, field_dependencies, exceptions | IEntityMapper |
| validation_service.py | validation_manager, validation_mediator | validation_rules, field_validators | IValidationService |
| validation_manager.py | validation_rules, field_validators | validation_base, exceptions | - |
| validation_mediator.py | validation_manager | field_dependencies, exceptions | IValidationMediator |
| entity_factory.py | entity_serializer, entity_cache | entity_store, exceptions | IEntityFactory |
| entity_store.py | file_utils, entity_cache | serialization_utils, exceptions | IEntityStore |
| entity_mediator.py | entity_factory, entity_mapper | entity_store, exceptions | - |
| chunked_writer.py | file_utils | serialization_utils | - |
| field_selector.py | schema_mapping | field_dependencies | - |
| boolean_adapters.py | schema_adapters | type_definitions | - |
| enum_adapters.py | schema_adapters | type_definitions | - |
| string_adapters.py | schema_adapters | type_definitions | - |
| schema_adapters.py | type_definitions | exceptions | - |
| text_file_cache.py | file_utils | serialization_utils | - |
| entity_cache.py | serialization_utils | file_utils | - |
| entity_serializer.py | serialization_utils | exceptions | - |
| field_validators.py | validation_base | type_definitions | - |
| validator.py | validation_base | field_validators | - |
| component_utils.py | factory | exceptions | - |
| dictionary.py | component_utils | keys, type_definitions | - |
| factory.py | component_utils | exceptions | IFactory |
| keys.py | type_definitions | - | - |

## Validation System

```mermaid
flowchart TD
    subgraph Validation
        VS[Validation Service]
        VM[Validation Manager]
        VE[Validation Engine]
        DM[Dependency Manager]
    end

    subgraph Rules
        VR[Validation Rules]
        SA[Schema Adapters]
        FD[Field Dependencies]
    end

    VS -->|"validate_entity()"| VM
    VM -->|"load_rules()"| VR
    VM -->|"register_adapter()"| SA
    VM -->|"add_dependency()"| FD
    
    VE -->|"validate_record()"| VM
    DM -->|"validate_dependencies()"| VS
    
    style Validation fill:#f9e6e6,stroke:#333,stroke-width:2px
    style Rules fill:#e6f9e6,stroke:#333,stroke-width:2px
```

## Entity Processing Flow

```mermaid
sequenceDiagram
    participant PT as ProcessTransactions
    participant PR as Processor
    participant EM as EntityMapper
    participant VS as ValidationService
    participant ES as EntityStore

    PT->>PR: convert_csv_to_json()
    PR->>EM: map_entity()
    EM->>VS: validate_entity()
    VS-->>EM: validation_result
    
    alt Valid Entity
        EM->>PR: entity_data
        PR->>ES: save()
        ES-->>PR: success
    else Invalid Entity
        VS-->>EM: validation_errors
        EM-->>PR: error
    end
```

## Caching Architecture

```mermaid
flowchart LR
    subgraph Cache Management
        VC[Validation Cache]
        EC[Entity Cache]
    end

    VS[Validation Service] -->|"_cache_validation_result()"| VC
    ES[Entity Store] -->|"cache_entity()"| EC
    
    VC -->|"_generate_cache_key()"| VS
    EC -->|"get_cached_entity()"| ES

    style Cache Management fill:#e6e6f9,stroke:#333,stroke-width:2px
```

## Interface Implementation Details

| Interface | Implementers | Key Methods | Purpose |
|-----------|-------------|-------------|---------|
| IDataProcessor | Processor | process_record(), process_batch() | Coordinate data processing |
| IEntityMapper | EntityMapper | map_entity(), configure() | Transform data to entities |
| IValidationService | ValidationService | validate_entity(), validate_field() | Validate data integrity |
| IEntityStore | EntityStore, FileSystemEntityStore | save(), load(), extract_entity_data() | Persist entity data |
| IDependencyManager | DependencyManager | validate_dependencies(), get_validation_order() | Manage field dependencies |

## Factory Architecture

```mermaid
classDiagram
    class IFactory {
        <<interface>>
        +create(config: Dict) Any
        +register(name: str, creator: Callable)
    }
    
    class BaseFactory {
        <<abstract>>
        -_creators: Dict[str, Callable]
        +create(config: Dict) Any
        +register(name: str, creator: Callable)
        #_validate_config(config: Dict)
    }

    class ComponentFactory {
        -_component_utils: ComponentUtils
        +create_from_config(config: Dict)
        +create_many(configs: List[Dict])
    }

    class EntityFactory {
        -_serializer: EntitySerializer
        -_cache: EntityCache
        +create_entity(data: Dict)
        +register_entity_type(name: str)
    }

    IFactory <|-- BaseFactory
    BaseFactory <|-- ComponentFactory
    BaseFactory <|-- EntityFactory

    note for BaseFactory "Common factory functionality"
    note for ComponentFactory "Dynamic component creation"
    note for EntityFactory "Entity instantiation"
```

## Circular Dependency Prevention

The system employs several strategies to prevent and handle circular dependencies:

```mermaid
flowchart TD
    subgraph Detection
        CD[Circular Detection]
        TO[Topological Ordering]
    end

    VM[Validation Manager] -->|"_check_circular_deps()"| CD
    DM[Dependency Manager] -->|"_get_ordered_fields()"| TO
    
    CD -->|"report error"| VM
    TO -->|"validation order"| DM

    style Detection fill:#f9f9e6,stroke:#333,stroke-width:2px
```

## Validation Inheritance Chain

The validation system follows a hierarchical inheritance pattern from most basic to most specialized:

```mermaid
classDiagram
    class IValidatable {
        <<interface>>
        +validate() bool
        +get_validation_errors() List[str]
    }
    
    class BaseValidatable {
        <<abstract>>
        -_errors: List[str]
        -_is_valid: Optional[bool]
        +validate() bool
        #_perform_validation()* bool
    }

    class IValidator {
        <<interface>>
        +validate_record(record) bool
        +get_validation_errors() List[str]
        +get_validation_stats() Dict
    }

    class BaseValidator {
        <<abstract>>
        +errors: List[str]
        -_validation_cache: Dict
        -_error_history: List
        +add_error()
        +clear_errors()
        +get_error_summary()
    }

    class IValidationService {
        <<interface>>
        +validate_entity() bool
        +validate_field() bool
    }

    class ValidationService {
        -_mediator: IValidationMediator
        -_rules: Dict
        -_dependencies: Dict
        +validate_entity()
        +validate_field()
    }

    IValidatable <|-- BaseValidatable
    IValidator <|-- BaseValidator
    BaseValidator <|-- ValidationService
    IValidationService <|-- ValidationService

    note for BaseValidatable "Starting point for entity validation"
    note for BaseValidator "Core validation functionality"
    note for ValidationService "Full validation implementation"
```

## Validation Data Flow

The validation process follows this sequence:

```mermaid
sequenceDiagram
    participant Data
    participant BV as BaseValidatable
    participant VS as ValidationService
    participant VM as ValidationMediator
    participant Cache

    Data->>BV: validate()
    activate BV
    BV->>BV: _perform_validation()
    BV->>VS: validate_entity()
    
    VS->>Cache: check cache
    alt Cache Hit
        Cache-->>VS: return cached result
    else Cache Miss
        VS->>VM: validate_entity()
        VM->>VM: apply rules
        VM-->>VS: validation result
        VS->>Cache: store result
    end
    
    VS-->>BV: validation result
    BV-->>Data: is_valid
    deactivate BV
```

## Component Utilities Architecture

```mermaid
classDiagram
    class ComponentUtils {
        +create_component(name: str, config: Dict)
        +implements(cls: Type, interface: Type) bool
        +validate_implementation(cls: Type, interface: Type)
    }
    
    class Dictionary {
        -_key_manager: KeyManager
        -_type_validator: TypeValidator
        +get(key: str) Any
        +set(key: str, value: Any)
        +validate() bool
    }

    class KeyManager {
        -_type_definitions: Dict
        +register_key(key: str, type_info: Dict)
        +validate_key(key: str, value: Any)
    }

    Dictionary --> KeyManager
    ComponentUtils --> Dictionary

    note for ComponentUtils "Dynamic component creation and validation"
    note for Dictionary "Type-safe configuration storage"
    note for KeyManager "Key registration and validation"
```

## Configuration System

```mermaid
flowchart TD
    subgraph ConfigCore["Configuration Core"]
        CL[Config Loader]
        CP[Config Provider]
        CV[Config Validator]
    end

    subgraph Schema["Schema Layer"]
        CS[Config Schema]
        CST[Schema Types]
        CSS[Schema Store]
    end

    subgraph Dictionary["Dictionary Layer"]
        DM[Dictionary Manager]
        KM[Key Manager]
        TV[Type Validator]
    end

    CL -->|"load()"| CS
    CS -->|"validate()"| CV
    CP -->|"get_config()"| DM
    
    CS -->|"register_types()"| CST
    CST -->|"store()"| CSS
    
    DM -->|"validate_key()"| KM
    KM -->|"check_type()"| TV
    
    CSS -->|"provide_schema()"| CV

    style ConfigCore fill:#f9d9d9,stroke:#333,stroke-width:2px
    style Schema fill:#d9f9d9,stroke:#333,stroke-width:2px
    style Dictionary fill:#d9d9f9,stroke:#333,stroke-width:2px
```

## Key Management System

```mermaid
classDiagram
    class IKeyManager {
        <<interface>>
        +register_key(key: str, type_info: Dict)
        +validate_key(key: str, value: Any)
        +get_type_info(key: str) Dict
    }
    
    class KeyManager {
        -_type_registry: Dict
        -_validators: Dict
        +register_key(key: str, type_info: Dict)
        +validate_key(key: str, value: Any)
        +get_type_info(key: str) Dict
    }

    class TypeDefinition {
        +name: str
        +validators: List
        +constraints: Dict
        +validate(value: Any) bool
    }

    IKeyManager <|-- KeyManager
    KeyManager --> TypeDefinition

    note for KeyManager "Manages configuration key definitions"
    note for TypeDefinition "Type validation rules"
```

## Transformer System

```mermaid
classDiagram
    class ITransformer {
        <<interface>>
        +transform(data: Any) Any
        +validate_input(data: Any) bool
        +validate_output(result: Any) bool
    }
    
    class BaseTransformer {
        <<abstract>>
        #_type_validator: TypeValidator
        +transform(data: Any) Any
        #_validate_data(data: Any) bool
        #_perform_transform(data: Any)* Any
    }

    class TransformerFactory {
        -_registry: Dict[str, Type]
        +register(name: str, transformer: Type)
        +create(name: str, config: Dict) ITransformer
    }

    class ChainedTransformer {
        -_transformers: List[ITransformer]
        +add_transformer(transformer: ITransformer)
        +transform(data: Any) Any
    }

    ITransformer <|-- BaseTransformer
    BaseTransformer <|-- ChainedTransformer
    TransformerFactory --> ITransformer

    note for BaseTransformer "Base transformation logic"
    note for ChainedTransformer "Sequential transformations"
    note for TransformerFactory "Creates transformer instances"
```

## Data Processing Pipeline

```mermaid
flowchart TD
    subgraph Input["Input Processing"]
        CSV[CSV Reader]
        CW[Chunked Writer]
        FS[Field Selector]
    end
    
    subgraph Transform["Transformation"]
        TF[Transformer Factory]
        CT[Chained Transformer]
        SA[Schema Adapters]
    end
    
    subgraph Validation["Validation"]
        VS[Validation Service]
        VM[Validation Manager]
        VR[Validation Rules]
    end
    
    subgraph Storage["Persistence"]
        ES[Entity Store]
        EC[Entity Cache]
        TC[Text Cache]
    end
    
    CSV -->|"read_batch()"| CW
    CW -->|"process_chunk()"| FS
    FS -->|"select_fields()"| TF
    
    TF -->|"create()"| CT
    CT -->|"transform()"| SA
    SA -->|"adapt()"| VS
    
    VS -->|"validate()"| VM
    VM -->|"apply_rules()"| VR
    VR -->|"validate()"| ES
    
    ES -->|"cache()"| EC
    ES -->|"cache_text()"| TC

    style Input fill:#f9d9d9,stroke:#333,stroke-width:2px
    style Transform fill:#d9f9d9,stroke:#333,stroke-width:2px
    style Validation fill:#d9d9f9,stroke:#333,stroke-width:2px
    style Storage fill:#f9f9f9,stroke:#333,stroke-width:2px
```

## Type System Architecture

```mermaid
classDiagram
    class TypeDefinition {
        +name: str
        +validators: List
        +constraints: Dict
        +validate(value: Any) bool
    }
    
    class TypeValidator {
        -_type_registry: Dict
        +register_type(type_def: TypeDefinition)
        +validate_type(value: Any, type_name: str)
    }

    class BaseAdapter {
        <<abstract>>
        #_type_validator: TypeValidator
        +adapt(value: Any) Any
        #_validate_input(value: Any) bool
        #_validate_output(result: Any) bool
    }

    class SchemaAdapter {
        -_schema: Dict
        -_adapters: Dict[str, BaseAdapter]
        +adapt_record(record: Dict) Dict
        +register_adapter(field: str, adapter: BaseAdapter)
    }

    BaseAdapter <|-- BooleanAdapter
    BaseAdapter <|-- EnumAdapter
    BaseAdapter <|-- StringAdapter
    SchemaAdapter --> BaseAdapter
    TypeValidator --> TypeDefinition

    note for TypeDefinition "Defines type constraints"
    note for TypeValidator "Validates type rules"
    note for BaseAdapter "Core adapter logic"
    note for SchemaAdapter "Schema-based adaptation"
```

## File Update Order

When implementing new validation features, update files in this order:

1. **Base Interfaces** (src/usaspending/interfaces.py):
   - IValidatable (most basic)
   - IValidator
   - IFieldValidator
   - IValidationMediator
   - IValidationService

2. **Base Implementations** (src/usaspending/validation_base.py):
   - BaseValidatable
   - BaseValidator

3. **Validation Components** (src/usaspending/):
   - validation_service.py
   - validation_manager.py
   - field_dependencies.py

4. **Entity-Specific Validation** (src/usaspending/):
   - entity_mapper.py
   - entity_store.py
   - processor.py

## Validation Details by Component

| Component | Base Class | Interfaces | Key Responsibilities |
|-----------|------------|------------|---------------------|
| BaseValidatable | None | IValidatable | Basic validation state, error tracking |
| BaseValidator | None | IValidator | Core validation, caching, stats |
| ValidationService | BaseValidator | IValidationService | Rule application, dependency management |
| ValidationMediator | None | IValidationMediator | Validation coordination, result aggregation |
| EntityMapper | BaseValidatable | IEntityMapper | Entity-specific validation rules |

## Testing Update Order

When adding new validation features, update tests in this order:

1. test_validation_base.py (tests base validation functionality)
2. test_validation_service.py (tests validation service implementation)
3. test_validation_manager.py (tests validation coordination)
4. test_field_dependencies.py (tests dependency handling)
5. test_entity_mapper.py (tests entity-specific validation)

Each test file corresponds to a component in the validation chain and should be updated to maintain complete test coverage of the validation system.

## File Locations

| Component Type | Location | Purpose |
|---------------|----------|----------|
| Entry Points | src/ | Main execution entry points |
| Core Components | src/usaspending/ | Primary system functionality |
| Configuration | / | YAML configuration files |
| Tests | tests/ | Test suite and fixtures |
| Documentation | docs/ | System documentation and analysis |

## Detailed File Interactions

### Core Processing Flow
1. **Entry Point** (`process_transactions.py`)
   - Interacts with `config_loader.py` and `config_provider.py` for configuration management
   - Uses `startup_checks.py` for initial system validation
   - Initializes logging through `logging_config.py`

2. **Configuration Layer**
   - `config_loader.py` → `config_schema.py` → `config_schemas.py` → `config_schema_types.py`
   - `config_validation.py` validates configuration using schema definitions
   - `config_provider.py` manages configuration access throughout the system

3. **Processing Pipeline**
   - `processor.py` orchestrates the data processing flow:
     - Uses `chunked_writer.py` for efficient data handling
     - Coordinates with `entity_mediator.py` for entity management
     - Interacts with `field_selector.py` for data field selection

4. **Entity Management**
   - `entity_mapper.py` transforms data using:
     - `schema_mapping.py` for field mappings
     - `field_dependencies.py` for managing field relationships
     - Multiple adapters (`boolean_adapters.py`, `enum_adapters.py`, `string_adapters.py`)
   - `entity_factory.py` creates entities using:
     - `entity_serializer.py` for data serialization
     - `entity_cache.py` for caching
     - `entity_store.py` for persistence

5. **Validation Chain**
   - `validation_service.py` coordinates validation using:
     - `validation_manager.py` for managing validation rules
     - `validation_mediator.py` for validation flow control
     - `validation_rules.py` for rule definitions
     - `field_validators.py` for field-level validation
   - `validation_base.py` provides core validation functionality
   - `validator.py` implements specific validation logic

6. **Utility Support**
   - `text_file_cache.py` provides caching for file operations
   - `file_utils.py` handles file system operations
   - `serialization_utils.py` manages data serialization
   - `transformers.py` implements data transformations
   - `utils.py` provides general utility functions

### Data Flow Dependencies
- CSV Input → `processor.py` → `entity_mapper.py` → `validation_service.py` → `entity_store.py` → JSON Output
- Configuration: `config_loader.py` → `config_validation.py` → `config_provider.py` → All Components
- Validation: `validation_service.py` → `validation_manager.py` → `validation_mediator.py` → `validator.py`
- Entity Processing: `entity_mapper.py` → `entity_factory.py` → `entity_mediator.py` → `entity_store.py`

### Key Component Interfaces
- `interfaces.py` defines core contracts implemented by:
  - `processor.py` (IDataProcessor)
  - `entity_mapper.py` (IEntityMapper)
  - `validation_service.py` (IValidationService)
  - `entity_store.py` (IEntityStore)
  - `entity_factory.py` (IEntityFactory)

### Type System
- `type_definitions.py` provides core type definitions
- Adapters handle type conversion:
  - `boolean_adapters.py` for boolean values
  - `enum_adapters.py` for enumeration values
  - `string_adapters.py` for string manipulation
  - `schema_adapters.py` for schema-based conversions

### Error Handling
- `exceptions.py` defines system-wide exceptions
- `fallback_messages.py` provides error message templates
- Each component includes specific error handling for its domain
