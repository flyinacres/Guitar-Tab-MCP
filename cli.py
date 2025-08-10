#!/usr/bin/env python3
"""
Guitar Tab Generator - Standalone Command Line Interface
======================================================

Standalone command-line tool for guitar tab generation. This provides a way
to test and use the tab generator without MCP/LLM integration, making it
ideal for development, testing, and direct use by developers.

Key Design Goals:
- Simple, intuitive command-line interface
- Cross-platform compatibility (Windows, macOS, Linux)
- Comprehensive error reporting for debugging
- Support for batch processing multiple files
- JSON validation with helpful error messages

Usage Examples:
    python cli.py input.json                    # Output to stdout
    python cli.py input.json output.txt         # Output to file
    python cli.py --validate input.json         # Validation only
    python cli.py --verbose input.json          # Detailed logging
    python cli.py --help                        # Show help
"""

import sys
import json
import argparse
import logging
from pathlib import Path
from typing import Optional

# Import our core functionality
from core import (
    TabRequest, validate_tab_data, generate_tab_output, 
    check_attempt_limit
)

# ============================================================================
# Cross-Platform Compatibility Setup
# ============================================================================

def setup_cross_platform_environment():
    """
    Configure environment for cross-platform compatibility.
    
    Handles encoding issues on Windows and ensures consistent
    behavior across different operating systems.
    """
    # Windows-specific encoding fixes
    if sys.platform == "win32":
        try:
            # Ensure UTF-8 encoding for console output
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except AttributeError:
            # Python < 3.7 doesn't have reconfigure
            pass

