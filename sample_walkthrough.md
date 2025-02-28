# USASpending Data Processing Walkthrough

## A. Setup and Configuration

### Initialization Steps
1. Command Line Processing
   - `--config` or `-c`: Path to configuration file (defaults to conversion_config.yaml)
   - `--input` or `-i`: Input CSV file path (overrides config file setting)
   - `--output-dir` or `-o`: Output directory path (overrides config file setting)
   - `--batch-size` or `-b`: Process batch size (overrides config file setting)
   - `--verbose` or `-v`: Enable verbose logging

2. Logging Setup
   - conversion.log: Contains INFO level and above messages
   - debug.log: Contains detailed DEBUG level messages
   - Log level set by --verbose flag (DEBUG if enabled, INFO if not)

3. Configuration Loading
   - Load YAML configuration file (default: conversion_config.yaml)
   - Apply command line overrides
   - Create output directory if needed

## B. Input Structure and Validation

### Input Data Structure

#### Complete CSV Field Categories

| Category | MorphWorks Contract | FedEx Contract |
|----------|-------------------|----------------|
| **Identifiers** |
| contract_transaction_unique_key | 1501_4732_15JPSS24F00000910_P00001_47QTCA20D005U_0 | 1544_1501_15M40024FA3500004_0_15JPSS24D00000254_0 |
| contract_award_unique_key | CONT_AWD_15JPSS24F00000910_1501_47QTCA20D005U_4732 | CONT_AWD_15M40024FA3500004_1544_15JPSS24D00000254_1501 |
| award_id_piid | 15JPSS24F00000910 | 15M40024FA3500004 |
| **Values** (Note: current_total_value_of_award maps to base_exercised_options_value, potential_total_value_of_award maps to base_and_all_options_value) |
| federal_action_obligation | 0.00 | 0.00 |
| current_total_value_of_award | 958756.74 | 70000.00 |
| potential_total_value_of_award | 5004390.54 | 70000.00 |
| base_exercised_options_value | 0.00 | 70000.00 |
| base_and_all_options_value | 5000.00 | 70000.00 |
| total_dollars_obligated | 0.00 | 0.00 |
| **Agency Information** |
| awarding_agency_code | 015 | 015 |
| awarding_agency_name | Department of Justice | Department of Justice |
| awarding_sub_agency_code | 1501 | 1544 |
| awarding_sub_agency_name | Offices, Boards and Divisions | U.S. Marshals Service |
| awarding_office_code | 15JPSS | 15M400 |
| awarding_office_name | JMD-PROCUREMENT SERVICES STAFF | U.S. DEPT OF JUSTICE, USMS |
| funding_agency_code | 015 | 015 |
| funding_agency_name | Department of Justice | Department of Justice |
| funding_sub_agency_code | 1501 | 1544 |
| funding_sub_agency_name | Offices, Boards and Divisions | U.S. Marshals Service |
| funding_office_code | 15JSDS | 15M400 |
| funding_office_name | SERVICE DELIVERY STAFF (JMD) | U.S. DEPT OF JUSTICE, USMS |
| **Recipient Information** |
| recipient_uei | UNXEYQN41M87 | EM7LMJJCF6B7 |
| recipient_name | MORPHWORKS INC. | FEDERAL EXPRESS CORPORATION |
| recipient_doing_business_as_name | MORPHWORKS INC. | FEDEX |
| recipient_name_raw | MORPHWORKS INC. | FEDERAL EXPRESS CORPORATION |
| cage_code | 7VYR1 | 01FJ4 |
| recipient_parent_uei | UNXEYQN41M87 | D8YCU3XSC4V5 |
| recipient_parent_name | MORPHWORKS INC. | FEDEX CORP |
| recipient_parent_name_raw | MORPHWORKS INC. | FEDERAL EXPRESS CORPORATION |
| **Contact Information** |
| recipient_phone_number | 7033720828 | 2022922241 |
| recipient_fax_number | null | 8663702491 |
| **Contract Details** |
| type_of_contract_pricing_code | Y | J |
| type_of_contract_pricing | TIME AND MATERIALS | FIRM FIXED PRICE |
| action_date | 2024-09-30 | 2024-09-30 |
| period_of_performance_start_date | 2024-10-01 | 2024-10-01 |
| period_of_performance_current_end_date | 2025-09-30 | 2025-09-30 |
| award_or_idv_flag | AWARD | AWARD |
| award_type_code | C | C |
| award_type | DELIVERY ORDER | DELIVERY ORDER |
| solicitation_identifier | null | null |
| **Business Characteristics** (f = false, t = true) |
| alaskan_native_corporation_owned_firm | f | f |
| american_indian_owned_business | f | f |
| indian_tribe_federally_recognized | f | f |
| native_hawaiian_organization_owned_firm | f | f |
| tribally_owned_firm | f | f |
| veteran_owned_business | f | f |
| service_disabled_veteran_owned_business | f | f |
| woman_owned_business | f | f |
| women_owned_small_business | f | f |
| economically_disadvantaged_women_owned_small_business | f | f |
| joint_venture_women_owned_small_business | f | f |
| joint_venture_economic_disadvantaged_women_owned_small_bus | f | f |
| minority_owned_business | f | f |
| subcontinent_asian_asian_indian_american_owned_business | f | f |
| asian_pacific_american_owned_business | f | f |
| black_american_owned_business | f | f |
| hispanic_american_owned_business | f | f |
| native_american_owned_business | f | f |
| other_minority_owned_business | f | f |
| **Business Structure** (f = false, t = true) |
| corporate_entity_not_tax_exempt | t | t |
| corporate_entity_tax_exempt | f | f |
| partnership_or_limited_liability_partnership | f | f |
| sole_proprietorship | f | f |
| small_agricultural_cooperative | f | f |
| international_organization | f | f |
| us_government_entity | f | f |
| **Size Standards** (f = false, t = true) |
| small_disadvantaged_business | f | f |
| emerging_small_business | f | f |
| c8a_program_participant | f | f |
| historically_underutilized_business_zone_hubzone_firm | f | f |
| **Competition Information** |
| extent_competed_code | A | C |
| extent_competed | FULL AND OPEN COMPETITION | NOT COMPETED |
| solicitation_procedures_code | MAFO | SSS |
| solicitation_procedures | SUBJECT TO MULTIPLE AWARD FAIR OPPORTUNITY | ONLY ONE SOURCE |
| type_of_set_aside_code | SBA | NONE |
| type_of_set_aside | SMALL BUSINESS SET ASIDE - TOTAL | NO PREFERENCE USED |
| evaluated_preference_code | NONE | null |
| evaluated_preference | NO PREFERENCE USED | null |
| **Emergency Funding** |
| disaster_emergency_fund_codes | null | null |
| covid19_supplementals_outlayed | 0.00 | 0.00 |
| covid19_supplementals_obligated | 0.00 | 0.00 |
| iija_supplemental_outlayed | 0.00 | 0.00 |
| iija_supplemental_obligated | 0.00 | 0.00 |
| **Financial Accounts** |
| treasury_accounts | [] | [] |
| federal_accounts | [] | [] |
| object_classes | [] | [] |
| program_activities | [] | [] |
| **Parent Award** |
| parent_award_agency_id | 4732 | null |
| parent_award_agency_name | FEDERAL ACQUISITION SERVICE | null |
| parent_award_id_piid | 47QTCA20D005U | null |
| parent_award_modification_number | PA0006 | null |
| **Location Information** |
| recipient_country_code | USA | USA |
| recipient_country_name | UNITED STATES | UNITED STATES |
| recipient_address_line_1 | 1750 TYSONS BLVD | 3610 HACKS CROSS RD |
| recipient_address_line_2 | STE 1500 | null |
| recipient_city_name | MCLEAN | MEMPHIS |
| recipient_county_name | FAIRFAX | SHELBY |
| recipient_state_code | VA | TN |
| recipient_state_name | VIRGINIA | TENNESSEE |
| recipient_zip_4_code | 221024200 | 381258800 |
| prime_award_transaction_recipient_cd_original | VA-11 | TN-09 |
| prime_award_transaction_recipient_cd_current | VA-11 | TN-09 |
| **Place of Performance** |
| primary_place_of_performance_country_code | USA | USA |
| primary_place_of_performance_country_name | UNITED STATES | UNITED STATES |
| primary_place_of_performance_city_name | MCLEAN | MEMPHIS |
| primary_place_of_performance_county_name | FAIRFAX | SHELBY |
| primary_place_of_performance_state_code | VA | TN |
| primary_place_of_performance_state_name | VIRGINIA | TENNESSEE |
| primary_place_of_performance_zip_4 | 221024200 | 381258800 |
| prime_award_transaction_place_of_performance_cd_original | VA-11 | TN-09 |
| prime_award_transaction_place_of_performance_cd_current | VA-11 | TN-09 |
| **Other Information** |
| number_of_actions | 1 | 1 |
| initial_report_date | 2024-09-30 | 2024-09-29 |
| last_modified_date | 2024-09-30 | 2024-09-30 |
| usaspending_permalink | https://www.usaspending.gov/award/CONT_AWD_15JPSS24F00000910_1501_47QTCA20D005U_4732/ | https://www.usaspending.gov/award/CONT_AWD_15M40024FA3500004_1544_15JPSS24D00000254_1501/ |

