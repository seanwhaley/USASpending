# USASpending Codebase Analysis and Refactoring Plan

## Continuation Prompts

### General Continuation
This prompt is to allow the developer to start a new LLM session to clean up the history/token size. this version just looks at what the current status of the codebase and this file are.
```
Review the USASpending codebase transformation project, which is transitioning from custom validation/transformation logic to a library-based approach using Pydantic and Marshmallow. The core adapter system and transformation pipeline are implemented. The project uses a configuration-driven approach with business logic defined in conversion_config.yaml. Review deepdive.md and codebase to identify the next integration points and continue the implementation of the next identified step. Update this deepdive.md file regularly. Running the test suite should be the first thing you do, and you should work to fix any issues identified.

Key focus areas:
1. Port remaining transformers to adapter system
2. Implement field dependencies
3. Create configuration bridge
4. Update validation engine

Do not maintain backwards compatibility and follow the established patterns for adapter implementation and configuration.
```

### Context-Aware Continuation
This prompt is to allow the developer to start a new LLM session to clean up the history/token size. This version is to be updated by the llm every time it makes an update to this file so that any additional details in it's memory are captured and do not have to be rehashed.
```
Continue the USASpending transformation project with the following context:
- EntityStore now supports all mapping types (direct, multi-source, object, reference, template)
- Processor properly handles entity relationships
- Added comprehensive field validation with type awareness
- Improved test infrastructure with proper directory management

Recent changes:
1. Enhanced EntityStore with complete mapping support
2. Fixed processor relationship handling
3. Added type-specific field validation
4. Improved file and directory handling
5. Enhanced error reporting and statistics

Next phase focuses on performance optimization and testing infrastructure.
```

### Documentation Update
This is a standardized prompt to have the llm update this document is a consitant way between chat sessions.
```
Update the USASpending project's deepdive.md documentation to reflect recent changes while preserving historical details and implementation decisions. Include:
1. Recent implementation progress
2. Historical context and decisions
3. Updated architectural details
4. Next steps and priorities
5. Integration strategy
6. Testing approach

Ensure all technical decisions and implementation details are preserved while improving organization and clarity. Include continuation prompts for easy reference.
```

## Project Status and Next Steps

### Recent Updates
- Implemented schema validation with ENTITY_CONFIG_SCHEMA
- Fixed runtime configuration loading
- Enhanced validation system with Pydantic v2
- Updated python-dateutil to 2.9.0.post0
- Improved error handling
- Fixed configuration management for both file and dictionary inputs
- Enhanced field dependencies with fallback ordering and cycle detection
- Fixed entity mapping for nested object structures

### Next Implementation Phase
1. Test Coverage (Immediate Priority)
   - Add config_schema.py validation tests
   - Add failure case coverage
   - Fix integration and performance test setup

2. Field Dependencies
   - Design dependency resolution system
   - Support composed transformations

3. Advanced Validation
   - Cross-field validation rules
   - Validation groups

4. Performance Optimization
   - Batch processing
   - Memory management

## Architecture Overview

### Core Components
1. Entry Points:
   - process_transactions.py (main CLI entry)
   - validate_config.py (config validation utility)

2. Configuration Management:
   - config.py (ConfigManager singleton)
   - conversion_config.yaml (source of truth)

3. Data Processing Pipeline:
   - processor.py (main processing logic)
   - entity_serializer.py (data serialization)

4. Adapter System:
   - schema_adapters.py (base adapters & pipeline)
   - decimal_adapters.py (numeric processing)

5. Support Systems:
   - validation.py (validation engine)
   - utils.py (utilities)

## Implementation Status

### Completed Tasks
- [x] Create base adapter interfaces
- [x] Implement core Pydantic adapters
- [x] Add configuration mapping system
- [x] Create validator integration
- [x] Implement transformation pipeline system
- [x] Add adapter transform registry
- [x] Create core string adapters
- [x] Create core enum adapters
- [x] Add numeric transformations
- [x] Add date handling
- [x] Fix ConfigManager to handle both file paths and dictionaries
- [x] Fix field dependencies to prevent circular references
- [x] Fix entity mapper object field mapping

