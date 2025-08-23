#!/usr/bin/env python3
"""
Guitar Tab MCP Test Framework
============================

Comprehensive testing framework for the Guitar Tab Generator MCP server.
Includes golden standard tests, regression testing, and automated validation.

Usage:
    python run_tests.py                 # Run all tests
    python run_tests.py --smoke         # Quick smoke tests only
    python run_tests.py --update        # Update golden outputs
    python run_tests.py --verbose       # Detailed output
"""

import sys
import json
import os
import subprocess
import difflib
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
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
            from core_parts import validate_tab_data, generate_tab_output
            
            # Validate input
            validation_result = validate_tab_data(input_data)
            if validation_result["isError"]:
                return False, "", f"Validation failed: {validation_result['message']}"
            
            # Generate tab
            tab_output, warnings = generate_tab_output(input_data)
            
            return True, tab_output, None
            
        except Exception as e:
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
    
    def run_single_test(self, test_name: str, test_data: Dict[str, Any], update_golden: bool = False) -> bool:
        """Run a single test case."""
        logger.info(f"Running test: {test_name}")
        
        success, output, error = self.run_mcp_test(test_data)
        
        if not success:
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

def get_test_suite() -> Dict[str, Dict[str, Any]]:
    """Define the complete test suite with all critical test cases."""
    
    return {
        "basic_chord": {
            "title": "Basic Chord Test",
            "timeSignature": "4/4",
            "measures": [
                {
                    "strumPattern": ["D", "", "D", "", "D", "U", "D", "U"],
                    "events": [
                        {"type": "chord", "beat": 1.0, "chordName": "G", "frets": [
                            {"string": 6, "fret": 3}, {"string": 5, "fret": 2}, {"string": 1, "fret": 3}
                        ]}
                    ]
                }
            ]
        },
        
        "chuck_and_strum": {
            "title": "Chuck with Strum Pattern",
            "timeSignature": "4/4", 
            "measures": [
                {
                    "strumPattern": ["", "", "D", "", "D", "", "D", "U"],
                    "events": [
                        {"type": "chord", "beat": 1.0, "chordName": "Em", "frets": [
                            {"string": 5, "fret": 2}, {"string": 4, "fret": 2}
                        ]},
                        {"type": "chuck", "beat": 1.0}
                    ]
                }
            ]
        },
        
        "two_chord_measure": {
            "title": "Two Chord Measure",
            "timeSignature": "4/4",
            "measures": [
                {
                    "strumPattern": ["D", "", "D", "", "D", "U", "D", "U"],
                    "events": [
                        {"type": "chord", "beat": 1.0, "chordName": "Em", "frets": [
                            {"string": 5, "fret": 2}, {"string": 4, "fret": 2}
                        ]},
                        {"type": "chord", "beat": 3.0, "chordName": "D/F#", "frets": [
                            {"string": 6, "fret": 2}, {"string": 4, "fret": 0}, 
                            {"string": 3, "fret": 2}, {"string": 2, "fret": 3}, {"string": 1, "fret": 2}
                        ]}
                    ]
                }
            ]
        },
        
        "three_chord_measure": {
            "title": "Three Chord Measure",
            "timeSignature": "4/4",
            "measures": [
                {
                    "strumPattern": ["D", "", "D", "", "D", "U", "D", "U"],
                    "events": [
                        {"type": "chord", "beat": 1.0, "chordName": "G", "frets": [
                            {"string": 6, "fret": 3}, {"string": 5, "fret": 2}, {"string": 1, "fret": 3}
                        ]},
                        {"type": "chord", "beat": 3.0, "chordName": "Am", "frets": [
                            {"string": 5, "fret": 0}, {"string": 4, "fret": 2}, 
                            {"string": 3, "fret": 2}, {"string": 2, "fret": 1}
                        ]},
                        {"type": "chord", "beat": 4.0, "chordName": "C/B", "frets": [
                            {"string": 5, "fret": 2}, {"string": 4, "fret": 2}, 
                            {"string": 3, "fret": 0}, {"string": 2, "fret": 1}, {"string": 1, "fret": 0}
                        ]}
                    ]
                }
            ]
        },
        
        "multiple_measures": {
            "title": "Multiple Measures Test",
            "timeSignature": "4/4",
            "measures": [
                {
                    "strumPattern": ["D", "", "D", "", "D", "U", "D", "U"],
                    "events": [
                        {"type": "chord", "beat": 1.0, "chordName": "G", "frets": [
                            {"string": 6, "fret": 3}, {"string": 5, "fret": 2}, {"string": 1, "fret": 3}
                        ]}
                    ]
                },
                {
                    "strumPattern": ["", "", "D", "", "D", "", "D", "U"],
                    "events": [
                        {"type": "chord", "beat": 1.0, "chordName": "C", "frets": [
                            {"string": 5, "fret": 3}, {"string": 4, "fret": 2}, 
                            {"string": 3, "fret": 0}, {"string": 2, "fret": 1}, {"string": 1, "fret": 0}
                        ]},
                        {"type": "chuck", "beat": 1.0}
                    ]
                },
                {
                    "strumPattern": ["D", "", "D", "", "D", "U", "D", "U"],
                    "events": [
                        {"type": "chord", "beat": 1.0, "chordName": "Em", "frets": [
                            {"string": 5, "fret": 2}, {"string": 4, "fret": 2}
                        ]},
                        {"type": "chord", "beat": 3.0, "chordName": "D", "frets": [
                            {"string": 4, "fret": 0}, {"string": 3, "fret": 2}, 
                            {"string": 2, "fret": 3}, {"string": 1, "fret": 2}
                        ]}
                    ]
                },
                {
                    "strumPattern": ["D", "", "D", "", "D", "U", "D", "U"],
                    "events": [
                        {"type": "chord", "beat": 1.0, "chordName": "G", "frets": [
                            {"string": 6, "fret": 3}, {"string": 5, "fret": 2}, {"string": 1, "fret": 3}
                        ]},
                        {"type": "chord", "beat": 3.0, "chordName": "Am", "frets": [
                            {"string": 5, "fret": 0}, {"string": 4, "fret": 2}, 
                            {"string": 3, "fret": 2}, {"string": 2, "fret": 1}
                        ]},
                        {"type": "chord", "beat": 4.0, "chordName": "C", "frets": [
                            {"string": 5, "fret": 3}, {"string": 4, "fret": 2}, 
                            {"string": 3, "fret": 0}, {"string": 2, "fret": 1}, {"string": 1, "fret": 0}
                        ]}
                    ]
                }
            ]
        },
        
        "ukulele_test": {
            "title": "Ukulele Test",
            "instrument": "ukulele",
            "timeSignature": "4/4",
            "measures": [
                {
                    "strumPattern": ["D", "", "D", "", "D", "U", "D", "U"],
                    "events": [
                        {"type": "chord", "beat": 1.0, "chordName": "C", "frets": [
                            {"string": 4, "fret": 0}, {"string": 3, "fret": 0}, 
                            {"string": 2, "fret": 0}, {"string": 1, "fret": 3}
                        ]}
                    ]
                }
            ]
        },
        
        "guitar_techniques": {
            "title": "Guitar Techniques Test",
            "timeSignature": "4/4",
            "measures": [
                {
                    "strumPattern": ["D", "", "D", "", "D", "U", "D", "U"],
                    "events": [
                        {"type": "note", "string": 1, "beat": 1.0, "fret": 3},
                        {"type": "hammerOn", "string": 1, "startBeat": 2.0, "fromFret": 3, "toFret": 5},
                        {"type": "bend", "string": 1, "beat": 3.0, "fret": 5, "semitones": 1.0, "vibrato": True}
                    ]
                }
            ]
        }
    }

