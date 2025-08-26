#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Guitar Tab MCP Test Framework
============================

Comprehensive testing framework for the Guitar Tab Generator MCP server.
Includes golden standard tests, regression testing

Usage:
    python run_tests.py                 # Run all tests
    python run_tests.py --smoke         # Quick smoke tests only
    python run_tests.py --update        # Update golden outputs
    python run_tests.py --verbose       # Detailed output
"""

import sys
import os
import json
import difflib
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from tab_models import TabRequest
import logging
import traceback
from notation_events import NotationEvent

# Configure logging
logging.basicConfig(level=logging.ERROR, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class TabTestFramework:
    """Test framework for Guitar Tab MCP server."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.tests_dir = project_root / "tests"
        self.examples_dir = project_root / "examples"
        self.golden_dir = self.tests_dir / "golden_outputs"
        
        # Ensure directories exist
        self.tests_dir.mkdir(exist_ok=True)
        self.examples_dir.mkdir(exist_ok=True)
        self.golden_dir.mkdir(exist_ok=True)
        
        self.test_results = []
    
    def run_mcp_test(self, input_data: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
        """
        Run a single test through the MCP server.
        
        Returns:
            (success, output_content, error_message)
        """
        try:
            # Import and use the MCP functionality directly
            from validation import validate_tab_data
            from tab_generation import generate_tab_output
            request = TabRequest(**input_data)

            # Validate input
            validation_result = validate_tab_data(request)
            if validation_result["isError"]:
                return False, "", f"Validation failed: {validation_result['message']}"
            
            # Generate tab
            tab_output, warnings = generate_tab_output(request)
            
            return True, tab_output, None
            
        except Exception as e:
            # If there was an exception, probably want to know where!
            logging.error(traceback.format_exc())
            return False, "", f"Generation failed: {str(e)}"

    
    def compare_with_golden(self, test_name: str, actual_output: str) -> bool:
        """Compare actual output with golden standard."""
        golden_file = self.golden_dir / f"{test_name}.txt"
        
        if not golden_file.exists():
            logger.warning(f"No golden file for {test_name}, creating one")
            self.save_golden_output(test_name, actual_output)
            return True
        
        with open(golden_file, 'r', encoding='utf-8') as f:
            expected = f.read()
        
        if actual_output.strip() == expected.strip():
            return True
        else:
            logger.error(f"Output mismatch for {test_name}")
            self.show_diff(test_name, expected, actual_output)
            return False
    
    def save_golden_output(self, test_name: str, output: str):
        """Save output as golden standard."""
        golden_file = self.golden_dir / f"{test_name}.txt"
        with open(golden_file, 'w', encoding='utf-8') as f:
            f.write(output)
        logger.info(f"Saved golden output: {golden_file}")
    
    def show_diff(self, test_name: str, expected: str, actual: str):
        """Show detailed diff between expected and actual output."""
        print(f"\n=== DIFF for {test_name} ===")
        diff = difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile=f"expected/{test_name}.txt",
            tofile=f"actual/{test_name}.txt"
        )
        print(''.join(diff))
        print("=== END DIFF ===\n")
    
    def run_single_test(self, test_name: str, test_data: Dict[str, Any], update_golden: bool = False, show: bool = False) -> bool:
        """Run a single test case."""
        logger.info(f"Running test: {test_name}")
        
        success, output, error = self.run_mcp_test(test_data)
        
        if show:
            print(output)

        # Some tests are designed to fail
        if test_data["shouldFail"]:
            # it was supposed to fail, but it did not!
            logger.info(f"Error for failure case '{error}'")
            if success:
                logger.error(f"Test {test_name} was designed to fail, but passed")
                self.test_results.append({"name": test_name, "status": "FAILED", "error": "Error condition passed"})
                return False
            elif test_data["expectedError"] != error:
                logger.error(f"Test {test_name} was expected to fail, but did so with the wrong error!")
                self.test_results.append({"name": test_name, "status": "FAILED", "error": "Wrong error type"})
                return False
        elif not success:
            logger.error(f"Test {test_name} failed: {error}")
            self.test_results.append({"name": test_name, "status": "FAILED", "error": error})
            return False
        
        if update_golden:
            self.save_golden_output(test_name, output)
            self.test_results.append({"name": test_name, "status": "UPDATED"})
            return True
        
        if self.compare_with_golden(test_name, output):
            logger.info(f"Test {test_name} passed")
            self.test_results.append({"name": test_name, "status": "PASSED"})
            return True
        else:
            self.test_results.append({"name": test_name, "status": "FAILED", "error": "Output mismatch"})
            return False
    
    def print_results(self):
        """Print test results summary."""
        print("\n" + "="*50)
        print("TEST RESULTS SUMMARY")
        print("="*50)
        
        passed = sum(1 for r in self.test_results if r["status"] == "PASSED")
        failed = sum(1 for r in self.test_results if r["status"] == "FAILED")
        updated = sum(1 for r in self.test_results if r["status"] == "UPDATED")
        
        print(f"Total tests: {len(self.test_results)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Updated: {updated}")
        
        if failed > 0:
            print(f"\nFAILED TESTS:")
            for result in self.test_results:
                if result["status"] == "FAILED":
                    error_msg = result.get("error", "Unknown error")
                    print(f"  ❌ {result['name']}: {error_msg}")
        
        print("\nAll tests:")
        for result in self.test_results:
            status_icon = "✅" if result["status"] == "PASSED" else "🔄" if result["status"] == "UPDATED" else "❌"
            print(f"  {status_icon} {result['name']}: {result['status']}")
        
        return failed == 0