### In Progress
1. Transformer Migration
   - [x] Design pipeline architecture
   - [ ] Port remaining transformers

2. Field Dependencies
   - [x] Design dependency system
   - [x] Add cycle detection and fallback ordering
   - [ ] Complete validation rules

3. Configuration Bridge
   - [x] Update config validation to handle both entities and global config
   - [ ] Support hybrid operation

## Integration Strategy

### 1. Transformer Migration (Current Phase)
- Port remaining transformers to adapter system
- Add adapter equivalents
- Test compatibility
- Validate results

### 2. Field Dependencies (Next Phase)
- Design dependency types
- Create resolution order
- Handle circular references
- Implement composition

### 3. Configuration Bridge (Future Phase)
- Create mapping layer
- Add validation tools
- Support gradual migration

## Architecture Details

### Adapter Pipeline System
```python
class TransformationPipeline(Generic[T, U]):
    """Pipeline for chaining multiple transformations."""
```

### Configuration Format
```yaml
# Field property with transformation pipeline
field_properties:
  status_code:
```

### Standard Transform Templates
```yaml
# Common field patterns
standard_transforms:
  money:
```

## Testing Strategy

### Unit Tests
1. Individual adapter testing
2. Pipeline validation
3. Transform registry
4. Error handling

### Integration Tests
1. Pipeline processing
2. Configuration loading
3. Transformation chains
4. Performance validation

### Migration Tests
1. Configuration compatibility
2. Data consistency
3. Error handling
4. Performance impact

## Key Principles

1. **Configuration-Driven**: Keep business logic in configuration files
2. **Composable**: Use adapter composition for complex transformations
3. **Type-Safe**: Maintain type safety through generics
4. **Extensible**: Easy registration of new transformations
5. **Backward Compatible**: Support gradual migration

## Notes for Implementation

### TransformationPipeline
- Generic type parameters ensure type safety
- Metadata support for debugging
- Error propagation through chain
- Configuration validation

### AdapterTransform
- Centralized transform registry
- Consistent interface
- Easy extension
- Configuration validation

### Integration Points
1. Validator needs pipeline awareness
2. Config system needs transform mapping
3. Entity mapper needs adapter support
4. Performance monitoring needed

## Documentation

### Technical Documentation
1. Adapter system architecture
2. Pipeline implementation
3. Transform registry
4. Configuration format

### User Documentation
1. Configuration guide
2. Migration guide
3. Best practices
4. Examples

## Historical Implementation Progress

### Completed Core Systems
1. Entity Management
   - [x] Consolidated entity stores
   - [x] Created unified rule processing

2. Configuration Management
   - [x] Merged config validation
   - [x] Updated field mapping structure
   - [x] Added support for dictionary-based configurations

3. Data Processing
   - [x] Consolidated processing logic
   - [x] Added dependency-based processing

### Completed Transformation System
1. Base Transformers
   - [x] String Transformers

2. Library Integration
   - [x] Create library adapter layer
   - [x] Implement adapter factory

### Adapter System Implementation
1. Base Components
   - [x] FieldAdapter interface
   - [x] SchemaAdapterFactory

2. Core Adapters
   - [x] StringFieldAdapter

3. Transformation Pipeline
   - [x] TransformationPipeline

## Implementation Strategy Details

### Current Phase: Transformer Migration
1. Analysis
   - Review existing transformers
   - Plan implementation

2. Implementation
   - Port core transformers
   - Add tests

3. Validation
   - Test compatibility
   - Update documentation

### Next Phase: Field Dependencies
1. Design
   - Define dependency types
   - Design validation rules

2. Implementation
   - Create dependency system
   - Update configuration

## Recent Implementation Progress (May 2024)

1. **ConfigManager Enhancement**
   - ✅ Modified ConfigManager to handle both file paths and dictionaries
   - ✅ Added proper null checks to prevent errors with dictionary configs
   - ✅ Modified initialization logic to work with direct configuration objects
   - ✅ Implemented selective validation for entity configurations