### Field Categories and Validation

#### Required Fields (Must Exist)
- contract_transaction_unique_key
- contract_award_unique_key  
- award_id_piid
- federal_action_obligation
- action_date
- recipient_uei
- recipient_name
- awarding_agency_code

#### Format Validation Rules
a) Identifiers and Codes
   - UEI: 12-character alphanumeric
   - Agency codes: 3-digit numeric, zero-padded
   - PIID: Agency-specific format
   - NAICS: 6-digit numeric
   - PSC: 4-character alphanumeric

b) Dates and Times
   - All dates in YYYY-MM-DD format
   - No time components stored

c) Monetary Values
   - Decimal numbers with 2 places
   - No currency symbols or commas
   - Must be valid decimal numbers

d) Location Codes
   - Country: ISO 3-character codes
   - State: 2-letter US state codes
   - ZIP: 5 or 9 digits
   - FIPS: State(2) + County(3) digits

### Required Implementation Changes (MoSCoW Priority)

**Must Have - Implementation Timeline**

1. Field Mapping and Value Validation (Week 1)
   - Fix value mapping for award values
   - Implement numeric field validation
   - Add missing location and contact mappings
   - Update domain value consistency

2. Entity Relationship Processing (Week 2) 
   - Parent/child award relationships
   - Agency hierarchy validation
   - Location data processing
   - NAICS code handling

