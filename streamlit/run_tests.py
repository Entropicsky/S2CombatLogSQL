#!/usr/bin/env python3
"""
Run specific test queries for Match_Summary page.
"""

import os
import sys
from pathlib import Path

# Set __file__ variable for modules that use it
os.environ['PYTHONPATH'] = str(Path(__file__).parent)

# Import module using importlib
import importlib.util

def run_test_for_file(file_path):
    """Run tests for a specific file."""
    print(f"\nRunning tests for {file_path}")
    print("=" * 80)
    
    # Import the module
    spec = importlib.util.spec_from_file_location("module", file_path)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = file_path  # Set __file__ attribute
    spec.loader.exec_module(module)
    
    # Run the test_queries function if it exists
    if hasattr(module, 'test_queries'):
        module.test_queries()
        return True
    else:
        print(f"No test_queries function found in {file_path}")
        return False

if __name__ == "__main__":
    # Run tests for Match_Summary
    run_test_for_file("pages/1_Match_Summary.py")
    
    # Run tests for Home.py
    run_test_for_file("Home.py") 