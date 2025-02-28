"""Test utilities and helper functions.

This module provides utility functions and helpers for testing the USASpending package.
Type checking is strictly enforced.
"""
from __future__ import annotations

import pytest
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime

from usaspending.utils import convert_field_value, generate_entity_key, TypeConverter
from usaspending.types import (
    ConfigType, EntityData, ChunkInfo, EntityStats,
    TypeConversionConfig, InputConfig, OutputConfig
)

# Type aliases for testing
TestDataDict = Dict[str, Any]
TestConfigDict = Dict[str, Any]

def create_test_config(
    input_file: str = "test.csv",
    batch_size: int = 100,
    chunk_size: int = 1000,
    create_index: bool = True
) -> TestConfigDict:
    """Create a test configuration with customizable parameters.
    
    Args:
        input_file: Name of input CSV file
        batch_size: Size of processing batches
        chunk_size: Number of records per output chunk
        create_index: Whether to create an index file
        
    Returns:
        Test configuration dictionary
    """
    return {
        "global": {
            "encoding": "utf-8",
            "date_format": "%Y-%m-%d"
        },
        "contracts": {
            "input": {
                "file": input_file,
                "batch_size": batch_size
            },
            "output": {
                "main_file": "test_output.json",
                "indent": 2,
                "ensure_ascii": False
            },
            "chunking": {
                "enabled": True,
                "records_per_chunk": chunk_size,
                "create_index": create_index
            },
            "type_conversion": {
                "date_fields": ["action_date", "last_modified_date"],
                "numeric_fields": ["obligation", "base_amount"],
                "boolean_true_values": ["Y", "YES", "TRUE", "1"],
                "boolean_false_values": ["N", "NO", "FALSE", "0"]
            }
        }
    }

def create_test_record(
    uei: str = "ABC123",
    amount: float = 1000.00,
    date: str = "2024-01-15",
    is_active: str = "Y"
) -> TestDataDict:
    """Create a test record with customizable values.
    
    Args:
        uei: Unique Entity ID
        amount: Award amount
        date: Action date
        is_active: Active status
        
    Returns:
        Test record dictionary
    """
    return {
        "recipient_uei": uei,
        "recipient_name": f"Test Company {uei}",
        "award_amount": str(amount),
        "action_date": date,
        "is_active": is_active,
        "modification_number": "",
        "transaction_number": None
    }

def verify_entity_key(key: str, prefix: str, data: EntityData) -> bool:
    """Verify that an entity key is correctly formatted.
    
    Args:
        key: Generated entity key to verify
        prefix: Expected prefix for the key
        data: Entity data used to generate the key
        
    Returns:
        True if key format is valid
    """
    if not key.startswith(f"{prefix}_"):
        return False
    
    # Check if it's a natural key
    natural_key_part = key[len(prefix)+1:]
    if any(v for v in data.values() if str(v) in natural_key_part):
        return True
    
    # Check if it's a hash key (32 chars for MD5)
    if len(natural_key_part) == 32 and all(c in "0123456789abcdef" for c in natural_key_part):
        return True
        
    return False

@pytest.mark.unit
class TestUtils:
    """Test suite for utility functions."""
    
    @pytest.fixture
    def sample_config(self) -> TestConfigDict:
        """Provide test configuration."""
        return {
            "global": {
                "date_format": "%Y-%m-%d"
            },
            "contracts": {
                "type_conversion": {
                    "date_fields": ["action_date", "period_of_performance_start"],
                    "numeric_fields": ["obligation", "base_amount"],
                    "boolean_true_values": ["Y", "YES", "1"],
                    "boolean_false_values": ["N", "NO", "0"]
                }
            }
        }

    def test_convert_field_value_date(self, sample_config: TestConfigDict) -> None:
        """Test date field conversion."""
        value = "2024-01-15"
        result = convert_field_value(value, "action_date", sample_config)
        assert result == "2024-01-15T00:00:00"

    def test_convert_field_value_numeric(self, sample_config: TestConfigDict) -> None:
        """Test numeric field conversion."""
        value = "$1,234.56"
        result = convert_field_value(value, "obligation", sample_config)
        assert result == 1234.56
        
        value = "1,000"
        result = convert_field_value(value, "base_amount", sample_config)
        assert result == 1000

    def test_convert_field_value_boolean(self, sample_config: TestConfigDict) -> None:
        """Test boolean field conversion."""
        assert convert_field_value("Y", "is_active", sample_config) is True
        assert convert_field_value("NO", "is_active", sample_config) is False
        assert convert_field_value("UNKNOWN", "is_active", sample_config) == "UNKNOWN"

    def test_generate_entity_key(self) -> None:
        """Test entity key generation."""
        data: EntityData = {"id": "123", "name": "Test"}
        
        # Test with key fields
        key = generate_entity_key("test", data, ["id"])
        assert verify_entity_key(key, "TEST", data)
        
        # Test with multiple key fields
        key = generate_entity_key("test", data, ["id", "name"])
        assert verify_entity_key(key, "TEST", data)
        
        # Test hash fallback
        key = generate_entity_key("test", data)
        assert verify_entity_key(key, "TEST", data)

    def test_generate_entity_key_missing_fields(self) -> None:
        """Test key generation with missing fields."""
        data: EntityData = {"id": "123"}
        
        # Should fall back to hash when key field is missing
        key = generate_entity_key("test", data, ["id", "missing_field"])
        assert verify_entity_key(key, "TEST", data)

