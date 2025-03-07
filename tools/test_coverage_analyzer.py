"""Test coverage analyzer."""
import os
import sys
import xml.etree.ElementTree as ET
import json
from collections import defaultdict
import re
from pathlib import Path

class TestCoverageAnalyzer:
    def __init__(self, coverage_file='output/reports/coverage/coverage.xml', source_dir='src', output_dir='output/reports/coverage'):
        self.coverage_file = coverage_file
        self.source_dir = source_dir
        self.output_dir = Path(output_dir)
        self.modules = defaultdict(dict)
        self.test_mapping = defaultdict(list)
        
    def parse_coverage(self):
        """Parse the coverage.xml file"""
        tree = ET.parse(self.coverage_file)
        root = tree.getroot()
        
        for pkg in root.findall('.//package'):
            pkg_name = pkg.get('name')
            for cls in pkg.findall('classes/class'):
                filename = cls.get('filename')
                self.modules[pkg_name][filename] = {
                    'line_rate': float(cls.get('line-rate')),
                    'lines_total': sum(1 for _ in cls.findall('.//line')),
                    'lines_covered': sum(1 for l in cls.findall('.//line') if l.get('hits') != '0'),
                    'uncovered_lines': [int(l.get('number')) for l in cls.findall('.//line') if l.get('hits') == '0']
                }
    
    def map_tests_to_modules(self):
        """Map test files to the modules they test"""
        for root, _, files in os.walk('tests'):
            for file in files:
                if file.startswith('test_') and file.endswith('.py'):
                    test_path = os.path.join(root, file)
                    with open(test_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Look for imports or references to modules
                        for pkg_name, modules in self.modules.items():
                            for module_file in modules.keys():
                                module_name = os.path.basename(module_file).replace('.py', '')
                                if re.search(rf'import.*{module_name}|from.*{module_name}', content):
                                    self.test_mapping[module_file].append(test_path)
    
    def identify_uncovered_components(self):
        """Identify modules with low coverage or no tests"""
        uncovered = []
        
        for pkg_name, modules in self.modules.items():
            for module_file, stats in modules.items():
                if stats['line_rate'] < 0.8:  # Less than 80% coverage
                    tests = self.test_mapping.get(module_file, [])
                    uncovered.append({
                        'module': module_file,
                        'coverage': stats['line_rate'],
                        'lines_total': stats['lines_total'],
                        'lines_covered': stats['lines_covered'],
                        'uncovered_lines': stats['uncovered_lines'],
                        'test_files': tests,
                        'missing_tests': len(tests) == 0
                    })
        
        return sorted(uncovered, key=lambda x: x['coverage'])
    
    def analyze(self):
        """Run the full analysis"""
        self.parse_coverage()
        self.map_tests_to_modules()
        return self.identify_uncovered_components()
    
    def generate_report(self):
        """Generate a JSON report file"""
        uncovered = self.analyze()
        
        report = {
            'timestamp': __import__('datetime').datetime.now().isoformat(),
            'overall_coverage': sum(m['lines_covered'] for pkg in self.modules.values() 
                                for m in pkg.values()) / sum(m['lines_total'] 
                                for pkg in self.modules.values() for m in pkg.values()),
            'modules_without_tests': [m['module'] for m in uncovered if m['missing_tests']],
            'low_coverage_modules': [m for m in uncovered if not m['missing_tests']],
            'action_items': [{
                'module': m['module'],
                'priority': 'high' if m['missing_tests'] else 'medium' if m['coverage'] < 0.5 else 'low',
                'recommendation': 'Create tests' if m['missing_tests'] else f'Improve coverage for lines: {m["uncovered_lines"][:5]}...'
            } for m in uncovered]
        }
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save to the configured output directory
        output_file = self.output_dir / 'coverage_report.json'
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        return report

if __name__ == '__main__':
    analyzer = TestCoverageAnalyzer()
    report = analyzer.generate_report()
    print(f"Overall coverage: {report['overall_coverage']:.2%}")
    print(f"{len(report['modules_without_tests'])} modules without tests")
    print(f"{len(report['low_coverage_modules'])} modules with low coverage")