"""Tests for type conversion functionality."""
import pytest
from datetime import datetime, date
from unittest.mock import Mock
from decimal import Decimal

from usaspending.utils import TypeConverter  # TypeConverter is in utils.py, not type_converter.py

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

import pytest
from usaspending.utils import TypeConverter

def test_money_conversion():
    # Add test logic here
    pass

def test_decimal_conversion():
    # Add test logic here
    pass

def test_integer_conversion():
    # Add test logic here
    pass

def test_standard_date_format():
    # Add test logic here
    pass

def test_dynamic_date_fields():
    # Add test logic here
    pass

def test_true_values():
    # Add test logic here
    pass

def test_false_values():
    # Add test logic here
    pass

def test_invalid_boolean():
    # Add test logic here
    pass

def test_phone_validation():
    # Add test logic here
    pass

def test_email_validation():
    # Add test logic here
    pass

def test_zip_validation():
    # Add test logic here
    pass

def test_url_validation():
    # Add test logic here
    pass

def test_phone_conversion():
    # Add test logic here
    pass

def test_zip_conversion():
    # Add test logic here
    pass

def test_cache_hit():
    # Add test logic here
    pass

def test_cache_size_limit():
    # Add test logic here
    pass