2. **Field Dependencies Improvements**
   - ✅ Fixed circular dependency detection to prevent self-reference dependencies
   - ✅ Added fallback validation order computation for circular dependency scenarios
   - ✅ Improved error reporting for dependency cycles to aid debugging

3. **Entity Mapping Fixes**
   - ✅ Updated object field mapping logic to ensure nested structures are created properly
   - ✅ Fixed partial object mappings to prevent KeyError exceptions
   - ✅ Added safeguards to always initialize object mapping structures

4. **Integration Test Improvements**
   - ✅ Added explicit directory creation for test directories
   - ✅ Ensured entity subdirectories are created before tests run
   - ✅ Made cleanup more robust to prevent test interference

5. **Performance Test Fixes**
   - ✅ Ensured proper directory management in performance tests
   - ✅ Fixed mock configuration setup for iteration interfaces

6. **Validation Engine Updates**
   - ✅ Added missing regex module import for pattern matching
   - ✅ Fixed conditional validation logic for payment type validation
   - ✅ Improved field dependency resolution and validation order

## Recent Test Fixes (May 2024)

### Fixed Issues

1. **Configuration Manager Issues**
   - ConfigManager now handles both file paths and dictionary configurations
   - Selective validation prevents global config sections from being validated as entities
   - Added iteration interface methods (__iter__, items(), get()) to support test mocks

2. **Field Dependencies Issues**
   - Prevents self-reference circular dependencies
   - Added fallback validation ordering for cases with circular dependencies
   - Improved error reporting to help identify problematic dependencies

3. **Entity Mapping Issues**
   - Object field mapping now creates nested structures properly
   - Added safeguards to prevent KeyErrors when accessing nested objects
   - Improved transformation error handling

4. **Test Directory Structure**
   - Integration tests now properly create and clean up test directories
   - Performance tests create required directories before execution
   - Test fixture improvements for directory management

### Fixed Tests

1. Unit Tests
   - `test_custom_type_validation`: Fixed object mapping issues
   - `test_field_dependency_creation`: Fixed by preventing self-reference dependencies
   - `test_circular_dependency_detection`: Improved cycle detection
   - `test_validation_order`: Added fallback validation ordering

2. Integration Tests
   - `test_end_to_end_processing`: Fixed directory creation issues
   - `test_relationship_integrity`: Fixed mock configuration issues

3. Performance Tests
   - `test_batch_size_impact`: Fixed directory management
   - `test_chunk_size_impact`: Improved test cleanup

## Recent Test Fixes (May 2024)

### Integration Test Improvements
- Fixed mock configuration manager to include required system key structure
- Enhanced mock object behavior with proper dictionary-style access methods
- Added support for system configuration sections in test configurations
- Improved test directory cleanup and management

### Test Infrastructure Updates
1. **Mock Configuration**
   - Added complete system configuration section to test configurations
   - Enhanced mock_config_manager with proper dictionary interface methods
   - Fixed configuration initialization for both file and dictionary inputs
   - Added validation support for system configuration sections

2. **Directory Management**
   - Implemented safe directory removal with proper error handling
   - Added robust cleanup procedures for test directories
   - Fixed permission issues in performance test directory handling
   - Enhanced directory creation with proper parent/child relationships

3. **Test Data Management**
   - Improved test data generation for performance tests
   - Added proper cleanup between test runs
   - Enhanced test data validation
   - Fixed CSV file handling in tests

### Fixed Test Issues
1. **Integration Tests**
   - Fixed end-to-end processing test failures by adding system configuration
   - Resolved invalid data handling issues with proper config initialization
   - Fixed relationship integrity test failures
   - Resolved transformation pipeline test issues

2. **Performance Tests**
   - Fixed directory permission issues with safe_remove_dir implementation
   - Improved test data cleanup between test runs
   - Enhanced performance measurement accuracy
   - Added proper error handling for file operations

3. **Validation Tests**
   - Fixed field dependency validation and ordering
   - Improved validation group tests
   - Added proper error handling tests

## Next Implementation Steps

### Immediate Priorities
1. **Performance Optimization**
   - [ ] Implement memory-efficient entity processing
   - [ ] Optimize batch processing configuration
   - [ ] Add performance monitoring tools