@pytest.fixture
def type_config() -> Dict[str, Any]:
    """Sample type conversion configuration."""
    return {
        'type_conversion': {
            'date_fields': ['action_date', 'period_of_performance_start_date'],
            'numeric_fields': ['federal_action_obligation', 'base_exercised_options_value'],
            'boolean_fields': ['is_fpds', 'corporate_entity_not_tax_exempt'],
            'value_mapping': {
                'true_values': ['true', 'yes', 'y', '1', 't'],
                'false_values': ['false', 'no', 'n', '0', 'f']
            }
        }
    }

def test_numeric_conversion(type_config):
    """Test numeric value conversions."""
    converter = TypeConverter(type_config)
    
    # Test integer conversion
    assert converter.convert_value('1000', 'federal_action_obligation') == 1000
    assert converter.convert_value('$1,000', 'federal_action_obligation') == 1000
    
    # Test float conversion
    assert converter.convert_value('1000.50', 'federal_action_obligation') == 1000.50
    assert converter.convert_value('$1,000.50', 'federal_action_obligation') == 1000.50
    
    # Test invalid numbers
    assert converter.convert_value('invalid', 'federal_action_obligation') is None
    assert converter.convert_value('', 'federal_action_obligation') is None

def test_date_conversion(type_config):
    """Test date value conversions."""
    converter = TypeConverter(type_config)
    
    # Test ISO format
    assert converter.convert_value('2024-01-15', 'action_date') == '2024-01-15'
    
    # Test invalid dates
    assert converter.convert_value('2024-13-45', 'action_date') is None
    assert converter.convert_value('invalid', 'action_date') is None
    assert converter.convert_value('', 'action_date') is None

def test_boolean_conversion(type_config):
    """Test boolean value conversions."""
    converter = TypeConverter(type_config)
    
    # Test true values
    assert converter.convert_value('true', 'is_fpds') is True
    assert converter.convert_value('yes', 'is_fpds') is True
    assert converter.convert_value('1', 'is_fpds') is True
    assert converter.convert_value('t', 'is_fpds') is True
    
    # Test false values
    assert converter.convert_value('false', 'is_fpds') is False
    assert converter.convert_value('no', 'is_fpds') is False
    assert converter.convert_value('0', 'is_fpds') is False
    assert converter.convert_value('f', 'is_fpds') is False
    
    # Test invalid values
    assert converter.convert_value('invalid', 'is_fpds') is None
    assert converter.convert_value('', 'is_fpds') is None

def test_string_conversion(type_config):
    """Test string value handling."""
    converter = TypeConverter(type_config)
    
    # Test regular string field
    assert converter.convert_value('test value', 'description') == 'test value'
    assert converter.convert_value(' TEST VALUE ', 'description') == 'test value'
    assert converter.convert_value('', 'description') is None

def test_value_caching(type_config):
    """Test value caching behavior."""
    converter = TypeConverter(type_config)
    
    # Add some values to cache
    for i in range(15000):  # More than max cache size
        converter.convert_value(str(i), 'test_field')
    
    # Check cache was cleaned
    assert len(converter._value_cache) <= converter.max_cache_size

def test_type_validation(type_config):
    """Test type validation functions."""
    converter = TypeConverter(type_config)
    
    # Test numeric validation
    assert converter.validate_type('1000.50', 'federal_action_obligation') is True
    assert converter.validate_type('invalid', 'federal_action_obligation') is False
    
    # Test date validation
    assert converter.validate_type('2024-01-15', 'action_date') is True
    assert converter.validate_type('invalid', 'action_date') is False
    
    # Test boolean validation
    assert converter.validate_type('true', 'is_fpds') is True
    assert converter.validate_type('invalid', 'is_fpds') is False
    
    # Test other field types
    assert converter.validate_type('any value', 'description') is True