def get_smoke_tests() -> Dict[str, Dict[str, Any]]:
    """Essential smoke tests that must always pass."""
    full_suite = get_test_suite()
    return {
        "basic_chord": full_suite["basic_chord"],
        "chuck_and_strum": full_suite["chuck_and_strum"],
        "three_chord_measure": full_suite["three_chord_measure"]
    }

# ============================================================================
# Test Runner Functions
# ============================================================================

def run_all_tests(update_golden: bool = False, smoke_only: bool = False, verbose: bool = False) -> bool:
    """Run the complete test suite."""
    project_root = Path(__file__).parent
    framework = TabTestFramework(project_root)
    
    # Select test suite
    if smoke_only:
        test_suite = get_smoke_tests()
        logger.info("Running smoke tests only")
    else:
        test_suite = get_test_suite()
        logger.info("Running full test suite")
    
    if verbose:
        logger.setLevel(logging.DEBUG)
    
    # Run tests
    all_passed = True
    for test_name, test_data in test_suite.items():
        passed = framework.run_single_test(test_name, test_data, update_golden)
        if not passed:
            all_passed = False
    
    # Print results
    framework.print_results()
    
    return all_passed

def create_example_files():
    """Create example JSON files for manual testing."""
    project_root = Path(__file__).parent
    examples_dir = project_root / "examples"
    examples_dir.mkdir(exist_ok=True)
    
    test_suite = get_test_suite()
    
    for test_name, test_data in test_suite.items():
        example_file = examples_dir / f"{test_name}.json"
        with open(example_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f, indent=2)
        
        logger.info(f"Created example: {example_file}")

def validate_project_structure():
    """Validate that all required files exist."""
    project_root = Path(__file__).parent
    required_files = [
        "core_parts.py",
        "mcp_server_parts.py", 
        "cli.py",
        "tab_constants.py",
        "tab_models_parts.py",
        "time_signatures.py",
        "requirements.txt"
    ]
    
    missing_files = []
    for file_name in required_files:
        if not (project_root / file_name).exists():
            missing_files.append(file_name)
    
    if missing_files:
        logger.error(f"Missing required files: {missing_files}")
        return False
    
    logger.info("Project structure validated")
    return True

# ============================================================================
# Command Line Interface
# ============================================================================

def main():
    """Main test runner entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Guitar Tab MCP Test Framework")
    parser.add_argument("--smoke", action="store_true", help="Run smoke tests only")
    parser.add_argument("--update", action="store_true", help="Update golden outputs")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--create-examples", action="store_true", help="Create example JSON files")
    parser.add_argument("--validate-structure", action="store_true", help="Validate project structure")
    
    args = parser.parse_args()
    
    if args.validate_structure:
        if validate_project_structure():
            print("✅ Project structure is valid")
            sys.exit(0)
        else:
            print("❌ Project structure validation failed")
            sys.exit(1)
    
    if args.create_examples:
        create_example_files()
        print("✅ Example files created")
        sys.exit(0)
    
    # Run tests
    try:
        success = run_all_tests(
            update_golden=args.update,
            smoke_only=args.smoke,
            verbose=args.verbose
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