3. Data Validation Framework (Week 2-3)
   - Value range validation
   - Cross-field consistency checks
   - Required domain values
   - Relationship integrity

**Example Validation Flow - MorphWorks Contract**

1. Value Validation:
```
Input:
current_total_value_of_award: 958756.74
potential_total_value_of_award: 5004390.54
base_exercised_options_value: 0.00
base_and_all_options_value: 5000.00

Validation Steps:
1. Map current_total_value_of_award to base_exercised_options_value
2. Map potential_total_value_of_award to base_and_all_options_value
3. Validate numeric format (2 decimal places)
4. Verify potential_total_value_of_award >= current_total_value_of_award (5004390.54 >= 958756.74)
5. Update base values from mappings:
   base_exercised_options_value: 958756.74
   base_and_all_options_value: 5004390.54

Result: Pass - Values properly mapped and validated
```

2. Agency Hierarchy:
```
Input:
awarding_agency_code: "015"
awarding_sub_agency_code: "1501"
awarding_office_code: "15JPSS"

Validation Steps:
1. Verify agency chain:
   015 (Department of Justice)
   -> 1501 (Offices, Boards and Divisions)
   -> 15JPSS (JMD-PROCUREMENT SERVICES STAFF)
2. Validate all references exist
3. Check parent/child relationships

Result: Pass - Complete hierarchy present and valid
```

3. Parent Award:
```
Input:
parent_award_agency_id: "4732"
parent_award_agency_name: "FEDERAL ACQUISITION SERVICE"
parent_award_id_piid: "47QTCA20D005U"
parent_award_modification_number: "PA0006"

Validation Steps:
1. Verify parent award agency exists
2. Create parent award reference
3. Link to child contract
4. Validate modification sequence

Result: Pass - Parent award properly linked
```

**Example Validation Flow - FedEx Contract**

1. Value Validation:
```
Input:
current_total_value_of_award: 70000.00
potential_total_value_of_award: 70000.00
base_exercised_options_value: 70000.00
base_and_all_options_value: 70000.00

Validation Steps:
1. Map current_total_value_of_award to base_exercised_options_value
2. Map potential_total_value_of_award to base_and_all_options_value
3. Validate numeric format (2 decimal places)
4. Verify potential_total_value_of_award >= current_total_value_of_award (70000.00 >= 70000.00)
5. Validate base values match mapped values

Result: Pass - Values consistent and valid
```

2. Location Processing:
```
Input:
recipient_address:
  country_code: "USA"
  address_line_1: "3610 HACKS CROSS RD"
  city_name: "MEMPHIS"
  county_name: "SHELBY"
  state_code: "TN"
  zip_code: "381258800"

performance_address:
  country_code: "USA"
  city_name: "MEMPHIS"
  county_name: "SHELBY" 
  state_code: "TN"
  zip_code: "381258800"

Validation Steps:
1. Validate country codes against ISO list
2. Verify state codes are valid US states
3. Check ZIP code format (9 digits)
4. Validate county names against FIPS database
5. Ensure consistent state/county combinations

Result: Pass - All location fields valid
```

3. Business Characteristics:
```
Input:
corporate_entity_not_tax_exempt: "t"
corporate_entity_tax_exempt: "f"
// ...other characteristics as "f"

Validation Steps:
1. Convert string values to booleans:
   "t" -> true
   "f" -> false
2. Group into categories:
   ownership: all false
   structure: corporate_entity_not_tax_exempt: true
   size: all false
3. Validate no conflicts in classifications

Result: Pass - Boolean conversions and grouping valid
```

## C. Processing Pipeline

### I. Initial Processing (process_transactions.py -> processor.py)

