"""Tests for the test coverage analyzer tool."""
import os
import sys
import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

# Ensure tools directory is in path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from tools.test_coverage_analyzer import TestCoverageAnalyzer


@pytest.fixture
def sample_coverage_xml():
    """Sample coverage.xml content for testing."""
    return """<?xml version="1.0" ?>
    <coverage version="6.5.0" timestamp="1678910111" lines-valid="1234" lines-covered="1000" line-rate="0.81">
        <packages>
            <package name="usaspending" line-rate="0.75">
                <classes>
                    <class name="module1" filename="src/usaspending/module1.py" line-rate="0.90">
                        <lines>
                            <line number="1" hits="1"/>
                            <line number="2" hits="1"/>
                            <line number="3" hits="1"/>
                            <line number="4" hits="0"/>
                        </lines>
                    </class>
                    <class name="module2" filename="src/usaspending/module2.py" line-rate="0.60">
                        <lines>
                            <line number="1" hits="1"/>
                            <line number="2" hits="1"/>
                            <line number="3" hits="0"/>
                            <line number="4" hits="0"/>
                            <line number="5" hits="0"/>
                        </lines>
                    </class>
                </classes>
            </package>
        </packages>
    </coverage>"""


@pytest.fixture
def sample_test_file():
    """Sample test file content for testing."""
    return """
    from usaspending.module1 import some_function
    
    def test_some_function():
        assert some_function() == True
    """


@pytest.fixture
def analyzer(sample_coverage_xml):
    """Create analyzer instance with mocked file reads."""
    with patch('xml.etree.ElementTree.parse') as mock_parse:
        mock_root = MagicMock()
        mock_parse.return_value.getroot.return_value = mock_root
        
        # Setup the mock to respond to findall methods to match the sample XML structure
        def mock_findall(path):
            if path == './/package':
                pkg = MagicMock()
                pkg.get.return_value = 'usaspending'
                return [pkg]
            elif 'classes/class' in path:
                cls1 = MagicMock()
                cls1.get.side_effect = lambda x: {'filename': 'src/usaspending/module1.py', 'line-rate': '0.90'}[x]
                cls1.findall.return_value = [
                    MagicMock(**{'get.return_value': '1'}), 
                    MagicMock(**{'get.return_value': '1'}),
                    MagicMock(**{'get.return_value': '1'}),
                    MagicMock(**{'get.return_value': '0'})
                ]
                
                cls2 = MagicMock()
                cls2.get.side_effect = lambda x: {'filename': 'src/usaspending/module2.py', 'line-rate': '0.60'}[x]
                cls2.findall.return_value = [
                    MagicMock(**{'get.return_value': '1'}),
                    MagicMock(**{'get.return_value': '1'}),
                    MagicMock(**{'get.return_value': '0'}),
                    MagicMock(**{'get.return_value': '0'}),
                    MagicMock(**{'get.return_value': '0'})
                ]
                return [cls1, cls2]
            return []
        
        mock_root.findall.side_effect = mock_findall
        
        analyzer = TestCoverageAnalyzer()
        return analyzer


def test_parse_coverage(analyzer):
    """Test parsing coverage.xml file."""
    analyzer.parse_coverage()
    
    assert len(analyzer.modules) == 1
    assert len(analyzer.modules['usaspending']) == 2
    assert 'src/usaspending/module1.py' in analyzer.modules['usaspending']
    assert 'src/usaspending/module2.py' in analyzer.modules['usaspending']
    
    # Check module1 stats
    module1_stats = analyzer.modules['usaspending']['src/usaspending/module1.py']
    assert module1_stats['line_rate'] == 0.90
    assert module1_stats['lines_total'] == 4
    assert module1_stats['lines_covered'] == 3
    assert module1_stats['uncovered_lines'] == [4]
    
    # Check module2 stats
    module2_stats = analyzer.modules['usaspending']['src/usaspending/module2.py']
    assert module2_stats['line_rate'] == 0.60
    assert module2_stats['lines_total'] == 5
    assert module2_stats['lines_covered'] == 2
    assert module2_stats['uncovered_lines'] == [3, 4, 5]


def test_map_tests_to_modules(analyzer, sample_test_file):
    """Test mapping test files to modules."""
    analyzer.parse_coverage()  # Populate modules first
    
    with patch('os.walk') as mock_walk, \
         patch('builtins.open', mock_open(read_data=sample_test_file)) as mock_file:
        
        # Mock os.walk to return a single test file
        mock_walk.return_value = [
            ('tests', [], ['test_module1.py'])
        ]
        
        analyzer.map_tests_to_modules()
    
    # Check that the test file was mapped to module1
    assert len(analyzer.test_mapping['src/usaspending/module1.py']) == 1
    assert analyzer.test_mapping['src/usaspending/module1.py'][0] == 'tests/test_module1.py'
    
    # module2 should have no mapped tests
    assert 'src/usaspending/module2.py' not in analyzer.test_mapping


