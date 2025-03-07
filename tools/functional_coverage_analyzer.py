#!/usr/bin/env python
"""Tool for analyzing gaps in test coverage by comparing implementation and test files."""
import os
import sys
import re
from collections import defaultdict
from pathlib import Path
import ast
import json
from datetime import datetime

class FunctionalCoverageAnalyzer:
    def __init__(self, src_dir='src/usaspending', test_dir='tests', output_dir='output/reports/coverage'):
        self.src_dir = src_dir
        self.test_dir = test_dir
        self.output_dir = Path(output_dir)
        self.functions = {}
        self.test_functions = defaultdict(list)
        print(f"Initializing analyzer with src_dir={src_dir}, test_dir={test_dir}")
        
    def extract_functions(self):
        """Extract all functions from source files"""
        print("Extracting functions from source files...")
        for root, _, files in os.walk(self.src_dir):
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    print(f"Processing file: {filepath}")
                    module_name = os.path.relpath(filepath, self.src_dir).replace('\\', '.').replace('/', '.').replace('.py', '')
                    
                    with open(filepath, 'r', encoding='utf-8') as f:
                        try:
                            tree = ast.parse(f.read())
                            for node in ast.walk(tree):
                                if isinstance(node, ast.FunctionDef) or isinstance(node, ast.ClassDef):
                                    full_name = f"{module_name}.{node.name}"
                                    
                                    # Determine if public or private
                                    is_public = not node.name.startswith('_')
                                    
                                    # Get docstring if available
                                    docstring = ast.get_docstring(node) or ""
                                    
                                    self.functions[full_name] = {
                                        'file': filepath,
                                        'name': node.name,
                                        'is_public': is_public,
                                        'docstring': docstring,
                                        'line_number': node.lineno,
                                    }
                        except SyntaxError:
                            print(f"Syntax error in {filepath}")
    
    def extract_test_references(self):
        """Extract test functions and what they appear to test"""
        print("Extracting test references...")
        for root, _, files in os.walk(self.test_dir):
            for file in files:
                if file.startswith('test_') and file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    print(f"Processing test file: {filepath}")
                    
                    # Guess corresponding implementation file
                    impl_name = file[5:] if file.startswith('test_') else file  # Remove test_ prefix
                    impl_module = impl_name[:-3]  # Remove .py
                    
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                        # Parse the file to get test functions
                        try:
                            tree = ast.parse(content)
                            for node in ast.walk(tree):
                                if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                                    test_name = node.name
                                    test_body = content[node.lineno:node.end_lineno]
                                    
                                    # Match functions from corresponding implementation module first
                                    for func_name, func_info in self.functions.items():
                                        if impl_module in func_name:
                                            self.test_functions[func_name].append({
                                                'test_file': filepath,
                                                'test_name': test_name,
                                                'test_line_number': node.lineno
                                            })
                                            continue
                                            
                                    # Then look for explicit references
                                    for func_name, func_info in self.functions.items():
                                        short_name = func_name.split('.')[-1]
                                        class_name = func_name.split('.')[-2] if '.' in func_name else None
                                        
                                        patterns = [
                                            rf'\b{short_name}\s*\(',  # Function call
                                            rf'\b{func_name}\b',      # Full qualified name
                                            rf'\b{short_name}\b'      # Function name in docstring/comment
                                        ]
                                        
                                        if class_name:
                                            patterns.append(rf'\b{class_name}\.{short_name}\b')  # Class method call
                                            
                                        if any(re.search(pattern, test_body) for pattern in patterns):
                                            self.test_functions[func_name].append({
                                                'test_file': filepath,
                                                'test_name': test_name,
                                                'test_line_number': node.lineno
                                            })
                        except SyntaxError:
                            print(f"Syntax error in {filepath}")
    
    def identify_untested_functions(self):
        """Identify public functions without tests"""
        untested_functions = []
        
        for func_name, func_info in self.functions.items():
            if func_info['is_public'] and func_name not in self.test_functions:
                untested_functions.append({
                    'function': func_name,
                    'file': func_info['file'],
                    'line_number': func_info['line_number'],
                    'has_docstring': bool(func_info['docstring'])
                })
        
        return sorted(untested_functions, key=lambda x: x['file'])
    
    def analyze(self):
        """Run the full analysis"""
        self.extract_functions()
        self.extract_test_references()
        return self.identify_untested_functions()
    
    def generate_report(self):
        """Generate a JSON report file"""
        untested = self.analyze()
        
        # Count public functions
        public_functions = [f for f, info in self.functions.items() if info['is_public']]
        
        report = {
            'timestamp': __import__('datetime').datetime.now().isoformat(),
            'total_public_functions': len(public_functions),
            'tested_functions': len(public_functions) - len(untested),
            'untested_functions': len(untested),
            'functional_coverage': (len(public_functions) - len(untested)) / len(public_functions) if public_functions else 0,
            'untested_functions_list': untested,
            'action_items': [{
                'function': func['function'],
                'file': func['file'],
                'line_number': func['line_number'],
                'priority': 'high' if not func['has_docstring'] else 'medium',
                'recommendation': 'Create tests for this function'
            } for func in untested]
        }
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_file = self.output_dir / 'functional_coverage_report.json'
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        return report

if __name__ == '__main__':
    analyzer = FunctionalCoverageAnalyzer()
    report = analyzer.generate_report()
    print(f"Functional coverage: {report['functional_coverage']:.2%}")
    print(f"{report['untested_functions']} of {report['total_public_functions']} public functions untested")