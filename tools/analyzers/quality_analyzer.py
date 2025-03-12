"""Quality analysis implementation."""

import os
import ast
from pathlib import Path
from typing import Dict, List, Optional

from ..common import BaseReport, DirectoryHelper

class TestQualityAnalyzer(BaseReport):
    """Analyze test files for quality metrics."""
    
    def __init__(self, test_dir: str = 'tests', output_dir: Optional[str] = None):
        if not output_dir:
            output_dir = str(DirectoryHelper.get_results_dir())
        super().__init__(output_dir)
        self.test_dir = test_dir
        self.test_files = []
        self.test_stats = {}
    
    def gather_test_files(self):
        """Find all test files"""
        for root, _, files in os.walk(self.test_dir):
            for file in files:
                if file.startswith('test_') and file.endswith('.py'):
                    self.test_files.append(os.path.join(root, file))
    
    def analyze_test_file(self, file_path: str) -> Optional[Dict]:
        """Analyze a single test file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        try:
            tree = ast.parse(content)
            
            stats = {
                'file': file_path,
                'test_count': 0,
                'assertion_count': 0,
                'fixtures_used': [],
                'parametrized_tests': 0,
                'mocks_used': 0,
                'test_complexity': {},
                'quality_score': 0
            }
            
            # Analyze test functions
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                    stats = self._analyze_test_function(node, stats)
            
            # Calculate quality score
            if stats['test_count'] > 0:
                stats['quality_score'] = self._calculate_quality_score(stats)
            
            return stats
            
        except SyntaxError:
            print(f"Syntax error in {file_path}")
            return None
    
    def _analyze_test_function(self, node: ast.FunctionDef, stats: Dict) -> Dict:
        """Analyze a test function node"""
        stats['test_count'] += 1
        
        # Check for parametrize decorator
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                if decorator.func.attr == 'parametrize':
                    stats['parametrized_tests'] += 1
        
        # Count assertions and mocks
        assertions = 0
        mocks = 0
        for subnode in ast.walk(node):
            if isinstance(subnode, ast.Assert):
                assertions += 1
            elif isinstance(subnode, ast.Call):
                if hasattr(subnode.func, 'attr') and subnode.func.attr in ['patch', 'Mock', 'MagicMock']:
                    mocks += 1
        
        stats['assertion_count'] += assertions
        stats['mocks_used'] += mocks
        stats['test_complexity'][node.name] = {
            'assertions': assertions,
            'uses_mocks': mocks > 0,
            'line_count': node.end_lineno - node.lineno
        }
        
        return stats
    
    def _calculate_quality_score(self, stats: Dict) -> float:
        """Calculate test quality score"""
        avg_assertions = stats['assertion_count'] / stats['test_count']
        parametrization_ratio = stats['parametrized_tests'] / stats['test_count']
        uses_mocks = stats['mocks_used'] > 0
        
        score = 0
        score += min(avg_assertions * 20, 40)  # Up to 40 points for assertions
        score += parametrization_ratio * 20    # Up to 20 points for parametrization
        score += 20 if uses_mocks else 0       # 20 points for using mocks
        score += 20 if stats['fixtures_used'] else 0  # 20 points for using fixtures
        
        return min(score, 100)
    
    def generate_report(self):
        """Generate test quality report"""
        self.gather_test_files()
        
        for file_path in self.test_files:
            stats = self.analyze_test_file(file_path)
            if stats:
                self.test_stats[file_path] = stats
        
        # Calculate overall stats
        total_tests = sum(stats['test_count'] for stats in self.test_stats.values())
        total_assertions = sum(stats['assertion_count'] for stats in self.test_stats.values())
        avg_quality = sum(stats['quality_score'] for stats in self.test_stats.values()) / len(self.test_stats) if self.test_stats else 0
        
        report = {
            'total_test_files': len(self.test_stats),
            'total_tests': total_tests,
            'total_assertions': total_assertions,
            'avg_assertions_per_test': total_assertions / total_tests if total_tests else 0,
            'overall_quality_score': avg_quality,
            'test_files': self.test_stats,
            'low_quality_tests': self._identify_low_quality_tests()
        }
        
        # Save directly to results directory
        self.save_report(report, 'test_quality_report.json')
        return report
    
    def _identify_low_quality_tests(self) -> List[Dict]:
        """Identify tests with quality issues"""
        return [
            {
                'file': file_path,
                'test_count': stats['test_count'],
                'assertion_count': stats['assertion_count'],
                'quality_score': stats['quality_score'],
                'issues': [
                    'Low assertion count' if stats['assertion_count'] < stats['test_count'] else None,
                    'No parameterization' if stats['parametrized_tests'] == 0 and stats['test_count'] > 1 else None,
                    'No mocks used' if stats['mocks_used'] == 0 else None
                ]
            }
            for file_path, stats in self.test_stats.items()
            if stats['quality_score'] < 50 and stats['test_count'] > 0
        ]