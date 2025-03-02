"""Tests for type conversion functionality."""
import pytest
from datetime import datetime, date
from unittest.mock import Mock

from usaspending.utils import TypeConverter

# Test configuration with validation types
TEST_CONFIG = {
    "validation_types": {
        "numeric": {
            "money": {"strip_characters": "$,."},
            "decimal": {"strip_characters": ",."},
            "integer": {"strip_characters": ","}
        },
        "date": {
            "standard": {"format": "%Y-%m-%d"}
        },
        "boolean": {
            "validation": {
                "true_values": ["true", "yes", "1"],
                "false_values": ["false", "no", "0"]
            }
        },
        "custom": {
            "phone": {
                "validator": "phone",
                "args": {"pattern": r"^\+?1?\d{9,15}$"}
            },
            "email": {
                "validator": "email",
                "args": {"pattern": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"}
            },
            "zip": {
                "validator": "zip",
                "args": {"pattern": r"^\d{5}(?:-\d{4})?$"}
            },
            "url": {
                "validator": "url",
                "args": {"pattern": r"^https?://[^\s/$.?#].[^\s]*$"}
            }
        }
    },
    "type_conversion": {
        "numeric": {
            "fields": [
                {
                    "$ref": "numeric.money",
                    "fields": ["amount", "total"]
                },
                {
                    "$ref": "numeric.decimal",
                    "fields": ["rate", "percentage"]
                },
                {
                    "$ref": "numeric.integer",
                    "fields": ["count", "quantity"]
                }
            ]
        },
        "date": {
            "fields": [
                {
                    "fields": ["created_at", "updated_at", "date_*"]
                }
            ]
        },
        "boolean": {
            "fields": [
                {
                    "fields": ["is_*", "has_*", "active"]
                }
            ]
        }
    }
}

# Added fixture for type converter configuration to fix attribute errors.
@pytest.fixture
def converter_config():
    """Return a config for type converter."""
    return {
        "string_patterns": {
            "money": {"strip_characters": "$,."},
            "decimal": {"strip_characters": ",."},
            "integer": {"strip_characters": ","}
        }
    }

@pytest.fixture
def type_converter(converter_config):
    """Create a type converter instance."""
    return TypeConverter(converter_config)

class TestNumericConversion:
    """Test numeric value conversions."""
    
    def test_money_conversion(self, type_converter):
        """Test money value conversion."""
        assert type_converter.convert_value("$1,234.56", "amount") == 1234.56
        assert type_converter.convert_value("1234.56", "amount") == 1234.56
        assert type_converter.convert_value("$1,234", "amount") == 1234.0
        assert type_converter.convert_value("invalid", "amount") is None

    def test_decimal_conversion(self, type_converter):
        """Test decimal value conversion."""
        assert type_converter.convert_value("123.45", "rate") == 123.45
        assert type_converter.convert_value("1,234.56", "rate") == 1234.56
        assert type_converter.convert_value("invalid", "rate") is None

    def test_integer_conversion(self, type_converter):
        """Test integer value conversion."""
        assert type_converter.convert_value("1,234", "count") == 1234
        assert type_converter.convert_value("1234.56", "count") == 1234
        assert type_converter.convert_value("invalid", "count") is None

class TestDateConversion:
    """Test date value conversions."""

    def test_standard_date_format(self, type_converter):
        """Test standard date format conversion."""
        assert type_converter.convert_value("2024-01-15", "created_at") == "2024-01-15"
        assert type_converter.convert_value("invalid", "created_at") is None

    def test_dynamic_date_fields(self, type_converter):
        """Test dynamic date field matching."""
        assert type_converter.convert_value("2024-01-15", "date_field") == "2024-01-15"
        assert type_converter.convert_value("2024-01-15", "date_custom") == "2024-01-15"

class TestBooleanConversion:
    """Test boolean value conversions."""

    def test_true_values(self, type_converter):
        """Test true value conversion."""
        assert type_converter.convert_value("true", "is_active") is True
        assert type_converter.convert_value("yes", "has_children") is True
        assert type_converter.convert_value("1", "active") is True

    def test_false_values(self, type_converter):
        """Test false value conversion."""
        assert type_converter.convert_value("false", "is_active") is False
        assert type_converter.convert_value("no", "has_children") is False
        assert type_converter.convert_value("0", "active") is False

    def test_invalid_boolean(self, type_converter):
        """Test invalid boolean values."""
        assert type_converter.convert_value("invalid", "is_active") is None

class TestCustomTypeValidation:
    """Test custom type validation."""

    def test_phone_validation(self, type_converter):
        """Test phone number validation."""
        assert type_converter.validate_type("1234567890", "phone") is True
        assert type_converter.validate_type("+11234567890", "phone") is True
        assert type_converter.validate_type("invalid", "phone") is False

    def test_email_validation(self, type_converter):
        """Test email validation."""
        assert type_converter.validate_type("test@example.com", "email") is True
        assert type_converter.validate_type("invalid", "email") is False

    def test_zip_validation(self, type_converter):
        """Test ZIP code validation."""
        assert type_converter.validate_type("12345", "zip") is True
        assert type_converter.validate_type("12345-6789", "zip") is True
        assert type_converter.validate_type("invalid", "zip") is False

    def test_url_validation(self, type_converter):
        """Test URL validation."""
        assert type_converter.validate_type("http://example.com", "url") is True
        assert type_converter.validate_type("https://example.com/path", "url") is True
        assert type_converter.validate_type("invalid", "url") is False

class TestCustomTypeConversion:
    """Test custom type conversion."""

    def test_phone_conversion(self, type_converter):
        """Test phone number conversion."""
        assert type_converter.convert_value("1234567890", "phone") == "(123) 456-7890"
        assert type_converter.convert_value("+11234567890", "phone") == "+11234567890"
        assert type_converter.convert_value("invalid", "phone") is None

    def test_zip_conversion(self, type_converter):
        """Test ZIP code conversion."""
        assert type_converter.convert_value("12345", "zip") == "12345"
        assert type_converter.convert_value("123456789", "zip") == "12345-6789"
        assert type_converter.convert_value("invalid", "zip") is None

class TestCaching:
    """Test type conversion caching."""

    def test_cache_hit(self, type_converter):
        """Test cache hit."""
        value = "$1,234.56"
        first_result = type_converter.convert_value(value, "amount")
        second_result = type_converter.convert_value(value, "amount")
        assert first_result == second_result
        assert first_result == 1234.56

    def test_cache_size_limit(self, type_converter):
        """Test cache size limiting."""
        # Set small cache size for testing
        type_converter.max_cache_size = 2
        
        # Fill cache
        type_converter.convert_value("$1.00", "amount")
        type_converter.convert_value("$2.00", "amount")
        
        # This should clear the cache
        type_converter.convert_value("$3.00", "amount")
        
        # Original value should be recomputed
        assert type_converter.convert_value("$1.00", "amount") == 1.0