#### Field Validation Stage
For each record, fields are validated against the following rules:
- Essential fields must exist and not be empty:
  ```
  contract_transaction_unique_key
  contract_award_unique_key
  award_id_piid
  federal_action_obligation
  action_date
  recipient_uei
  recipient_name
  awarding_agency_code
  ```

#### Type Conversion Stage
Fields are converted according to type_conversion config:

1. Date Fields:
```
Input:
action_date: "2024-09-30 00:00:00"
period_of_performance_start_date: "2024-10-01 00:00:00"
period_of_performance_current_end_date: "2025-09-30 00:00:00"
period_of_performance_potential_end_date: "2029-09-30 00:00:00"

Output:
action_date: "2024-09-30"
period_of_performance_start_date: "2024-10-01"
period_of_performance_current_end_date: "2025-09-30"
period_of_performance_potential_end_date: "2029-09-30"
```

2. Numeric Fields:
```
Input:
federal_action_obligation: "0.00"
base_exercised_options_value: "0.00" 
base_and_all_options_value: "5000.00"
total_obligation: "0.00"
total_dollars_obligated: "0.00"

Output:
federal_action_obligation: 0.00
base_exercised_options_value: 0.00
base_and_all_options_value: 5000.00
total_obligation: 0.00
total_dollars_obligated: 0.00
```

3. Boolean Fields and Value Mapping:
```
Input CSV Values:
corporate_entity_not_tax_exempt: "t"  # Maps to true via value_mapping
corporate_entity_tax_exempt: "f"      # Maps to false via value_mapping
veteran_owned_business: "f"           # Maps to false via value_mapping
woman_owned_business: "f"             # Maps to false via value_mapping
small_disadvantaged_business: "f"      # Maps to false via value_mapping

Output JSON Values:
corporate_entity_not_tax_exempt: true
corporate_entity_tax_exempt: false
veteran_owned_business: false
woman_owned_business: false
small_disadvantaged_business: false

Value Mapping Rules:
true for: ["true", "yes", "y", "1", "t"]
false for: ["false", "no", "n", "0", "f"]
```

4. Domain Value Mappings:
```
Input CSV Values:
contract_type_code: "C"
contract_type: "DELIVERY ORDER"
extent_competed_code: "A"
extent_competed: "FULL AND OPEN COMPETITION"
solicitation_procedures_code: "MAFO"
solicitation_procedures: "SUBJECT TO MULTIPLE AWARD FAIR OPPORTUNITY"
type_of_set_aside_code: "SBA"
type_of_set_aside: "SMALL BUSINESS SET ASIDE - TOTAL"
evaluated_preference_code: "NONE"
evaluated_preference: "NO PREFERENCE USED"

Validation Rules:
1. Code must exist in mapping
2. Description must match mapped value
3. Consistent across related records

Domain Value Mappings:
contract_type: {
    "A": "BLANKET PURCHASE AGREEMENT",
    "B": "INDEFINITE DELIVERY CONTRACT",
    "C": "DELIVERY ORDER",
    "D": "DEFINITIVE CONTRACT",
    "E": "PURCHASE ORDER",
    "F": "BASIC ORDERING AGREEMENT"
}

extent_competed: {
    "A": "FULL AND OPEN COMPETITION",
    "B": "NOT AVAILABLE FOR COMPETITION",
    "C": "NOT COMPETED",
    "D": "FULL AND OPEN COMPETITION AFTER EXCLUSION OF SOURCES",
    "E": "FOLLOW ON TO COMPETED ACTION"
}

solicitation_procedures: {
    "NP": "NEGOTIATED PROPOSAL/QUOTE",
    "SP": "SEALED BID",
    "MAFO": "SUBJECT TO MULTIPLE AWARD FAIR OPPORTUNITY",
    "SSS": "ONLY ONE SOURCE",
    "TO": "TASK ORDER",
    "DO": "DELIVERY ORDER"
}

type_of_set_aside: {
    "NONE": "NO PREFERENCE USED",
    "SBA": "SMALL BUSINESS SET ASIDE - TOTAL",
    "8A": "8(A) SET ASIDE",
    "SDVO": "SERVICE-DISABLED VETERAN-OWNED SMALL BUSINESS",
    "WOSB": "WOMAN OWNED SMALL BUSINESS",
    "HUB": "HISTORICALLY UNDERUTILIZED BUSINESS ZONE"
}

evaluated_preference: {
    "NONE": "NO PREFERENCE USED",
    "HUB": "HUB ZONE PRICE EVALUATION PREFERENCE",
    "SDVO": "SERVICE-DISABLED VETERAN OWNED SMALL BUSINESS PREFERENCE"
}

type_of_contract_pricing: {
    "A": "FIXED PRICE REDETERMINATION",
    "B": "FIXED PRICE LEVEL OF EFFORT",
    "J": "FIRM FIXED PRICE",
    "K": "FIXED PRICE WITH ECONOMIC PRICE ADJUSTMENT",
    "L": "FIXED PRICE INCENTIVE",
    "M": "FIXED PRICE AWARD FEE",
    "R": "COST PLUS AWARD FEE",
    "S": "COST NO FEE",
    "T": "COST SHARING",
    "U": "COST PLUS FIXED FEE",
    "V": "COST PLUS INCENTIVE FEE",
    "Y": "TIME AND MATERIALS",
    "Z": "LABOR HOURS",
    "1": "ORDER DEPENDENT (IDV ALLOWS PRICING ARRANGEMENT TO BE DETERMINED SEPARATELY FOR EACH ORDER)",
    "2": "COMBINATION (APPLIES TO AWARDS WHERE TWO OR MORE OF THE ABOVE APPLY)",
    "3": "OTHER (APPLIES TO AWARDS WHERE NONE OF THE ABOVE APPLY)"
}

action_type: {
    "A": "ADDITIONAL WORK (NEW AGREEMENT, JUSTIFICATION REQUIRED)",
    "B": "SUPPLEMENTAL AGREEMENT FOR WORK WITHIN SCOPE",
    "C": "FUNDING ONLY ACTION",
    "D": "CHANGE ORDER",
    "E": "TERMINATE FOR DEFAULT (COMPLETE OR PARTIAL)",
    "F": "TERMINATE FOR CONVENIENCE (COMPLETE OR PARTIAL)",
    "G": "EXERCISE AN OPTION",
    "K": "CLOSE OUT",
    "M": "OTHER ADMINISTRATIVE ACTION"
}

inherently_governmental_functions: {
    "CL": "CLOSELY ASSOCIATED",
    "CT": "CRITICAL FUNCTIONS",
    "OT": "OTHER FUNCTIONS",
    "CL,CT": "CLOSELY ASSOCIATED,CRITICAL FUNCTIONS"
}

government_furnished_property: {
    "Y": "TRANSACTION USES GFE/GFP",
    "N": "TRANSACTION DOES NOT USE GFE/GFP"
}

performance_based_service_acquisition: {
    "Y": "YES - SERVICE WHERE PBA IS USED.",
    "N": "NO - SERVICE WHERE PBA IS NOT USED.",
    "X": "NOT APPLICABLE"
}

multi_year_contract: {
    "Y": "YES",
    "N": "NO"
}

purchase_card_as_payment_method: {
    "Y": "YES",
    "N": "NO"
}
```