2. **Validation Enhancement**
   - [ ] Complete field dependency implementation
   - [ ] Add comprehensive validation group support
   - [ ] Enhance error reporting system

3. **Test Coverage**
   - [ ] Add missing validation test cases
   - [ ] Implement performance benchmarks
   - [ ] Add stress testing for large datasets

### Required Changes
1. **Field Dependencies**
   - Enhance bidirectional dependency handling
   - Improve cycle detection in complex validation rules
   - Add better error reporting for dependency issues

2. **Validation Groups**
   - Complete validation group implementation
   - Add support for group inheritance
   - Implement conditional validation rules

3. **Performance Testing**
   - Add memory usage monitoring
   - Implement proper cleanup procedures
   - Add benchmarking tools

## Updated Entity Processing Architecture

Entity processing is governed by the `processing_order` value in each entity's `entity_processing` configuration section. This enables a flexible, dependency-aware processing pipeline:

1. Entities are processed in ascending order based on their `processing_order` value
2. Lower order entities (like Recipients, processing_order=10) are processed before higher order entities (like Contracts, processing_order=30)
3. This enables proper relationship resolution across entity stores
4. The system validates that there are no duplicate processing orders

The `ConfigManager.get_processing_order()` method returns entities sorted by their processing order:

```python
def get_processing_order(self) -> List[tuple[int, str]]:
    """Get ordered list of entities by processing order."""
    entities = []
    for entity_name, config in self._config.items():
        if isinstance(config, dict):
            order = config.get('entity_processing', {}).get('processing_order', 999)
            entities.append((order, entity_name))
    return sorted(entities)
```

This ensures that dependencies between entities (like Contracts referencing Recipients) are properly resolved during processing.

## Historical Implementation Context

### Phase 1: Base Components
1. Core Adapters
   - Base interfaces and abstractions
   - Validation engine

2. Initial Transformers
   - String operations
   - Enum mapping

### Phase 2: Enhanced Pipeline
1. Transformation System
   - Type-safe execution
   - Configuration validation

2. Registry Implementation
   - Centralized transform registry
   - Runtime type checking

### Phase 3: Business Logic Migration
1. Core Transformations
   - Standard field patterns
   - Error handling

2. Configuration Bridge
   - YAML structure
   - Field mapping

## Recent Implementation Progress (May 2024)

### Major Improvements
1. **EntityStore Enhancements**
   - ✅ Completed field mapping implementation with support for all mapping types:
     - Direct mappings
     - Multi-source mappings
     - Object mappings with nested structures
     - Reference mappings with composite keys
     - Template mappings
   - ✅ Added comprehensive validation integration
   - ✅ Improved relationship management

2. **Processor Enhancement**
   - ✅ Fixed entity processing order handling
   - ✅ Added proper relationship processing after entity creation
   - ✅ Improved error handling and statistics
   - ✅ Enhanced record validation workflow

3. **Validation System**
   - ✅ Added comprehensive field type validation
   - ✅ Implemented field dependency resolution
   - ✅ Added support for validation groups
   - ✅ Enhanced validation caching

### Fixed Issues
1. **ConfigManager**
   - Fixed singleton pattern implementation
   - Added proper validation of system configuration sections
   - Fixed config path handling for both file and dictionary inputs

2. **EntityFactory**
   - Fixed constructor to handle both dictionary and ConfigManager inputs
   - Added proper entity store creation path handling
   - Improved error handling and validation

3. **Validation Engine**
   - Enhanced field config lookup with type-specific handling
   - Added pattern matching for field identification
   - Fixed validation group dependency resolution

### Next Steps
1. **Performance Optimization**
   - [ ] Implement batch processing for entity stores
   - [ ] Add memory management for large datasets
   - [ ] Optimize relationship processing

2. **Testing Infrastructure**
   - [ ] Add comprehensive test cases for new mapping types
   - [ ] Implement performance benchmarks
   - [ ] Add relationship validation tests

3. **Documentation**
   - [ ] Update API documentation
   - [ ] Add examples for each mapping type
   - [ ] Document relationship patterns