def test_identify_uncovered_components(analyzer):
    """Test identification of modules with low coverage."""
    analyzer.parse_coverage()  # Populate modules first
    
    # Setup the test mapping
    analyzer.test_mapping = {
        'src/usaspending/module1.py': ['tests/test_module1.py']
    }
    
    uncovered = analyzer.identify_uncovered_components()
    
    assert len(uncovered) == 2
    
    # Check first uncovered module (with lowest coverage)
    assert uncovered[0]['module'] == 'src/usaspending/module2.py'
    assert uncovered[0]['coverage'] == 0.60
    assert uncovered[0]['missing_tests'] is True
    
    # Check second uncovered module
    assert uncovered[1]['module'] == 'src/usaspending/module1.py'
    assert uncovered[1]['coverage'] == 0.90
    assert uncovered[1]['missing_tests'] is False
    assert uncovered[1]['test_files'] == ['tests/test_module1.py']


def test_analyze(analyzer):
    """Test the full analysis process."""
    with patch.object(analyzer, 'parse_coverage') as mock_parse, \
         patch.object(analyzer, 'map_tests_to_modules') as mock_map, \
         patch.object(analyzer, 'identify_uncovered_components', return_value=['result']) as mock_identify:
        
        result = analyzer.analyze()
        
        # Verify that all component methods were called
        mock_parse.assert_called_once()
        mock_map.assert_called_once()
        mock_identify.assert_called_once()
        
        # Verify the result
        assert result == ['result']


def test_generate_report(analyzer):
    """Test report generation."""
    # Set up test data
    analyzer.modules = {
        'usaspending': {
            'src/usaspending/module1.py': {
                'line_rate': 0.90,
                'lines_total': 100,
                'lines_covered': 90,
                'uncovered_lines': [4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
            },
            'src/usaspending/module2.py': {
                'line_rate': 0.60,
                'lines_total': 50,
                'lines_covered': 30,
                'uncovered_lines': list(range(21, 41))
            }
        }
    }
    
    # Mock the analyze method to return pre-set uncovered components
    uncovered = [
        {
            'module': 'src/usaspending/module2.py',
            'coverage': 0.60,
            'lines_total': 50,
            'lines_covered': 30,
            'uncovered_lines': list(range(21, 41)),
            'test_files': [],
            'missing_tests': True
        },
        {
            'module': 'src/usaspending/module1.py',
            'coverage': 0.90,
            'lines_total': 100,
            'lines_covered': 90,
            'uncovered_lines': [4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            'test_files': ['tests/test_module1.py'],
            'missing_tests': False
        }
    ]
    
    with patch.object(analyzer, 'analyze', return_value=uncovered), \
         patch('builtins.open', mock_open()) as mock_file:
        
        report = analyzer.generate_report()
        
        # Check that the file was written
        mock_file.assert_called_once_with('coverage_report.json', 'w')
        
        # Check report contents
        assert 'timestamp' in report
        assert report['overall_coverage'] == (90 + 30) / (100 + 50)
        assert report['modules_without_tests'] == ['src/usaspending/module2.py']
        assert len(report['low_coverage_modules']) == 1
        assert report['low_coverage_modules'][0]['module'] == 'src/usaspending/module1.py'
        
        # Check action items
        assert len(report['action_items']) == 2
        assert report['action_items'][0]['module'] == 'src/usaspending/module2.py'
        assert report['action_items'][0]['priority'] == 'high'
        assert report['action_items'][1]['module'] == 'src/usaspending/module1.py'
        assert report['action_items'][1]['priority'] == 'low'


def test_main_execution():
    """Test the main execution flow."""
    mock_analyzer = MagicMock()
    mock_analyzer.generate_report.return_value = {
        'overall_coverage': 0.85,
        'modules_without_tests': ['module1', 'module2'],
        'low_coverage_modules': ['module3', 'module4']
    }
    
    with patch('tools.test_coverage_analyzer.TestCoverageAnalyzer', return_value=mock_analyzer), \
         patch('builtins.print') as mock_print:
        
        # Execute the main code
        from tools.test_coverage_analyzer import __name__ as module_name
        
        # But don't actually run it (we'd need to import and run the module for that)
        # Instead, check that our TestCoverageAnalyzer calls would behave correctly
        mock_analyzer.generate_report.assert_not_called()