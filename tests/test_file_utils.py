"""Tests for file utility functions."""
import os
import pytest
import tempfile
from usaspending.core.file_utils import (
    ensure_directory,
    safe_file_write,
    chunked_file_read,
    get_file_hash
)

@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield tmpdirname

def test_ensure_directory(temp_dir):
    """Test directory creation."""
    test_dir = os.path.join(temp_dir, 'test_dir')
    assert not os.path.exists(test_dir)
    
    ensure_directory(test_dir)
    assert os.path.exists(test_dir)
    assert os.path.isdir(test_dir)

def test_safe_file_write(temp_dir):
    """Test safe file writing."""
    test_file = os.path.join(temp_dir, 'test.txt')
    test_content = 'Test content\nLine 2'
    
    # Write file
    safe_file_write(test_file, test_content)
    assert os.path.exists(test_file)
    
    # Verify content
    with open(test_file, 'r') as f:
        content = f.read()
    assert content == test_content

def test_chunked_file_read(temp_dir):
    """Test reading file in chunks."""
    test_file = os.path.join(temp_dir, 'large.txt')
    test_content = 'Line ' * 1000  # Create some content
    
    # Write test file
    with open(test_file, 'w') as f:
        f.write(test_content)
    
    # Read in chunks
    content = []
    for chunk in chunked_file_read(test_file, chunk_size=100):
        content.append(chunk)
    
    assert ''.join(content) == test_content
    assert len(content) > 1  # Verify it was actually chunked

def test_get_file_hash(temp_dir):
    """Test file hash calculation."""
    test_file = os.path.join(temp_dir, 'hash_test.txt')
    test_content = 'Test content for hashing'
    
    # Write test file
    with open(test_file, 'w') as f:
        f.write(test_content)
    
    # Calculate hash
    file_hash = get_file_hash(test_file)
    assert file_hash  # Hash should not be empty
    assert isinstance(file_hash, str)
    assert len(file_hash) == 64  # SHA-256 hash length