### II. Entity Processing

#### Recipient Entity Extraction
Input Fields Used:
```
recipient_uei: "UNXEYQN41M87"
recipient_name: "MORPHWORKS INC."
recipient_doing_business_as_name: "MORPHWORKS INC."
cage_code: "7VYR1"
recipient_parent_uei: "UNXEYQN41M87"
recipient_parent_name: "MORPHWORKS INC."
naics_code: "541519"
naics_description: "OTHER COMPUTER RELATED SERVICES"
```

Validation Rules:
- recipient_uei is required and must be non-empty
- If recipient_parent_uei exists and differs from recipient_uei, parent-child relationship is created

Field Transformations:
- Business characteristics fields are converted to boolean values
- Parent/child relationships are tracked in relationships map
- Characteristics are grouped into categories:
  - ownership
  - structure 
  - size

#### Agency Entity Extraction
Input Fields Used:
```
awarding_agency_code: "015"
awarding_agency_name: "Department of Justice"
awarding_sub_agency_code: "1501"
awarding_sub_agency_name: "Offices, Boards and Divisions"
awarding_office_code: "15JPSS"
awarding_office_name: "JMD-PROCUREMENT SERVICES STAFF"
```

Hierarchical Processing:
1. Agency Level:
   - Creates agency entity with code/name
   - Establishes as top level in hierarchy

2. Sub-Agency Level:  
   - Creates sub-agency entity
   - Links to parent agency
   - Tracks sub-agency relationships

3. Office Level:
   - Creates office entity
   - Links to sub-agency
   - Maintains full hierarchical chain

#### Contract Entity Extraction 
Input Fields Used:
```
contract_award_unique_key: "CONT_AWD_15JPSS24F00000910_1501_47QTCA20D005U_4732"
award_id_piid: "15JPSS24F00000910"
current_total_value_of_award: 958756.74  # Maps to base_exercised_options_value
potential_total_value_of_award: 5004390.54  # Maps to base_and_all_options_value
total_obligation: 0.00
period_of_performance_start_date: "2024-10-01"
period_of_performance_current_end_date: "2025-09-30"
type_of_contract_pricing_code: "Y"
type_of_contract_pricing: "TIME AND MATERIALS"
```

