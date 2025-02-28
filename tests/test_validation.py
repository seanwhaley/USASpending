from usaspending.validation import ValidationEngine

def test_date_range_validation(sample_config):
    """Test date range validation scenarios."""
    engine = ValidationEngine(sample_config)

    # Test valid date range
    result = engine.validate_field(
        'period_of_performance_start_date',
        '2024-01-01',
        [{'type': 'type', 'value': 'date'}],
        {'period_of_performance_current_end_date': '2024-12-31'}
    )
    assert result.valid

    # Test invalid date range
    result = engine.validate_field(
        'period_of_performance_start_date',
        '2024-12-31',
        [{'type': 'type', 'value': 'date'}],
        {'period_of_performance_current_end_date': '2024-01-01'}
    )
    assert not result.valid
    assert result.error_type == 'date_range_invalid'

def test_numeric_field_validation_edge_cases(sample_config):
    """Test numeric field validation edge cases."""
    engine = ValidationEngine(sample_config)

    # Test valid numeric values
    valid_values = ['1000', '1000.00', '0.00', '-1000.00', '1,000.00']
    for value in valid_values:
        result = engine.validate_field(
            'federal_action_obligation',
            value,
            [{'type': 'type', 'value': 'numeric'}]
        )
        assert result.valid, f"Failed for value: {value}"

    # Test invalid numeric values
    invalid_values = ['ABC', '1000.000', '1.2.3', '1,000,000,00']
    for value in invalid_values:
        result = engine.validate_field(
            'federal_action_obligation',
            value,
            [{'type': 'type', 'value': 'numeric'}]
        )
        assert not result.valid, f"Should fail for value: {value}"
        assert result.error_type == 'numeric_invalid'

def test_domain_value_case_sensitivity(sample_config):
    """Test domain value validation with different case combinations."""
    engine = ValidationEngine(sample_config)

    # Test case variations
    test_cases = ['A', 'a', 'B', 'b']
    for value in test_cases:
        result = engine.validate_field(
            'action_type',
            value,
            [{'type': 'exists_in_mapping', 'mapping': 'action_type'}]
        )
        assert result.valid, f"Failed for value: {value}"

    # Test invalid values with correct format
    result = engine.validate_field(
        'action_type',
        'C',  # Not in mapping
        [{'type': 'exists_in_mapping', 'mapping': 'action_type'}]
    )
    assert not result.valid
    assert result.error_type == 'domain_value_invalid'

def test_multiple_validation_rules(sample_config):
    """Test fields with multiple validation rules."""
    engine = ValidationEngine(sample_config)

    # Test combined numeric and domain validation
    result = engine.validate_field(
        'federal_action_obligation',
        '1000.00',
        [
            {'type': 'type', 'value': 'numeric'},
            {'type': 'decimal', 'precision': 2},
            {'type': 'min_value', 'value': 0}
        ]
    )
    assert result.valid

    # Test failing multiple rules
    result = engine.validate_field(
        'federal_action_obligation',
        '-1000.000',  # Fails both precision and min_value
        [
            {'type': 'type', 'value': 'numeric'},
            {'type': 'decimal', 'precision': 2},
            {'type': 'min_value', 'value': 0}
        ]
    )
    assert not result.valid

def test_bulk_validation_performance(sample_config):
    """Test validation performance with bulk data."""
    engine = ValidationEngine(sample_config)
    
    # Generate test data
    test_records = [
        {
            'federal_action_obligation': f'{i}.00',
            'period_of_performance_start_date': '2024-01-01',
            'period_of_performance_current_end_date': '2024-12-31',
            'action_type': 'A',
            'uei': 'ABC123DEF456'
        }
        for i in range(100)
    ]

    # Validate bulk records
    for record in test_records:
        results = engine.validate_entity('transaction', record)
        assert not any(not r.valid for r in results), "Bulk validation failed"

def test_validate_field(sample_config):
    """Test field validation with various rules."""
    engine = ValidationEngine(sample_config)

    # Test empty value handling for required fields
    result = engine.validate_field(
        'action_date',
        None,
        [{'type': 'required'}]
    )
    assert not result.valid
    assert result.error_type == 'date_None'

    result = engine.validate_field(
        'federal_action_obligation',
        '',
        [{'type': 'required'}]
    )
    assert not result.valid
    assert result.error_type == 'numeric_None'

    # Test empty value handling for optional fields
    result = engine.validate_field(
        'description',
        None,
        []
    )
    assert result.valid

    # Test decimal validation
    result = engine.validate_field(
        'federal_action_obligation',
        '1000.00',
        [{'type': 'decimal', 'precision': 2}]
    )
    assert result.valid

    result = engine.validate_field(
        'federal_action_obligation',
        '1000.123',
        [{'type': 'decimal', 'precision': 2}]
    )
    assert not result.valid

    # Test date validation with explicit type
    result = engine.validate_field(
        'action_date',
        '2024-01-15',
        [{'type': 'type', 'value': 'date'}]
    )
    assert result.valid

    result = engine.validate_field(
        'action_date',
        '01/15/2024',
        [{'type': 'type', 'value': 'date'}]
    )
    assert not result.valid
    assert result.error_type == 'date_format'

    # Test pattern validation
    result = engine.validate_field(
        'uei',
        'ABC123DEF456',
        [{'type': 'pattern', 'pattern': r'^[A-Z0-9]{12}$'}]
    )
    assert result.valid

    result = engine.validate_field(
        'uei',
        'invalid-uei',
        [{'type': 'pattern', 'pattern': r'^[A-Z0-9]{12}$'}]
    )
    assert not result.valid