def setup_logging(verbose: bool = False) -> logging.Logger:
    """
    Configure logging for CLI usage.
    
    Unlike the MCP server which logs to stderr to avoid protocol
    interference, the CLI can use more flexible logging since
    stdout is reserved for tab output or user-specified content.
    """
    level = logging.DEBUG if verbose else logging.INFO
    
    # Configure logging format for CLI usage
    logging.basicConfig(
        level=level,
        format='%(asctime)s - TAB-CLI - %(levelname)s - %(message)s',
        stream=sys.stderr  # Keep logs separate from tab output
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Guitar Tab Generator CLI starting (verbose={'on' if verbose else 'off'})")
    return logger

# ============================================================================
# File I/O Operations
# ============================================================================

def load_json_file(file_path: Path, logger: logging.Logger) -> Optional[dict]:
    """
    Load and parse JSON file with comprehensive error handling.
    
    This provides much more detailed error reporting than the MCP server
    since we can assume a human developer is using the CLI and can
    benefit from specific file/line number information.
    """
    logger.debug(f"Loading JSON file: {file_path}")
    
    if not file_path.exists():
        logger.error(f"Input file not found: {file_path}")
        print(f"Error: Input file '{file_path}' does not exist.", file=sys.stderr)
        return None
    
    if not file_path.is_file():
        logger.error(f"Path is not a file: {file_path}")
        print(f"Error: '{file_path}' is not a regular file.", file=sys.stderr)
        return None
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.debug(f"Successfully loaded JSON with {len(data)} top-level keys")
        return data
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing failed: {e}")
        print(f"Error: Invalid JSON in '{file_path}':", file=sys.stderr)
        print(f"  Line {e.lineno}, Column {e.colno}: {e.msg}", file=sys.stderr)
        
        # Try to show context around the error
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            if e.lineno <= len(lines):
                error_line = lines[e.lineno - 1].rstrip()
                print(f"  >>> {error_line}", file=sys.stderr)
                if e.colno > 0:
                    pointer = " " * (e.colno - 1 + 6) + "^"
                    print(pointer, file=sys.stderr)
        except Exception:
            pass  # Don't let context display errors mask the main error
        
        return None
    
    except UnicodeDecodeError as e:
        logger.error(f"Unicode decoding failed: {e}")
        print(f"Error: Cannot read '{file_path}' - file encoding issue.", file=sys.stderr)
        print(f"  Try saving the file as UTF-8 encoding.", file=sys.stderr)
        return None
    
    except Exception as e:
        logger.error(f"Unexpected error loading file: {e}")
        print(f"Error: Cannot read '{file_path}': {e}", file=sys.stderr)
        return None

def save_output_file(content: str, file_path: Path, logger: logging.Logger) -> bool:
    """
    Save tab content to output file with error handling.
    
    Creates parent directories if needed and handles common
    file writing issues like permissions and disk space.
    """
    logger.debug(f"Saving output to: {file_path}")
    
    try:
        # Create parent directories if they don't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"Tab successfully saved to: {file_path}")
        return True
        
    except PermissionError:
        logger.error(f"Permission denied writing to: {file_path}")
        print(f"Error: Permission denied writing to '{file_path}'.", file=sys.stderr)
        print("  Check file permissions and try again.", file=sys.stderr)
        return False
    
    except OSError as e:
        logger.error(f"OS error writing file: {e}")
        print(f"Error: Cannot write to '{file_path}': {e}", file=sys.stderr)
        return False
    
    except Exception as e:
        logger.error(f"Unexpected error saving file: {e}")
        print(f"Error: Failed to save '{file_path}': {e}", file=sys.stderr)
        return False

# ============================================================================
# Tab Processing Pipeline
# ============================================================================

def process_tab_generation(data: dict, logger: logging.Logger, validate_only: bool = False) -> Optional[str]:
    """
    Complete tab generation pipeline with comprehensive error reporting.
    
    This provides the same functionality as the MCP server but with
    more detailed error output suitable for developer debugging.
    The validate_only flag allows checking input without generating output.
    """
    logger.debug("Starting tab generation pipeline")
    
    # Check attempt limit if specified
    attempt = data.get('attempt', 1)
    if attempt > 1:
        logger.info(f"Processing attempt #{attempt}")
    
    attempt_error = check_attempt_limit(attempt)
    if attempt_error:
        logger.error(f"Attempt limit exceeded: {attempt}")
        print("Error: Maximum regeneration attempts exceeded", file=sys.stderr)
        print(f"  This appears to be attempt #{attempt} out of 5 maximum", file=sys.stderr)
        print("  Consider simplifying the tab or starting with a basic example", file=sys.stderr)
        return None
    
    # Run validation pipeline
    logger.debug("Running validation pipeline")
    validation_result = validate_tab_data(data)
    
    if validation_result["isError"]:
        logger.error("Validation failed")
        print("Validation Error:", file=sys.stderr)
        
        # Format error message for human readability
        error = validation_result
        print(f"  Type: {error.get('errorType', 'unknown')}", file=sys.stderr)
        
        if 'measure' in error:
            print(f"  Measure: {error['measure']}", file=sys.stderr)
        if 'beat' in error:
            print(f"  Beat: {error['beat']}", file=sys.stderr)
            
        print(f"  Problem: {error['message']}", file=sys.stderr)
        print(f"  Solution: {error['suggestion']}", file=sys.stderr)
        
        return None
    
    logger.info("Validation passed successfully")
    
    if validate_only:
        print("✓ Validation successful - input file is valid", file=sys.stderr)
        return ""  # Empty string indicates validation success
    
    # Generate tab output
    logger.debug("Generating tab output")
    try:
        tab_output, warnings = generate_tab_output(data)
        
        # Report any warnings to stderr
        if warnings:
            logger.warning(f"Generated tab with {len(warnings)} warnings")
            print(f"Warnings ({len(warnings)}):", file=sys.stderr)
            
            for warning in warnings:
                print(f"  Measure {warning.get('measure', '?')}, Beat {warning.get('beat', '?')}: {warning['message']}", file=sys.stderr)
        
        logger.info("Tab generation completed successfully")
        return tab_output
        
    except Exception as e:
        logger.error(f"Tab generation failed: {e}")
        print(f"Error: Tab generation failed: {e}", file=sys.stderr)
        return None

# ============================================================================
# Command Line Interface
# ============================================================================

def create_argument_parser() -> argparse.ArgumentParser:
    """
    Create command line argument parser with comprehensive options.
    
    Provides intuitive interface for both simple usage and advanced
    debugging scenarios. Help text is designed to be useful for
    developers who may not be familiar with the tab format.
    """
    parser = argparse.ArgumentParser(
        description="Generate ASCII guitar tablature from structured JSON input",
        epilog="""
Examples:
  %(prog)s input.json                    # Output tab to console
  %(prog)s input.json output.txt         # Save tab to file
  %(prog)s --validate input.json         # Check input validity only
  %(prog)s --verbose input.json          # Show detailed logging
  
For JSON format documentation, see the Guitar Tab Generation Specification.
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        'input_file',
        type=Path,
        help='JSON file containing guitar tab specification'
    )
    
    parser.add_argument(
        'output_file',
        type=Path,
        nargs='?',
        help='Output file for generated tab (default: print to console)'
    )
    
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate input file without generating tab output'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging for debugging'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='Guitar Tab Generator 0.1.0'
    )
    
    return parser

def main():
    """
    Main CLI entry point with comprehensive error handling.
    
    This function orchestrates the entire CLI workflow:
    1. Parse command line arguments
    2. Set up cross-platform environment
    3. Load and validate input
    4. Generate tab output
    5. Save or display results
    
    Exit codes follow Unix conventions:
    - 0: Success
    - 1: Input/output errors
    - 2: Validation errors
    - 3: Generation errors
    """
    # Set up cross-platform compatibility
    setup_cross_platform_environment()
    
    # Parse command line arguments
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Set up logging
    logger = setup_logging(args.verbose)
    
    # Load input file
    logger.info(f"Loading input file: {args.input_file}")
    data = load_json_file(args.input_file, logger)
    if data is None:
        sys.exit(1)  # File loading error
    
    # Process tab generation
    tab_output = process_tab_generation(data, logger, args.validate)
    if tab_output is None:
        sys.exit(2)  # Validation or generation error
    
    # Handle output
    if args.validate:
        # Validation-only mode
        logger.info("Validation completed successfully")
        sys.exit(0)
    
    elif args.output_file:
        # Save to file
        success = save_output_file(tab_output, args.output_file, logger)
        if not success:
            sys.exit(1)  # File writing error
        
        print(f"✓ Tab generated successfully: {args.output_file}")
        sys.exit(0)
    
    else:
        # Output to console
        print(tab_output)
        logger.info("Tab output sent to console")
        sys.exit(0)

# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(3)