Transformations:
1. Key Generation:
   - Uses contract_award_unique_key if present
   - Otherwise constructs from award_id_piid + awarding_agency_code

2. Reference Creation:
   - recipient_ref: Links to recipient via recipient_uei
   - agencies: Contains references to awarding, funding, and parent award agencies
   - parent_award_ref: Links to parent award if parent_award_id_piid exists

3. Value Processing:
   - Maps current_total_value_of_award to base_exercised_options_value
   - Maps potential_total_value_of_award to base_and_all_options_value
   - Converts all monetary amounts to decimals
   - Validates base_exercised_options_value <= base_and_all_options_value
   - Tracks running totals of obligations

#### Transaction Entity Extraction
Input Fields Used:
```
contract_transaction_unique_key: "1501_4732_15JPSS24F00000910_P00001_47QTCA20D005U_0"
action_date: "2024-09-30"
action_type: "SUPPLEMENTAL AGREEMENT FOR WORK WITHIN SCOPE"
modification_number: "P00001"
federal_action_obligation: 0.00
```

Transformations:
1. Key Management:
   - Uses contract_transaction_unique_key if present
   - Otherwise constructs composite key from component fields

2. Relationship Tracking:
   - Links to contract via contract_award_unique_key
   - Tracks modification sequence for each contract
   - Maintains action date ordering

3. Value Processing:
   - Validates obligation amounts
   - Updates contract running totals
   - Tracks cumulative changes

#### Solicitation Entity Extraction
Input Fields Used:
```
solicitation_identifier: "15JPSS24F00000910"
type_of_set_aside_code: "SBA"
type_of_set_aside: "SMALL BUSINESS SET ASIDE - TOTAL"
```

### III. Entity Processing Flow

The processing pipeline handles entities in this sequence:

```
CSV Record
    |
    +-> Agency Entity Processing
    |    |
    |    +-> Create/Update Agency (015)
    |    |    +-> Name, Code, Type
    |    |    +-> Parent Award Only Flag
    |    |
    |    +-> Create/Update Sub-Agency (015:1501)
    |    |    +-> Name, Code, Parent Reference
    |    |    +-> Hierarchical Validation
    |    |
    |    +-> Create/Update Office (015:1501:15JPSS)
    |         +-> Name, Code, Parent References
    |         +-> Complete Chain Validation
    |
    +-> Recipient Entity Processing
    |    |
    |    +-> Create/Update Recipient
    |    |    +-> UEI, Name, CAGE Code
    |    |    +-> NAICS Code/Description
    |    |
    |    +-> Process Business Characteristics
    |    |    +-> Ownership Types
    |    |    +-> Business Structure
    |    |    +-> Size Standards
    |    |
    |    +-> Handle Parent/Child
    |         +-> Parent UEI Reference
    |         +-> Relationship Type
    |
    +-> Contract Entity Processing
    |    |
    |    +-> Create/Update Contract
    |    |    +-> Award ID, PIID
    |    |    +-> Values and Dates
    |    |    +-> Pricing Information
    |    |
    |    +-> Link References
    |    |    +-> Agency References
    |    |    +-> Recipient Reference
    |    |    +-> Parent Award (if exists)
    |    |
    |    +-> Validate Relationships
    |         +-> Agency Chain Complete
    |         +-> References Resolved
    |         +-> Values Consistent
    |
    +-> Transaction Entity Processing
         |
         +-> Create/Update Transaction
         |    +-> Key Generation
         |    +-> Action Information
         |    +-> Obligation Amount
         |
         +-> Process Modifications
         |    +-> Sequence Tracking
         |    +-> Temporal Validation
         |
         +-> Update Contract Stats
              +-> Obligation Totals
              +-> Modification Counts
              +-> Date Tracking
```

### IV. Relationship Management

#### Hierarchical Relationships
1. Agency Hierarchy:
```
Agency (015) 
  -> SubAgency (1501)
    -> Office (15JPSS)
```

2. Contract Hierarchy:
```
Parent Contract (if exists)
  -> Child Contract
    -> Transactions (ordered by mod number)
```

#### Reference Relationships
1. Contract References:
```
Contract -> Recipient (recipient_ref)
Contract -> Agency (awarding_agency_ref)
Contract -> Parent Contract (parent_award_ref)
```

2. Transaction References:
```
Transaction -> Contract (contract_award_unique_key)
Transaction -> Parent Transaction (via modification sequence)
```

### V. Data Quality

#### Cross-Entity Validation
1. Reference Integrity:
   - All entity references must point to existing entities
   - Hierarchical relationships are validated for cycles
   - Parent/child relationships are bidirectional

2. Value Consistency:
   - Contract values must be logically consistent
   - Transaction modifications must maintain sequence
   - Agency hierarchies must be complete