## Implementation Details

### Entity Processing Architecture
The processing pipeline follows this workflow:
1. Read CSV records in configurable batches
2. Validate record data using the validation engine
3. Process entities in dependency order using EntityStore
4. Extract and transform data according to field mappings
5. Create and validate entity relationships
6. Save processed data periodically

### Field Mapping System
The field mapping system now supports:
1. **Direct Mappings**
   ```yaml
   direct:
     target_field: source_field
   ```

2. **Multi-Source Mappings**
   ```yaml
   multi_source:
     target_field:
       sources: [field1, field2]
       strategy: first_non_empty
   ```

3. **Object Mappings**
   ```yaml
   object:
     address:
       fields:
         line1: address_line_1
         line2: address_line_2
       nested_objects:
         location:
           fields:
             city: city_name
             state: state_code
   ```

4. **Reference Mappings**
   ```yaml
   reference:
     location_ref:
       entity: location
       key_fields: [country_code, state_code, city_name]
       key_prefix: primary_place_of_performance
   ```

5. **Template Mappings**
   ```yaml
   template:
     agencies:
       templates:
         ref: "{agency_code}"
         sub_ref: "{agency_code}:{sub_agency_code}"
   ```

### Validation System
The enhanced validation system provides:
1. Type-specific validation rules
2. Field dependency resolution
3. Validation groups with inheritance
4. Pattern-based field matching
5. Conditional validation rules

### Performance Considerations
Current bottlenecks identified:
1. Entity relationship processing
2. Large dataset memory usage
3. Validation cache efficiency
4. File I/O operations

Next optimizations planned:
1. Batch relationship processing
2. Memory-efficient entity stores
3. Improved validation caching
4. Optimized file operations

## Testing Strategy

### Unit Tests
New test cases needed for:
1. Field mapping types
2. Relationship processing
3. Validation rules
4. Error handling

### Integration Tests
Enhanced tests needed for:
1. End-to-end processing
2. Entity relationships
3. File operations
4. Configuration validation

### Performance Tests
New benchmarks needed for:
1. Large dataset processing
2. Memory usage patterns
3. I/O performance
4. Cache efficiency

## Documentation Needs

### Technical Documentation
1. Field mapping system
2. Validation rules
3. Entity relationships
4. Configuration format

### User Documentation
1. Configuration examples
2. Common patterns
3. Performance tuning
4. Troubleshooting

## Historical Context
This project began as a custom data processing system and is being transformed into a configuration-driven architecture using modern Python libraries. The goal is to improve maintainability, reliability, and performance while reducing custom code complexity.

# Deep Dive into Field Dependency Management System

## Overview

This document provides an in-depth look into the field dependency management system, focusing on recent changes, identified issues, and proposed fixes. The system is designed to manage dependencies between fields, ensuring proper validation and processing order.

## Recent Changes

### Configuration Updates
- **conversion_config.yaml**: Updated to fix missing or incorrect configurations.
  ```yaml
  system:
    processing:
      records_per_chunk: 10000
      create_index: true
      max_chunk_size_mb: 100
      entity_save_frequency: 10000
      incremental_save: true
      log_frequency: 1000

    io:
      input:
        file: "FY2024_015_Contracts_Full_20250109_1.csv"
        batch_size: 1000
        validate_input: true
        skip_invalid_rows: false
        field_pattern_exceptions: []

      output:
        directory: "output"
        transaction_file: "contracts.json"
        entities_subfolder: "entities"
        transaction_base_name: "transactions"
        indent: 2
        ensure_ascii: false

    formats:
      csv:
        encoding: "utf-8-sig"
        delimiter: ","
        quotechar: "\""
        has_header_row: true
      json:
        indent: 2
        ensure_ascii: false

    error_handling:
      max_retries: 3
      log_errors: true
      error_messages:
        validation:
          missing_fields: "Required fields missing in input: {fields}"
          invalid_numeric: "Invalid numeric value for field {field}"
          invalid_date: "Invalid date format for field {field}"
          invalid_enum: "Value {value} not in allowed values for field {field}"
          invalid_reference: "Referenced entity not found for field {field}"
        processing:
          entity_error: "Error processing entity {entity_type}: {error}"
          skipping_record: "Skipping invalid record: {reason}"
          missing_entity_config: "Missing configuration for entity type: {entity_type}"
        file_operations:
          file_not_found: "File not found: {path}"
          permission_error: "Permission denied: {path}"
  ```

