# Guitar Tab MCP Testing Framework

This document describes the testing framework for the Guitar Tab MCP project.

## Overview

The testing framework provides **gold standard validation** to ensure that code changes don't break existing functionality. It includes:

- **Critical smoke tests** that must always pass
- **Comprehensive test suite** covering all major features  
- **Golden output comparison** to catch subtle regressions
- **Simple test runner** for quick validation

## Quick Start

### Run Critical Tests (Recommended)
```bash
python simple_test_runner.py
```
This runs the 3 most critical tests that validate core functionality.

### Run Full Test Suite  
```bash
python run_tests.py
```
This runs all tests including edge cases and advanced features.

### Save Test Outputs for Inspection
```bash
python simple_test_runner.py --save
```
Saves actual outputs to `test_outputs/` directory for manual review.

## Test Categories

### 1. Smoke Tests (Critical)
These 3 tests **must always pass**:

- **Basic Chord**: Single chord with standard strum pattern
- **Chuck + Strum**: Chuck event with strum pattern alignment  
- **Three-Chord Measure**: Complex measure with proper chord timing

If any smoke test fails, the system is broken and needs immediate attention.

### 2. Comprehensive Tests
Full feature validation including:

- Multiple measures
- Guitar techniques (hammer-ons, bends, slides)
- Ukulele support
- Edge cases and error handling

## File Structure

```
Guitar-Tab-MCP/
├── simple_test_runner.py      # Quick critical tests
├── run_tests.py               # Full test framework  
├── TESTING.md                 # This file
├── tests/
│   └── golden_outputs/        # Expected outputs
├── test_outputs/              # Generated during --save
└── examples/                  # Example JSON files
```

## Adding New Tests

### 1. Add to Simple Test Runner
For critical functionality, add a new test function to `simple_test_runner.py`:

```python
def test_new_feature():
    """Test description."""
    test_data = {
        "title": "New Feature Test",
        "timeSignature": "4/4", 
        "measures": [...]
    }
    return "new_feature", test_data
```

Then add it to the `tests` list in `run_all_tests()`.

### 2. Add to Comprehensive Suite
For full feature coverage, add to the `get_test_suite()` function in `run_tests.py`.

## Workflow

### Before Making Changes
```bash
# Establish current state as golden standard
python run_tests.py --update
```

### After Making Changes  
```bash
# Quick validation
python simple_test_runner.py

# Full validation  
python run_tests.py

# If tests fail, inspect differences
python simple_test_runner.py --save
# Check files in test_outputs/ directory
```

### When Changing Expected Behavior
```bash
# Update golden outputs after verifying changes are correct
python run_tests.py --update
```

## Interpreting Results

### ✅ All Tests Passed
```
🎉 ALL CRITICAL TESTS PASSED! 🎉
System is ready for use.
```
Your changes didn't break anything - good to go!

### ❌ Tests Failed
```
💥 2 CRITICAL TESTS FAILED! 💥
System needs attention before use.
```

Check the specific error messages and:
1. Fix the code if it's a bug
2. Update golden outputs if behavior intentionally changed
3. Review test outputs in `test_outputs/` for manual inspection

### ⚠️ Warnings
```
⚠️  Generated with 2 warnings
   - Multi-digit fret (12) may affect template alignment
```
Warnings indicate potential issues but don't fail tests. Review and decide if action needed.

## Golden Standard Philosophy

The testing framework uses **golden standard comparison**:

- **First run**: Saves current output as "correct"
- **Subsequent runs**: Compares new output to saved "golden" output
- **Differences**: Highlighted with detailed diffs

This catches even subtle changes like:
- Different spacing in tab output
- Changed chord fingerings
- Modified strum pattern display
- Altered warning messages

## Integration with Development

### Pre-Commit Testing
Always run before committing:
```bash
python simple_test_runner.py
```

### Continuous Integration  
The test framework is designed to work with CI/CD:
```bash
# In CI pipeline
python run_tests.py --validate-structure  # Check all files exist
python run_tests.py                       # Run full test suite
```

### Code Review
When reviewing changes:
1. Check that tests still pass
2. Review any updated golden outputs
3. Ensure new features have corresponding tests

## Troubleshooting

### Import Errors
```bash
python simple_test_runner.py --validate-env
```
Checks that all required modules are available.

### Missing Files
```bash
python run_tests.py --validate-structure  
```
Ensures project structure is complete.

### Test Framework Issues
```bash
python run_tests.py --verbose
```
Shows detailed logging for debugging test framework itself.

## Advanced Usage

### Custom Test Runs
```bash
python run_tests.py --smoke          # Just smoke tests
python run_tests.py --update         # Update golden outputs  
python run_tests.py --verbose        # Detailed logging
```

### Creating Examples
```bash
python run_tests.py --create-examples
```
Generates example JSON files in `examples/` directory.

---

**Remember**: The goal is to catch regressions early and maintain confidence that the system works correctly after any changes.