3. Temporal Integrity:
   - Performance dates must be logically ordered
   - Modification sequences must be temporally valid
   - Action dates must be within performance period

## D. Output Generation

### I. Entity Files
1. recipients.json:
```json
{
  "metadata": {
    "entity_type": "recipient",
    "total_references": null,
    "unique_entities": null
  },
  "entities": {
    "UNXEYQN41M87": {
      "uei": "UNXEYQN41M87",
      "name": "MORPHWORKS INC.",
      "dba_name": "MORPHWORKS INC.",
      "cage_code": "7VYR1",
      "naics_code": "541519",
      "naics_description": "OTHER COMPUTER RELATED SERVICES",
      "business_characteristics": {
        "ownership": {
          "alaskan_native_corporation_owned_firm": false,
          "american_indian_owned_business": false,
          "indian_tribe_federally_recognized": false,
          "native_hawaiian_organization_owned_firm": false,
          "tribally_owned_firm": false,
          "veteran_owned_business": false,
          "service_disabled_veteran_owned_business": false,
          "woman_owned_business": false,
          "women_owned_small_business": false,
          "economically_disadvantaged_women_owned_small_business": false,
          "joint_venture_women_owned_small_business": false,
          "joint_venture_economic_disadvantaged_women_owned_small_bus": false,
          "minority_owned_business": false,
          "subcontinent_asian_asian_indian_american_owned_business": false,
          "asian_pacific_american_owned_business": false,
          "black_american_owned_business": false,
          "hispanic_american_owned_business": false,
          "native_american_owned_business": false,
          "other_minority_owned_business": false
        },
        "structure": {
          "corporate_entity_not_tax_exempt": true,
          "corporate_entity_tax_exempt": false,
          "partnership_or_limited_liability_partnership": false,
          "sole_proprietorship": false,
          "small_agricultural_cooperative": false,
          "international_organization": false,
          "us_government_entity": false
        },
        "size": {
          "small_disadvantaged_business": false,
          "emerging_small_business": false,
          "c8a_program_participant": false,
          "historically_underutilized_business_zone_hubzone_firm": false
        }
      }
    }
  },
  "relationships": {
    "SUBSIDIARY_OF": {},
    "HAS_SUBSIDIARY": {}
  }
}
```

2. agencies.json:
```json
{
  "metadata": {
    "entity_type": "agency",
    "total_references": null,
    "hierarchy_levels": ["agency", "sub_agency", "office"]
  },
  "entities": {
    "015": {
      "code": "015",
      "identifier": "015",
      "name": "Department of Justice",
      "type": "agency",
      "sub_agencies": {
        "015:1501": {
          "code": "1501",
          "identifier": "015:1501",
          "name": "Offices, Boards and Divisions",
          "type": "sub_agency",
          "parent_agency_code": "015",
          "offices": {
            "015:1501:15JPSS": {
              "code": "15JPSS",
              "identifier": "015:1501:15JPSS",
              "name": "JMD-PROCUREMENT SERVICES STAFF",
              "type": "office",
              "parent_agency_code": "015",
              "parent_subagency_code": "1501"
            },
            "015:1501:15JSDS": {
              "code": "15JSDS",
              "identifier": "015:1501:15JSDS",
              "name": "SERVICE DELIVERY STAFF (JMD)",
              "type": "office",
              "parent_agency_code": "015",
              "parent_subagency_code": "1501"
            }
          }
        }
      }
    },
    "4732": {
      "code": "4732",
      "identifier": "4732",
      "name": "FEDERAL ACQUISITION SERVICE",
      "type": "agency",
      "is_parent_award_only": true
    }
  },
  "relationships": {
    "HAS_SUBAGENCY": {
      "015": ["015:1501"]
    },
    "BELONGS_TO_AGENCY": {
      "015:1501": "015"
    },
    "HAS_OFFICE": {
      "015:1501": ["015:1501:15JPSS", "015:1501:15JSDS"]
    },
    "BELONGS_TO_SUBAGENCY": {
      "015:1501:15JPSS": "015:1501",
      "015:1501:15JSDS": "015:1501"
    }
  }
}
```

3. contracts.json:
```json
{
  "metadata": {},
  "entities": {
    "CONT_AWD_15JPSS24F00000910_1501_47QTCA20D005U_4732": {
      "award_id": "CONT_AWD_15JPSS24F00000910_1501_47QTCA20D005U_4732",
      "piid": "15JPSS24F00000910",
      "type": "DELIVERY ORDER",
      "base_exercised_options_value": 958756.74,  // Mapped from current_total_value_of_award
      "base_and_all_options_value": 5004390.54,   // Mapped from potential_total_value_of_award
      "total_obligation": 0.00,
      "performance_start": "2024-10-01",
      "performance_end": "2025-09-30",
      "pricing": {
        "code": "Y",
        "description": "TIME AND MATERIALS"
      },
      "recipient_ref": "UNXEYQN41M87",
      "agencies": {
        "awarding": {
          "agency_ref": "015",
          "sub_agency_ref": "015:1501",
          "office_ref": "015:1501:15JPSS"
        },
        "funding": {
          "agency_ref": "015",
          "sub_agency_ref": "015:1501", 
          "office_ref": "015:1501:15JSDS"
        },
        "parent_award": {
          "agency_ref": "4732"
        }
      }
    }
  }
}
```