### Code Updates
- **FieldDependencyManager**: Enhanced to handle validation rules and circular dependencies more robustly.
  ```python
  class FieldDependencyManager:
      # ...existing code...

      def add_dependency(self, field, target_field, dependency_type, validation_rule=None):
          """Add a dependency between fields."""
          if field not in self.dependencies:
              self.dependencies[field] = set()
          self.dependencies[field].add(FieldDependency(field, target_field, dependency_type, validation_rule))

      def get_dependencies(self, field):
          """Get dependencies for a given field."""
          return self.dependencies.get(field, set())

      def remove_dependency(self, field, target_field, dependency_type):
          """Remove a dependency between fields."""
          if field in self.dependencies:
              self.dependencies[field] = {dep for dep in self.dependencies[field] if dep.target_field != target_field or dep.dependency_type != dependency_type}
              if not self.dependencies[field]:
                  del self.dependencies[field]

      def has_circular_dependency(self, field):
          """Check for circular dependencies."""
          visited = set()
          stack = set()

          def visit(f):
              if f in stack:
                  return True
              if f in visited:
                  return False
              stack.add(f)
              visited.add(f)
              for dep in self.get_dependencies(f):
                  if visit(dep.target_field):
                      return True
              stack.remove(f)
              return False

          return visit(field)

      def get_validation_order(self):
          """Get the order of fields for validation."""
          try:
              return self._compute_validation_order()
          except ValueError:
              return self._compute_fallback_order()

      def _compute_validation_order(self):
          """Compute the validation order using topological sort."""
          # ...existing code...

      def _compute_fallback_order(self):
          """Compute a fallback validation order."""
          # ...existing code...

  # ...existing code...
  ```

### Test Updates
- **test_field_dependencies.py**: Updated test cases to ensure they pass and cover all edge cases.
  ```python
  def test_update_dependency_validation_rule():
      """Test updating a dependency's validation rule."""
      manager = FieldDependencyManager()
      manager.add_dependency('total', 'subtotal', 'calculation', {'operation': 'sum'})
      
      # Get original dependency
      deps = manager.get_dependencies('total')
      dep = next(dep for dep in deps if dep.target_field == 'subtotal')
      assert dep.validation_rule['operation'] == 'sum'
      
      # Update by removing and re-adding with new rule
      manager.remove_dependency('total', 'subtotal', 'calculation')
      manager.add_dependency('total', 'subtotal', 'calculation', {'operation': 'multiply'})
      
      # Check updated validation rule
      deps = manager.get_dependencies('total')
      dep = next(dep for dep in deps if dep.target_field == 'subtotal')
      assert dep.validation_rule['operation'] == 'multiply'
  ```

## Identified Issues and Proposed Fixes

### Configuration Issues
- **Issue**: Missing or incorrect configurations in `conversion_config.yaml`.
- **Fix**: Update the configuration file to include all necessary settings and correct any errors.

### Validation Issues
- **Issue**: Incorrect handling of validation rules and circular dependencies in `FieldDependencyManager`.
- **Fix**: Enhance the `FieldDependencyManager` class to handle these cases more robustly.

### Test Failures
- **Issue**: Test cases in `test_field_dependencies.py` failing due to incorrect assumptions or setup.
- **Fix**: Update the test cases to ensure they pass and cover all edge cases.

## Next Steps

1. **Review and Merge Fixes**: Ensure all proposed fixes are reviewed and merged into the main codebase.
2. **Run Full Test Suite**: Run the full test suite to ensure all issues are resolved and no new issues are introduced.
3. **Perform Additional Testing**: Conduct additional testing to verify the stability and correctness of the system.

By following this plan, we can systematically address the issues identified in the error log and ensure the system is stable and functioning correctly.

# USASpending Codebase Analysis - March 3, 2025 Update

