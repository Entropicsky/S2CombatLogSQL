#!/usr/bin/env python3
"""
Test all SQL queries in the Streamlit application.

This script:
1. Runs the generic query test that checks all SQL queries from all Python files
2. Runs page-specific query tests for each page that has them

Usage:
    python test_all_queries.py
"""

import os
import sys
import importlib.util
from pathlib import Path

# Make sure current directory is in the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Add the parent directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

def run_test_module(module_path):
    """Run a test module by path."""
    module_name = os.path.basename(module_path).replace('.py', '')
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = module_path  # Set __file__ attribute
    spec.loader.exec_module(module)
    
    # Check if the module has a test_queries function
    if hasattr(module, 'test_queries'):
        print(f"\n{'='*80}\nRunning tests for {module_path}\n{'='*80}")
        module.test_queries()
        return True
    return False

def main():
    """Run all query tests."""
    print("Starting SQL query validation...\n")
    
    # First run the generic query tests
    try:
        from tests.test_queries import test_streamlit_queries
        test_streamlit_queries()
    except ImportError:
        print("Could not import test_queries module. Make sure tests/test_queries.py exists.")
        # Try direct import
        try:
            test_queries_path = os.path.join(current_dir, 'tests', 'test_queries.py')
            if os.path.exists(test_queries_path):
                run_test_module(test_queries_path)
            else:
                print(f"File not found: {test_queries_path}")
        except Exception as e:
            print(f"Error running test_queries: {e}")
    
    # Then run page-specific tests
    streamlit_dir = Path(__file__).parent
    pages_dir = streamlit_dir / 'pages'
    
    # If pages directory exists, test each page
    if pages_dir.exists():
        page_files = list(pages_dir.glob('*.py'))
        
        test_count = 0
        for page_file in page_files:
            if run_test_module(str(page_file)):
                test_count += 1
        
        if test_count == 0:
            print("\nNo page-specific tests were found.")
    
    # Also test the Home.py file if it exists
    home_file = streamlit_dir / 'Home.py'
    if home_file.exists():
        run_test_module(str(home_file))
    
    print("\nAll query tests complete!")

if __name__ == "__main__":
    main() 