"""Tests for the coverage, quality, gap and functional analyzers."""

import pytest

from src.tools.analyzers.coverage_analyzer import CoverageAnalyzer
from src.tools.analyzers.quality_analyzer import TestQualityAnalyzer
from src.tools.analyzers.gap_analyzer import TestGapAnalyzer
from src.tools.analyzers.functional_analyzer import FunctionalCoverageAnalyzer

@pytest.fixture
def coverage_xml():
    """Sample coverage XML data."""
    return '''<?xml version="1.0" ?>
    <coverage version="1.0">
        <packages>
            <package name="src.usaspending">
                <classes>
                    <class name="processor.py">
                        <lines>
                            <line hits="1" number="1"/>
                            <line hits="1" number="2"/>
                            <line hits="0" number="3"/>
                        </lines>
                    </class>
                </classes>
            </package>
        </packages>
    </coverage>'''

@pytest.fixture
def test_files():
    """Sample test files content."""
    return {
        'test_a.py': '''
def test_function():
    assert True
    assert 1 == 1

@pytest.mark.parametrize("input,expected", [(1,1), (2,2)])
def test_parametrized():
    assert input == expected
''',
        'test_b.py': '''
def test_simple():
    x = 1
    assert x == 1
'''
    }

def test_coverage_analyzer(tmp_path, coverage_xml):
    """Test CoverageAnalyzer functionality."""
    # Create coverage XML file
    xml_file = tmp_path / "coverage.xml"
    xml_file.write_text(coverage_xml)
    
    analyzer = CoverageAnalyzer(str(xml_file))
    report = analyzer.generate_report()
    
    assert report['total_files'] == 1
    assert 'files' in report
    assert 'processor.py' in str(report['files'])
    assert report['coverage_percent'] > 0

def test_quality_analyzer(tmp_path, test_files):
    """Test TestQualityAnalyzer functionality."""
    # Create test files
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    for name, content in test_files.items():
        (test_dir / name).write_text(content)
    
    analyzer = TestQualityAnalyzer(str(test_dir))
    report = analyzer.generate_report()
    
    assert report['total_test_files'] == 2
    assert 'test_files' in report
    assert report['overall_quality_score'] > 0

def test_gap_analyzer(tmp_path):
    """Test TestGapAnalyzer functionality."""
    # Create sample implementation and test files
    src_dir = tmp_path / "src"
    test_dir = tmp_path / "tests"
    src_dir.mkdir()
    test_dir.mkdir()
    
    # Implementation files
    (src_dir / "module_a.py").touch()
    (src_dir / "module_b.py").touch()
    
    # Test file (only for module_a)
    (test_dir / "test_module_a.py").touch()
    
    analyzer = TestGapAnalyzer(str(src_dir), str(test_dir))
    report = analyzer.generate_report()
    
    assert 'gaps' in report
    assert len(report['gaps']) == 1
    assert 'module_b.py' in report['gaps']

def test_functional_analyzer(tmp_path):
    """Test FunctionalCoverageAnalyzer functionality."""
    # Create sample implementation files
    src_dir = tmp_path / "src"
    test_dir = tmp_path / "tests"
    src_dir.mkdir()
    test_dir.mkdir()
    
    # Implementation with functions
    (src_dir / "module.py").write_text('''
def public_function():
    pass

def _private_function():
    pass
''')
    
    # Test file that references the public function
    (test_dir / "test_module.py").write_text('''
def test_public_function():
    public_function()
''')
    
    analyzer = FunctionalCoverageAnalyzer(str(src_dir), str(test_dir))
    report = analyzer.generate_report()
    
    assert 'features' in report
    assert report['total_functions'] > 0
    assert report['covered_functions'] > 0
    assert report['functional_coverage'] > 0