4. solicitations.json:
```json
{
  "metadata": {},
  "entities": {
    "15JPSS24F00000910": {
      "identifier": "15JPSS24F00000910",
      "set_aside": {
        "code": "SBA",
        "description": "SMALL BUSINESS SET ASIDE - TOTAL"
      }
    }
  },
  "relationships": {
    "REFERENCED_BY_CONTRACT": {},
    "REFERENCES_SOLICITATION": {}
  }
}
```

5. transactions.json:
```json
{
  "metadata": {},
  "entities": {
    "1501_4732_15JPSS24F00000910_P00001_47QTCA20D005U_0": {
      "transaction_key": "1501_4732_15JPSS24F00000910_P00001_47QTCA20D005U_0",
      "action_date": "2024-09-30",
      "action_type": "SUPPLEMENTAL AGREEMENT FOR WORK WITHIN SCOPE",
      "modification_number": "P00001",
      "description": "DATA CENTER TRANSFORMATION INITIATIVE SUPPORT SERVICES/UPDATE CLIN/SLIN NTE AMOUNT",
      "obligation_amount": 0.00,
      "award_stats": {
        "transaction_count": 1,
        "modification_count": 1,
        "first_action_date": "2024-09-30"
      }
    }
  },
  "relationships": {
    "MODIFIES": {},
    "MODIFIED_BY": {}
  }
}
```

### II. Verification

#### Transaction Chunking
- Records are written in chunks of 6500 records
- Each chunk maintains complete entity references
- Index file tracks chunk locations and metadata
- Relationships are preserved across chunks

### III. Performance Metrics

#### Processing Pipeline Stages and Logging

1. Input Stage Logging
- Input file characteristics logged at INFO level:
  ```
  Transaction file size and record count
  Expected vs actual field count
  Header validation results
  ```

2. Processing Stage Metrics
- Progress logged every 1000 records (from config)
- Batch processing statistics at DEBUG level:
  ```
  Records processed in current batch
  Entity extraction counts by type
  Memory usage statistics
  Processing rate (records/second)
  ```

3. Output Stage Tracking
- Entity statistics logged at INFO level:
  ```
  Total unique entities by type
  Relationship counts by type
  Output file sizes and locations
  ```

## E. Operational Support

### I. Recovery Systems

#### Checkpoint System

1. Progress Tracking
- Checkpoint files created containing:
  ```
  Last successfully processed record
  Current entity counts
  Chunk file status
  Error counts by category
  ```

2. Recovery Process
- On restart after failure:
  ```
  Locate last checkpoint
  Restore entity caches
  Resume from last complete chunk
  Validate relationship integrity
  ```

3. State Verification
- Before resuming processing:
  ```
  Verify output file integrity
  Check entity reference consistency
  Validate checkpoint data
  Confirm file permissions
  ```

#### Error Recovery Procedures

1. File System Issues
- Handle common scenarios:
  ```
  Disk space exhaustion
  File permission changes
  Network file system timeouts
  Concurrent access conflicts
  ```

2. Data Consistency Recovery
- Repair procedures for:
  ```
  Incomplete entity references
  Broken relationship chains
  Duplicate entity records
  Missing chunk files
  ```

3. Resource Exhaustion Recovery
- Mitigation steps for:
  ```
  Memory allocation failures
  File handle limits
  CPU throttling
  I/O bottlenecks
  ```

### II. Monitoring

#### Performance Monitoring and Logging

1. Memory Usage Monitoring
- Tracked per processing stage:
  ```
  Entity cache sizes
  Relationship map sizes
  Current batch memory footprint
  Peak memory usage
  ```

2. Chunk Management
- Chunk statistics logged at DEBUG level:
  ```
  Records per chunk
  Entity references preserved
  Chunk file sizes
  Index updates
  ```

3. Performance Optimization Points
- Key metrics tracked for optimization:
  ```
  Entity cache hit rates
  Reference resolution times
  File I/O latencies
  Memory release patterns
  ```

### III. Maintenance

a) System Health Checks
   - Daily validation runs
   - Entity reference verification
   - Performance baseline monitoring

b) Data Cleanup
   - Orphaned reference removal
   - Duplicate detection
   - Cache optimization

c) Performance Tuning
   - Processing threshold adjustments
   - Memory allocation optimization
   - I/O pattern analysis
