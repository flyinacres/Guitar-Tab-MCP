#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple Test Runner for Guitar Tab MCP
=====================================

Quick and easy test runner that validates core functionality.
Run this after any code changes to ensure nothing is broken.

Usage:
    python simple_test_runner.py           # Run all critical tests
    python simple_test_runner.py --update  # Update expected outputs
"""

import json
import sys
from pathlib import Path

def test_basic_chord():
    """Test basic chord functionality."""
    test_data = {
            "title": "Basic Chord Test",
            "shouldFail": False,
            "timeSignature": "4/4",
            "parts": {
                "Main": {
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
                }
            }
    }
    return "basic_chord", test_data

def test_chuck_strum():
    """Test chuck with strum pattern."""
    test_data = {
            "title": "Chuck with Strum Pattern",
            "shouldFail": False,
            "timeSignature": "4/4",
            "parts": {
                "Main": {
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
                }
            }
    }
    return "chuck_strum", test_data

def test_three_chord_measure():
    """Test critical three-chord measure pattern."""
    test_data = {
            "title": "Three Chord Measure",
            "shouldFail": False,
            "timeSignature": "4/4",
            "parts": {
                "Main": {
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
                }
            }
    }
    return "three_chord_measure", test_data

def run_test(test_name: str, test_data: dict) -> bool:
    """Run a single test through the MCP system."""
    try:
        from validation import validate_tab_data
        from core import generate_tab_output
        
        print(f"Testing: {test_name}...")
        
        # Validate
        validation = validate_tab_data(test_data)
        if validation["isError"]:
            print(f"  ❌ Validation failed: {validation['message']}")
            return False
        
        # Generate
        output, warnings = generate_tab_output(test_data)
        
        if warnings:
            print(f"  ⚠️  Generated with {len(warnings)} warnings")
            for warning in warnings[:3]:  # Show first 3 warnings
                print(f"     - {warning.get('message', 'Unknown warning')}")
        
        # Basic output validation
        if not output or len(output) < 50:
            print(f"  ❌ Output too short or empty")
            return False
        
        # Check for essential elements
        if "1 & 2 & 3 & 4 &" not in output:
            print(f"  ❌ Missing beat markers")
            return False
        
        if test_data["title"] not in output:
            print(f"  ❌ Missing title in output")
            return False
        
        print(f"  ✅ Passed")
        return True
        
    except Exception as e:
        print(f"  ❌ Exception: {str(e)}")
        return False

def save_test_output(test_name: str, test_data: dict):
    """Save test output for visual inspection."""
    try:
        from validation import validate_tab_data
        from core import generate_tab_output
        
        validation = validate_tab_data(test_data)
        if validation["isError"]:
            print(f"Cannot save {test_name}: validation failed")
            return
        
        output, warnings = generate_tab_output(test_data)
        
        # Create outputs directory
        outputs_dir = Path("test_outputs")
        outputs_dir.mkdir(exist_ok=True)
        
        # Save output
        output_file = outputs_dir / f"{test_name}.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output)
        
        # Save input for reference
        input_file = outputs_dir / f"{test_name}_input.json"
        with open(input_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f, indent=2)
        
        print(f"Saved: {output_file}")
        
    except Exception as e:
        print(f"Error saving {test_name}: {e}")

def run_all_tests(save_outputs: bool = False) -> bool:
    """Run all critical tests."""
    print("="*60)
    print("GUITAR TAB MCP - CRITICAL TEST SUITE")
    print("="*60)
    
    # Define all tests
    tests = [
        test_basic_chord(),
        test_chuck_strum(), 
        test_three_chord_measure()
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_data in tests:
        if run_test(test_name, test_data):
            passed += 1
            if save_outputs:
                save_test_output(test_name, test_data)
        else:
            failed += 1
    
    print("\n" + "="*60)
    print("RESULTS:")
    print(f"  ✅ Passed: {passed}")
    print(f"  ❌ Failed: {failed}")
    print(f"  📊 Total:  {len(tests)}")
    
    if failed == 0:
        print("\n🎉 ALL CRITICAL TESTS PASSED! 🎉")
        print("System is ready for use.")
        return True
    else:
        print(f"\n💥 {failed} CRITICAL TESTS FAILED! 💥")
        print("System needs attention before use.")
        return False

def validate_environment():
    """Check that all required modules are available."""
    print("Validating environment...")
    
    required_modules = [
        "core",
        "tab_constants", 
        "tab_models",
        "time_signatures"
    ]
    
    missing = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    
    if missing:
        print(f"❌ Missing required modules: {missing}")
        print("Make sure you're in the correct directory and all files exist.")
        return False
    
    print("✅ Environment validated")
    return True

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Simple Guitar Tab MCP Test Runner")
    parser.add_argument("--save", action="store_true", 
                       help="Save test outputs to files for inspection")
    parser.add_argument("--validate-env", action="store_true",
                       help="Only validate environment")
    
    args = parser.parse_args()
    
    if args.validate_env:
        success = validate_environment()
        sys.exit(0 if success else 1)
    
    # Validate environment first
    if not validate_environment():
        sys.exit(1)
    
    # Run tests
    success = run_all_tests(save_outputs=args.save)
    
    if args.save:
        print(f"\nTest outputs saved to: {Path('test_outputs').absolute()}")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
