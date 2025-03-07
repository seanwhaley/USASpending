#!/usr/bin/env python
"""Tool for analyzing gaps in test coverage by comparing implementation and test files."""
import os
import sys
from pathlib import Path
import ast
import argparse
from typing import Dict, List, Set, Tuple
import json

def parse_python_file(file_path: str) -> Set[str]:
    """Parse a Python file and extract class and function names."""
    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            tree = ast.parse(f.read(), filename=file_path)
        except SyntaxError:
            print(f"Error parsing {file_path}")
            return set()

    names = set()
    
    class ParentNodeVisitor(ast.NodeVisitor):
        def visit(self, node):
            # Add parent references to all child nodes
            for child in ast.iter_child_nodes(node):
                child.parent = node
            super().visit(node)
    
    # Add parent references
    tree.parent = None
    ParentNodeVisitor().visit(tree)
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            names.add(node.name)
            # Get methods
            for child in node.body:
                if isinstance(child, ast.FunctionDef):
                    names.add(f"{node.name}.{child.name}")
        elif isinstance(node, ast.FunctionDef):
            # Only add top-level functions
            if hasattr(node, 'parent') and isinstance(node.parent, ast.Module):
                names.add(node.name)
    
    return names

def find_implementation_files(src_dir: str) -> List[str]:
    """Find Python implementation files in the source directory."""
    impl_files = []
    for root, _, files in os.walk(src_dir):
        for file in files:
            if file.endswith('.py') and not file.startswith('test_'):
                impl_files.append(os.path.join(root, file))
    return impl_files

def find_test_file(impl_file: str, test_dir: str) -> str:
    """Find corresponding test file for an implementation file."""
    impl_name = os.path.basename(impl_file)
    test_name = f"test_{impl_name}"
    
    # Look for test file in test directory
    for root, _, files in os.walk(test_dir):
        if test_name in files:
            return os.path.join(root, test_name)
    
    return ""

def analyze_coverage_gaps(impl_dir: str, test_dir: str) -> Dict[str, Dict[str, List[str]]]:
    """Analyze test coverage gaps between implementation and test files."""
    results = {}
    
    impl_files = find_implementation_files(impl_dir)
    for impl_file in impl_files:
        impl_items = parse_python_file(impl_file)
        
        test_file = find_test_file(impl_file, test_dir)
        test_items = parse_python_file(test_file) if test_file else set()
        
        # Find items that don't have corresponding tests
        untested_items = [item for item in impl_items if not any(
            test.startswith(f"test_{item}") or 
            test.startswith(f"Test{item}") for test in test_items
        )]
        
        if untested_items:
            rel_path = os.path.relpath(impl_file, impl_dir)
            results[rel_path] = {
                "missing_tests": untested_items,
                "test_file": os.path.relpath(test_file, test_dir) if test_file else None
            }
    
    return results

def main():
    parser = argparse.ArgumentParser(
        description="Analyze test coverage gaps in Python codebase"
    )
    parser.add_argument(
        "--src-dir",
        default="src",
        help="Source directory containing implementation files"
    )
    parser.add_argument(
        "--test-dir",
        default="tests",
        help="Directory containing test files"
    )
    parser.add_argument(
        "--output",
        help="Output JSON file path. If not specified, will write to output/reports/coverage/test_gap_report.json"
    )
    
    args = parser.parse_args()
    
    # Resolve paths relative to script location
    script_dir = Path(__file__).parent.parent
    src_dir = script_dir / args.src_dir
    test_dir = script_dir / args.test_dir
    
    if not src_dir.exists():
        print(f"Source directory not found: {src_dir}")
        return 1
    if not test_dir.exists():
        print(f"Test directory not found: {test_dir}")
        return 1
        
    print(f"Analyzing test coverage gaps...")
    print(f"Source directory: {src_dir}")
    print(f"Test directory: {test_dir}")
    
    results = analyze_coverage_gaps(str(src_dir), str(test_dir))
    
    # Output results
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = script_dir / 'output' / 'reports' / 'coverage' / 'test_gap_report.json'
        
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Results written to {output_path}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())