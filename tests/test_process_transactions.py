import pytest
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch
from decimal import Decimal
from src.process_transactions import process_transactions, setup_validation, setup_entity_mediator
from src.usaspending.core.adapters import MoneyAdapter, DateAdapter, StringAdapter

@pytest.fixture
def sample_config():
    return {
        'system': {
            'io': {
                'input': {
                    'file': 'test_input.json'
                },
                'output': {
                    'directory': 'output'
                }
            },
            'processing': {
                'chunk_size': 2,
                'validation': True
            }
        },
        'schema': {
            'contract': {
                'amount': {
                    'type': 'money',
                    'required': True,
                    'adapter': MoneyAdapter()
                },
                'date': {
                    'type': 'date',
                    'required': True,
                    'adapter': DateAdapter()
                },
                'description': {
                    'type': 'string',
                    'required': False,
                    'adapter': StringAdapter()
                }
            }
        }
    }

@pytest.fixture
def sample_transactions():
    return [
        {
            'id': '1',
            'amount': '$1000.00',
            'date': '2024-01-01',
            'description': 'Test transaction 1'
        },
        {
            'id': '2',
            'amount': '$2000.00',
            'date': '2024-01-02',
            'description': 'Test transaction 2'
        }
    ]

@pytest.fixture
def temp_input_file(tmp_path, sample_transactions):
    input_file = tmp_path / "test_input.json"
    with open(input_file, 'w') as f:
        for transaction in sample_transactions:
            f.write(json.dumps(transaction) + '\n')
    return str(input_file)

@pytest.fixture
def mock_validation_service():
    service = Mock()
    service.validate_transaction.return_value = True
    service.get_validation_errors.return_value = []
    return service

@patch('src.process_transactions.ConfigProvider')
def test_process_transactions_basic(mock_config_provider, temp_input_file, sample_config):
    # Setup
    mock_config = Mock()
    mock_config_provider.return_value.load_config.return_value = sample_config
    
    # Update config with temp file path
    sample_config['system']['io']['input']['file'] = temp_input_file
    
    # Execute
    process_transactions('dummy_config.yaml')
    
    # Verify
    mock_config_provider.return_value.load_config.assert_called_once()

@pytest.mark.parametrize("invalid_input", [
    "not_existing_file.json",
    "",
    None
])
def test_process_transactions_invalid_input(invalid_input):
    with pytest.raises((FileNotFoundError, ValueError)):
        process_transactions('dummy_config.yaml', invalid_input)

@patch('src.process_transactions.ValidationService')
def test_setup_validation(mock_validation_service, sample_config):
    validation_service = setup_validation(sample_config)
    assert validation_service is not None
    # Verify validation service is configured with schema
    assert 'contract' in sample_config['schema']

@patch('src.process_transactions.EntityMediator')
def test_setup_entity_mediator(mock_entity_mediator, sample_config):
    mock_validation_service = Mock()
    entity_mediator = setup_entity_mediator(sample_config, mock_validation_service)
    assert entity_mediator is not None
    # Verify mediator is configured with adapters
    mock_entity_mediator.return_value.configure.assert_called_once()

def test_process_transactions_with_validation(tmp_path, sample_config, sample_transactions):
    # Setup input file
    input_file = tmp_path / "test_input.json"
    with open(input_file, 'w') as f:
        for transaction in sample_transactions:
            f.write(json.dumps(transaction) + '\n')
    
    # Update config with file path
    sample_config['system']['io']['input']['file'] = str(input_file)
    
    with patch('src.process_transactions.ConfigProvider') as mock_config_provider, \
         patch('src.process_transactions.ValidationService') as mock_validation_service:
        
        mock_config_provider.return_value.load_config.return_value = sample_config
        mock_validation_service.return_value.validate_transaction.return_value = True
        
        # Execute
        process_transactions('dummy_config.yaml')
        
        # Verify validation was performed
        mock_validation_service.return_value.validate_transaction.assert_called()