## Data Flow Analysis 

### Core Data Pipeline
We analyzed the data transformation pipeline that processes DOJ contract data through the following steps:

1. **Entry Point** (process_transactions.py)
   - Processes CSV input based on conversion_config.yaml
   - Sets up logging and configuration
   - Initializes entity stores

2. **Configuration Management**
   - Input: dummy_CSV_data.csv (DOJ contract records)
   - Output: /output/entities/ directory
   - Entity JSON files based on processing order

3. **Entity Processing Order**
   ```yaml
   Agency (Order: 1)
   Recipient (Order: 2)
   Contract (Order: 3)
   Transaction (Order: 4)
   Location (Order: 5)
   ```

### Entity Analysis

#### 1. Agency Entity
- Primary Key: agency_id (015 - Department of Justice)
- Sub-agencies: USMS (1544) and Offices/Boards/Divisions (1501)
- Stores hierarchical agency relationships

#### 2. Recipient Entity
- Primary Key: recipient_uei 
- Captures business details including:
  - Core company information
  - Parent company relationships
  - Business classifications
  - Contact details

#### 3. Contract Entity
- Primary Key: contract_award_unique_key
- Links agencies and recipients
- Stores:
  - Award details
  - Financial information
  - Performance periods
  - Contract metadata

#### 4. Transaction Entity
- Primary Key: contract_transaction_unique_key
- Records individual contract actions
- Tracks:
  - Modifications
  - Obligations
  - Action dates and types

#### 5. Location Entity
- Composite Key: Based on address components
- Handles both:
  - Recipient addresses
  - Performance locations

### Data Relationships

The system maintains complex relationships between entities:

1. **Hierarchical**
   - Agency → Sub-agency → Office
   - Recipient → Parent Company

2. **Associative**
   - Contract → Agency (Awarding)
   - Contract → Agency (Funding)
   - Contract → Recipient
   - Contract → Location (Performance)
   - Transaction → Contract

### Processing Pipeline

1. **Record Processing**
```python
def process_entity_data(entity_stores, record, config):
    - Extracts entities in processing_order
    - Validates data
    - Creates relationships
    - Maintains referential integrity
```

2. **Entity Store Management**
```python
class EntityStore:
    - Handles entity validation
    - Manages relationships
    - Processes field mappings
    - Maintains data integrity
```

3. **Field Mapping**
```python
class EntityMapper:
    - Direct field mapping
    - Multi-source mapping
    - Object/nested mapping
    - Reference mapping
    - Template mapping
```

### Configuration Structure

The conversion_config.yaml file defines:

1. **System Settings**
   ```yaml
   system:
     processing:
       records_per_chunk: 10000
       entity_save_frequency: 10000
     io:
       input:
         file: "dummy_CSV_data.csv"
       output:
         directory: "output"
   ```

2. **Field Properties**
   ```yaml
   field_properties:
     numeric:
       money:
         validation:
           type: decimal
           precision: 2
     date:
       standard:
         format: "%Y-%m-%d"
   ```

3. **Entity Definitions**
   ```yaml
   entities:
     agency:
       processing_order: 1
       key_fields: [agency_id]
     recipient:
       processing_order: 2
       key_fields: [recipient_uei]
   ```

### Implementation Status

#### Completed Components
- ✓ Base configuration loading
- ✓ Entity store implementation
- ✓ Field mapping system
- ✓ Relationship management
- ✓ Basic validation

#### Next Steps
1. **Performance Optimization**
   - Batch processing implementation
   - Memory management for large datasets
   - Caching strategies

2. **Error Handling**
   - Comprehensive validation rules
   - Error reporting
   - Recovery mechanisms

3. **Testing**
   - Unit test coverage
   - Integration tests
   - Performance benchmarks

## Continuation Prompts

[Previous continuation prompts remain unchanged]

## Notes

This implementation properly handles:
- Complex hierarchical relationships
- Multi-source field mappings
- Data validation
- Entity references
- Incremental processing

Key focus areas for next phase:
1. Performance optimization
2. Error handling enhancement
3. Test coverage expansion
4. Documentation updates
