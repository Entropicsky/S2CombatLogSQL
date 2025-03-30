#!/usr/bin/env python3
"""
Test runner for S2CombatLogSQL Streamlit application.
Finds and runs all test files in the tests directory.
"""

import os
import sys
import unittest
import importlib.util
import traceback
from glob import glob

def setup_test_environment():
    """Set up the environment for testing."""
    # Add the parent directory to the path so we can import from pages without package structure
    test_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(test_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    # Set environment variables for testing
    os.environ['STREAMLIT_TESTING'] = 'true'
    
    # Suppress Streamlit warnings about missing ScriptRunContext
    import warnings
    warnings.filterwarnings("ignore", 
                            message="Thread.*missing ScriptRunContext", 
                            category=Warning)
    
    print(f"Test environment configured. Parent directory: {parent_dir}")
    print(f"Python path: {sys.path}")

def find_test_modules():
    """Find all test modules in the tests directory."""
    test_dir = os.path.dirname(os.path.abspath(__file__))
    test_files = glob(os.path.join(test_dir, 'test_*.py'))
    test_modules = []
    
    for test_file in test_files:
        module_name = os.path.basename(test_file)[:-3]  # Remove .py
        print(f"Found test module: {module_name}")
        test_modules.append(module_name)
    
    return test_modules

def import_module(module_name):
    """Import a module by name from the tests directory."""
    test_dir = os.path.dirname(os.path.abspath(__file__))
    module_path = os.path.join(test_dir, f"{module_name}.py")
    
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None:
        print(f"Could not find module: {module_name} at {module_path}")
        return None
    
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        print(f"Error loading module {module_name}: {str(e)}")
        traceback.print_exc()
        return None

def load_tests_from_module(module_name):
    """Load all tests from a module."""
    module = import_module(module_name)
    if module is None:
        print(f"Error loading tests from {module_name}")
        return unittest.TestSuite()
    
    loader = unittest.TestLoader()
    try:
        return loader.loadTestsFromModule(module)
    except Exception as e:
        print(f"Error loading tests from {module_name}: {str(e)}")
        traceback.print_exc()
        return unittest.TestSuite()

def run_all_tests():
    """Run all tests in the tests directory."""
    setup_test_environment()
    
    test_modules = find_test_modules()
    print(f"\nRunning tests from {len(test_modules)} files...\n")
    
    suite = unittest.TestSuite()
    for module_name in test_modules:
        suite.addTest(load_tests_from_module(module_name))
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\nTest Summary:")
    print(f"  Ran {result.testsRun} tests")
    print(f"  Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  Failures: {len(result.failures)}")
    print(f"  Errors: {len(result.errors)}")
    
    # Return exit code based on result
    return 0 if result.wasSuccessful() else 1

if __name__ == "__main__":
    sys.exit(run_all_tests()) 