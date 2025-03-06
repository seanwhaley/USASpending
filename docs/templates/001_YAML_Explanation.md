The USASpending conversion configuration YAML file provides a comprehensive system for transforming raw data into structured entities with defined relationships. This architecture follows a layered approach where higher-level concepts build on foundational definitions.

## Configuration File Structure Overview

```
conversion_config.yaml
├─ 1. SYSTEM CONFIGURATION - Global processing settings
├─ 2. VALIDATION GROUPS - Reusable validation rule sets
├─ 3. DATA DICTIONARY - External reference data mapping
├─ 4. FIELD PROPERTIES - Field-level validation and transformation rules
├─ 5. ENTITY RELATIONSHIPS - Explicit relationship definitions
└─ 6. ENTITY DEFINITIONS - Complete entity specifications
```

## Key Architectural Components

### 1. System Configuration
Base-level system parameters that control overall processing behavior, I/O settings, and error handling strategies. These settings apply globally across all entity processing.

### 2. Validation Groups
Reusable validation configurations that can be applied to multiple fields across different entities. These provide consistent validation logic for common data types (amounts, dates, etc.).

### 3. Data Dictionary
Configuration for importing and cross-referencing external data dictionaries, ensuring alignment with authoritative field definitions and business rules.

### 4. Field Properties
Defines validation and transformation rules for field types (numeric, string, date, boolean, enum, etc.). These properties are referenced in entity field mappings to ensure consistent handling.

### 5. Entity Relationships
**Critical section for hierarchical structures.** This section explicitly defines all relationships between entities with:
- Source and target entity types
- Relationship type (hierarchical or associative)
- Cardinality (one_to_many, many_to_one, one_to_one)
- Key mapping between entities
- Metadata for relationship context

### 6. Entity Definitions
Each entity definition includes:
- Key fields for unique identification
- Field mappings (direct, multi_source, object, reference, template)
- Relationship references (linking to relationship definitions)
- Processing rules (order, dependencies, validation level)

## Entity Mapper Implementation

The `EntityMapper` class should be designed to interpret this configuration as follows:

1. **Read Entity and Relationship Definitions**: Load both entity definitions and relationship configuration.

2. **Process Relationships During Mapping**:
   - For each entity being processed, examine its related relationships
   - For hierarchical relationships:
     - When processing a parent entity, create collection fields for child entities
     - When processing child entities, include parent references
     - Properly nest structures based on relationship cardinality

3. **Use Relationship Type for Structure**:
   - `hierarchical` + `one_to_many` = parent entity contains collection of child entities
   - `hierarchical` + `many_to_one` = child entity references parent entity
   - `associative` = creates references without nesting

4. **Collection Naming Convention**:
   - For `one_to_many` hierarchical relationships, the collection field should be the plural of the target entity name
   - Example: agency-to-sub_agency relationship creates `sub_agencies` collection in agency entities

5. **Key Field Usage**:
   - Use the relationship's `keyMapping` section to determine how entities are connected
   - Composite keys should be handled according to the `compositeKey` flag

## Entity Structure Output

For hierarchical relationships (like agency → sub-agency → office), the output JSON should follow this pattern:

```json
{
  "entity_type": "agency",
  "id": "123",
  "agency_code": "123",
  "agency_name": "Department of Example",
  "sub_agencies": [
    {
      "id": "45",
      "sub_agency_code": "45",
      "sub_agency_name": "Example Division",
      "offices": [
        {
          "id": "678",
          "office_code": "678",
          "office_name": "Example Office A"
        },
        {
          "id": "679",
          "office_code": "679",
          "office_name": "Example Office B"
        }
      ]
    },
    {
      "id": "46",
      "sub_agency_code": "46",
      "sub_agency_name": "Another Division",
      "offices": [...]
    }
  ]
}
```

## Implementation Requirements

1. **No Hardcoding of Relationship Types**: The entity mapper should not hardcode which relationships are hierarchical; this should be derived from the `relationshipType` and `cardinality` in the relationship definitions.

2. **Relationship-Driven Nesting**: Entity nesting should be driven entirely by relationship definitions, not by naming conventions or patterns.

3. **Collection Field Generation**: Collection field names should be derived from the target entity name through proper pluralization.

4. **Post-Processing**: The entity mapper may need post-processing to merge multiple instances of nested entities when they appear across different input records.

This configuration-driven approach ensures that all entity structures and relationships are defined explicitly in the YAML file, minimizing hardcoded logic and maximizing flexibility for different entity models.