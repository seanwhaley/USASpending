import os
import ast
import json
from collections import defaultdict
from pathlib import Path

class TestQualityAnalyzer:
    def __init__(self, test_dir='tests', output_dir='output/reports/test_quality'):
        self.test_dir = test_dir
        self.output_dir = Path(output_dir)
        self.test_files = []
        self.test_stats = {}
        
    def gather_test_files(self):
        """Gather all test files"""
        for root, _, files in os.walk(self.test_dir):
            for file in files:
                if file.startswith('test_') and file.endswith('.py'):
                    self.test_files.append(os.path.join(root, file))
    
    def analyze_test_file(self, file_path):
        """Analyze a single test file for quality metrics"""
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
            
            # Find imports to detect test tools
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        imports.add(name.name)
                elif isinstance(node, ast.ImportFrom):
                    imports.add(node.module)
            
            # Check for pytest fixtures
            fixtures_defined = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for decorator in node.decorator_list:
                        if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name) and decorator.func.id == 'fixture':
                            fixtures_defined.append(node.name)
            
            # Analyze test functions
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                    stats['test_count'] += 1
                    
                    # Check for parametrize decorator
                    for decorator in node.decorator_list:
                        if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute) and decorator.func.attr == 'parametrize':
                            stats['parametrized_tests'] += 1
                    
                    # Count assertions
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
                        'line_count': node.end_lineno - node.lineno,
                    }
            
            # Calculate a quality score (simple heuristic)
            if stats['test_count'] > 0:
                avg_assertions = stats['assertion_count'] / stats['test_count']
                parametrization_ratio = stats['parametrized_tests'] / stats['test_count'] if stats['test_count'] > 0 else 0
                uses_mocks = stats['mocks_used'] > 0
                uses_fixtures = len(fixtures_defined) > 0
                
                # Score components
                score = 0
                score += min(avg_assertions * 20, 40)  # Up to 40 points for assertions
                score += parametrization_ratio * 20  # Up to 20 points for parametrization
                score += 20 if uses_mocks else 0  # 20 points for using mocks
                score += 20 if uses_fixtures else 0  # 20 points for using fixtures
                
                stats['quality_score'] = min(score, 100)
            
            return stats
        
        except SyntaxError:
            print(f"Syntax error in {file_path}")
            return None
    
    def analyze(self):
        """Run the full analysis"""
        self.gather_test_files()
        
        for file_path in self.test_files:
            stats = self.analyze_test_file(file_path)
            if stats:
                self.test_stats[file_path] = stats
        
        return self.test_stats
    
    def generate_report(self):
        """Generate a JSON report file"""
        test_stats = self.analyze()
        
        # Calculate overall stats
        total_tests = sum(stats['test_count'] for stats in test_stats.values())
        total_assertions = sum(stats['assertion_count'] for stats in test_stats.values())
        total_parametrized = sum(stats['parametrized_tests'] for stats in test_stats.values())
        total_quality_score = sum(stats['quality_score'] for stats in test_stats.values()) / len(test_stats) if test_stats else 0
        
        # Identify low quality tests
        low_quality_tests = [
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
            for file_path, stats in test_stats.items()
            if stats['quality_score'] < 50 and stats['test_count'] > 0
        ]
        
        report = {
            'timestamp': __import__('datetime').datetime.now().isoformat(),
            'total_test_files': len(test_stats),
            'total_tests': total_tests,
            'total_assertions': total_assertions,
            'avg_assertions_per_test': total_assertions / total_tests if total_tests else 0,
            'parametrized_tests_ratio': total_parametrized / total_tests if total_tests else 0,
            'overall_quality_score': total_quality_score,
            'low_quality_tests': low_quality_tests,
            'action_items': [{
                'file': test['file'],
                'quality_score': test['quality_score'],
                'issues': [issue for issue in test['issues'] if issue],
                'recommendation': 'Improve test quality with more assertions and parameterization'
            } for test in low_quality_tests]
        }

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_file = self.output_dir / 'test_quality_report.json'
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        return report

if __name__ == '__main__':
    analyzer = TestQualityAnalyzer()
    report = analyzer.generate_report()
    print(f"Overall test quality score: {report['overall_quality_score']:.1f}/100")
    print(f"{len(report['low_quality_tests'])} test files need quality improvements")