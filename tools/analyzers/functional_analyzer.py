"""Functional coverage analysis implementation."""

import os
import ast
from collections import defaultdict
from pathlib import Path
from typing import Dict, Optional

from ..common import BaseReport, DirectoryHelper

class FunctionalCoverageAnalyzer(BaseReport):
    """Analyze functional test coverage by parsing implementation and test files."""
    
    def __init__(self, src_dir: str = 'src', test_dir: str = 'tests', output_dir: Optional[str] = None):
        if not output_dir:
            output_dir = str(DirectoryHelper.get_results_dir())
        super().__init__(output_dir)
        self.src_dir = src_dir
        self.test_dir = test_dir
        self.functions = {}
        self.test_functions = defaultdict(list)
    
    def extract_functions(self):
        """Extract all functions from source files"""
        for root, _, files in os.walk(self.src_dir):
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    module_name = os.path.relpath(filepath, self.src_dir).replace('\\', '.').replace('/', '.').replace('.py', '')
                    
                    with open(filepath, 'r', encoding='utf-8') as f:
                        try:
                            tree = ast.parse(f.read())
                            for node in ast.walk(tree):
                                if isinstance(node, ast.FunctionDef) or isinstance(node, ast.ClassDef):
                                    full_name = f"{module_name}.{node.name}"
                                    self.functions[full_name] = {
                                        'file': filepath,
                                        'line_number': node.lineno,
                                        'is_public': not node.name.startswith('_'),
                                        'docstring': ast.get_docstring(node) or ""
                                    }
                        except SyntaxError:
                            print(f"Syntax error in {filepath}")
    
    def extract_test_references(self):
        """Extract test functions and what they appear to test"""
        for root, _, files in os.walk(self.test_dir):
            for file in files:
                if file.startswith('test_') and file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    impl_name = file[5:] if file.startswith('test_') else file
                    impl_module = impl_name[:-3]
                    
                    with open(filepath, 'r', encoding='utf-8') as f:
                        try:
                            tree = ast.parse(f.read())
                            for node in ast.walk(tree):
                                if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                                    # Find function being tested by analyzing the test code
                                    function_name = node.name[5:]  # Remove 'test_' prefix
                                    self.test_functions[impl_module].append(function_name)
                        except SyntaxError:
                            print(f"Syntax error in {filepath}")
    
    def calculate_feature_coverage(self, features: Dict) -> Dict:
        """Calculate coverage percentages for features recursively"""
        if not features:
            return features
            
        for feature in features.values():
            if "scenarios" in feature:
                total = len(feature["scenarios"])
                covered = sum(1 for s in feature["scenarios"] if s.get("automated", False))
                feature["coverage_percent"] = (covered / total * 100) if total > 0 else 0
            
            if "subfeatures" in feature:
                self.calculate_feature_coverage(feature["subfeatures"])
        
        return features
    
    def generate_report(self):
        """Generate functional coverage report"""
        self.extract_functions()
        self.extract_test_references()
        
        # Organize functions into feature hierarchy
        features = {}
        for func_name, func_info in self.functions.items():
            if not func_info['is_public']:
                continue
                
            path_parts = func_name.split('.')
            current = features
            
            # Build nested feature structure
            for part in path_parts[:-1]:
                if part not in current:
                    current[part] = {"scenarios": [], "subfeatures": {}}
                elif "subfeatures" not in current[part]:
                    current[part]["subfeatures"] = {}
                current = current[part]["subfeatures"]
            feature = path_parts[-2] if len(path_parts) > 1 else "root"
            if feature not in current:
                current[feature] = {"scenarios": [], "subfeatures": {}}
            
            current[feature]["scenarios"].append({
                "name": path_parts[-1],
                "automated": any(func_name in tests for tests in self.test_functions.values()),
                "coverage": 100 if any(func_name in tests for tests in self.test_functions.values()) else 0
            })
        
        # Calculate coverage percentages
        features = self.calculate_feature_coverage(features)
        
        report = {
            'features': features,
            'total_functions': len(self.functions),
            'covered_functions': sum(1 for func in self.functions if any(
                func in tests for tests in self.test_functions.values()
            )),
            'functional_coverage': sum(
                1 for func in self.functions if any(func in tests for tests in self.test_functions.values())
            ) / len(self.functions) if self.functions else 0
        }
        
        # Save directly to results directory
        self.save_report(report, 'functional_coverage_report.json')
        return report