def test_validate_entity(sample_config):
    """Test entity-level validation."""
    engine = ValidationEngine(sample_config)

    # Test transaction validation
    transaction = {
        'federal_action_obligation': '1000.00',
        'uei': 'ABC123DEF456'
    }
    results = engine.validate_entity('transaction', transaction)
    assert not any(not r.valid for r in results)

    # Test invalid transaction
    invalid_transaction = {
        'federal_action_obligation': '1000.123',
        'uei': 'invalid-uei'
    }
    results = engine.validate_entity('transaction', invalid_transaction)
    assert any(not r.valid for r in results)

def test_validate_business_characteristics(sample_config):
    """Test business characteristics validation."""
    engine = ValidationEngine(sample_config)

    # Test valid characteristics (all can be true)
    data = {
        'characteristics': {
            'minority_owned_business': True,
            'asian_pacific_american_owned_business': True,
            'black_american_owned_business': True
        }
    }
    results = engine.validate_business_characteristics(data)
    assert not any(not r.valid for r in results)

    # Test mixed boolean values
    data = {
        'characteristics': {
            'minority_owned_business': True,
            'asian_pacific_american_owned_business': False,
            'black_american_owned_business': True
        }
    }
    results = engine.validate_business_characteristics(data)
    assert not any(not r.valid for r in results)

def test_validate_field_relationships(sample_config):
    """Test validation of field relationships."""
    engine = ValidationEngine(sample_config)

    # Test valid relationship
    result = engine.validate_field(
        'base_exercised_options_value',
        1000.00,
        [{'type': 'less_than_or_equal', 'field': 'base_and_all_options_value'}],
        {'base_and_all_options_value': 2000.00}
    )
    assert result.valid

    # Test invalid relationship
    result = engine.validate_field(
        'base_exercised_options_value',
        2000.00,
        [{'type': 'less_than_or_equal', 'field': 'base_and_all_options_value'}],
        {'base_and_all_options_value': 1000.00}
    )
    assert not result.valid

def test_domain_value_validation(sample_config):
    """Test validation against domain value mappings."""
    engine = ValidationEngine(sample_config)

    # Test valid domain value
    result = engine.validate_field(
        'action_type',
        'A',
        [{'type': 'exists_in_mapping', 'mapping': 'action_type'}]
    )
    assert result.valid

    # Test invalid domain value
    result = engine.validate_field(
        'action_type',
        'X',
        [{'type': 'exists_in_mapping', 'mapping': 'action_type'}]
    )
    assert not result.valid

def test_null_value_validation(sample_config):
    """Test validation of null/empty values."""
    engine = ValidationEngine(sample_config)
    
    # Test null handling for typed fields
    result = engine.validate_field(
        'action_date',
        None,
        [{'type': 'type', 'value': 'date'}]
    )
    assert result.valid  # Optional field can be null

    result = engine.validate_field(
        'action_date',
        '',
        [{'type': 'type', 'value': 'date'}, {'type': 'required'}]
    )
    assert not result.valid
    assert result.error_type == 'date_None'

    # Test whitespace handling
    result = engine.validate_field(
        'federal_action_obligation',
        '   ',
        [{'type': 'type', 'value': 'numeric'}, {'type': 'required'}]
    )
    assert not result.valid
    assert result.error_type == 'numeric_None'

def test_type_validation(sample_config):
    """Test type-specific validation rules."""
    engine = ValidationEngine(sample_config)

    # Test numeric type validation
    result = engine.validate_field(
        'federal_action_obligation',
        'abc',
        [{'type': 'type', 'value': 'numeric'}]
    )
    assert not result.valid
    assert result.error_type == 'numeric_invalid'

    # Test date type validation
    result = engine.validate_field(
        'action_date',
        '2024-13-45',
        [{'type': 'type', 'value': 'date'}]
    )
    assert not result.valid
    assert result.error_type == 'date_invalid'

    # Test boolean type validation
    result = engine.validate_field(
        'is_fpds',
        'invalid',
        [{'type': 'type', 'value': 'boolean'}]
    )
    assert not result.valid
    assert result.error_type == 'boolean_invalid'