"""Tests for the functional_coverage_analyzer module."""
import unittest
from pathlib import Path
import tempfile
import json
import os
import shutil

from tools.functional_coverage_analyzer import FunctionalCoverageAnalyzer

class TestFunctionalCoverageAnalyzer(unittest.TestCase):
    def setUp(self):
        # Create temporary directories for testing
        self.temp_dir = tempfile.mkdtemp()
        self.src_dir = Path(self.temp_dir) / "src"
        self.test_dir = Path(self.temp_dir) / "tests"
        self.output_dir = Path(self.temp_dir) / "output"
        
        self.src_dir.mkdir()
        self.test_dir.mkdir()
        self.output_dir.mkdir()
        
        # Create some sample Python files for testing
        self._create_test_files()
        
        # Initialize the analyzer with our test directories
        self.analyzer = FunctionalCoverageAnalyzer(
            src_dir=str(self.src_dir),
            test_dir=str(self.test_dir),
            output_dir=str(self.output_dir)
        )
    
    def tearDown(self):
        # Clean up temp directory
        shutil.rmtree(self.temp_dir)
    
    def _create_test_files(self):
        # Create a sample source file with a couple of functions
        sample_src = self.src_dir / "sample.py"
        with open(sample_src, "w") as f:
            f.write("""
def public_function():
    \"\"\"This is a public function\"\"\"
    return True

def _private_function():
    return False

class SampleClass:
    def method_with_test(self):
        \"\"\"This method has a test\"\"\"
        return True
        
    def method_without_test(self):
        \"\"\"This method has no test\"\"\"
        return False
""")

        # Create a test file that tests some, but not all, of the functions
        sample_test = self.test_dir / "test_sample.py"
        with open(sample_test, "w") as f:
            f.write("""
import unittest
from src.sample import public_function, SampleClass

class TestSample(unittest.TestCase):
    def test_public_function(self):
        self.assertTrue(public_function())
        
    def test_sample_class_method(self):
        sample = SampleClass()
        self.assertTrue(sample.method_with_test())
""")

    def test_extract_functions(self):
        """Test that functions are correctly extracted from source files."""
        self.analyzer.extract_functions()
        
        # Verify we found the expected functions
        self.assertIn("sample.public_function", self.analyzer.functions)
        self.assertIn("sample._private_function", self.analyzer.functions)
        self.assertIn("sample.SampleClass", self.analyzer.functions)
        
        # Check function details
        self.assertTrue(self.analyzer.functions["sample.public_function"]["is_public"])
        self.assertFalse(self.analyzer.functions["sample._private_function"]["is_public"])
        self.assertTrue(self.analyzer.functions["sample.public_function"]["docstring"])
    
    def test_extract_test_references(self):
        """Test that test functions are correctly extracted and matched."""
        self.analyzer.extract_functions()
        self.analyzer.extract_test_references()
        
        # Verify test references
        self.assertIn("sample.public_function", self.analyzer.test_functions)
        self.assertNotIn("sample._private_function", self.analyzer.test_functions)
        
        # There should be test references for the method with test
        self.assertTrue(any("sample.SampleClass.method_with_test" in func_name 
                          for func_name in self.analyzer.test_functions))
    
    def test_identify_untested_functions(self):
        """Test identification of untested functions."""
        untested = self.analyzer.analyze()
        
        # Extract function names from the report for easier testing
        untested_names = [item["function"] for item in untested]
        
        # The private function should not be in untested (as it's private)
        self.assertNotIn("sample._private_function", untested_names)
        
        # The method without test should be listed as untested
        self.assertTrue(any("method_without_test" in name for name in untested_names))
        
        # The method with test should not be listed as untested
        self.assertFalse(any("method_with_test" in name for name in untested_names))
    
    def test_generate_report(self):
        """Test that report generation works and creates a valid JSON file."""
        report = self.analyzer.generate_report()
        
        # Check the report structure
        self.assertIn("total_public_functions", report)
        self.assertIn("untested_functions", report)
        self.assertIn("functional_coverage", report)
        
        # Verify that the report file was created
        report_file = Path(self.output_dir) / "functional_coverage_report.json"
        self.assertTrue(report_file.exists())
        
        # Check that the file contains valid JSON
        with open(report_file) as f:
            loaded_report = json.load(f)
            self.assertEqual(report["total_public_functions"], loaded_report["total_public_functions"])


if __name__ == "__main__":
    unittest.main()