# ============================================================================
# Test Data Definitions
# ============================================================================

def get_test_suite(test_file: Path) -> Dict[str, Dict[str, Any]]:
    """Load test suite from JSON file."""
    print(f"Using test file '{test_file}'")

    test_file_path = Path(__file__).parent / test_file
    
    if not test_file_path.exists():
        raise FileNotFoundError(f"Test file not found: {test_file_path}")
    
    with open(test_file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_smoke_tests(test_file: Path) -> Dict[str, Dict[str, Any]]:
    """Essential smoke tests that must always pass."""
    full_suite = get_test_suite(test_file)
    return {
        "basic_chord": full_suite["basic_chord"],
        "chuck_and_strum": full_suite["chuck_and_strum"],
        "three_chord_measure": full_suite["three_chord_measure"]
    }

# ============================================================================
# Test Runner Functions
# ============================================================================

def run_all_tests(test_file: str, update_golden: bool = False, smoke_only: bool = False, verbose: bool = False, show: bool = False) -> bool:
    """Run the complete test suite."""
    project_root = Path(__file__).parent
    framework = TabTestFramework(project_root)
    
    # Select test suite
    if smoke_only:
        test_suite = get_smoke_tests(test_file)
        logger.info("Running smoke tests only")
    else:
        test_suite = get_test_suite(test_file)
        logger.info("Running full test suite")
    
    if verbose:
        logger.setLevel(logging.DEBUG)
    
    # Ran a quick test to see if this scheme worked...
    #NotationEvent.set_technique_style("alternating")

    # Run tests
    all_passed = True
    for test_name, test_data in test_suite.items():
        passed = framework.run_single_test(test_name, test_data, update_golden, show)
        if not passed:
            all_passed = False
    
    # Print results
    framework.print_results()
    
    return all_passed

def create_json_files(test_file):
    """Create example JSON files for manual testing."""
    project_root = Path(__file__).parent
    examples_dir = project_root / "examples"
    examples_dir.mkdir(exist_ok=True)
    
    test_suite = get_test_suite(test_file)
    
    for test_name, test_data in test_suite.items():
        example_file = examples_dir / f"{test_name}.json"
        with open(example_file, 'w', encoding='utf-8') as f:
            wrapped = {test_name: test_data}
            json.dump(wrapped, f, indent=2)
        
        logger.info(f"Created example: {example_file}")


# ============================================================================
# Command Line Interface
# ============================================================================

def main():
    """Main test runner entry point."""
    import argparse

    # Default test file...
    test_file = os.path.join("tests", "test_suite.json")
    
    parser = argparse.ArgumentParser(description="Guitar Tab MCP Test Framework")
    parser.add_argument("--smoke", action="store_true", help="Run smoke tests only")
    parser.add_argument("--update", action="store_true", help="Update golden outputs")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--show", action="store_true", help="Sometimes you need to see the tabs to ensure they are correct!")
    parser.add_argument("--create-json", action="store_true", help="Create JSON files from test files")
    parser.add_argument("--test-file", help="Specific test file to run")
    
    args = parser.parse_args()

    # Validate extension
    if args.test_file:
        if not args.test_file.lower().endswith(".json"):
            print("Error: File must have a .json extension", file=sys.stderr)
            sys.exit(1)

        # Validate existence
        if not os.path.isfile(args.test_file):
            print(f"Error: File not found: {args.test_file}", file=sys.stderr)
            sys.exit(1)

        test_file = args.test_file
        print(f"Main() Using test file '{test_file}'")

    
    if args.create_json:
        create_json_files(test_file)
        print("✅ Example files created")
        sys.exit(0)
    
    # Run tests
    try:
        success = run_all_tests(
            test_file,
            update_golden=args.update,
            smoke_only=args.smoke,
            verbose=args.verbose,
            show=args.show
        )
        
        if success:
            print("\n🎉 All tests passed!")
            sys.exit(0)
        else:
            print("\n💥 Some tests failed!")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Test framework error: {e}")
        print(f"❌ Test framework error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
