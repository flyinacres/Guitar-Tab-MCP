#!/usr/bin/env python3
"""
Guitar Tab Generator - MCP Server Implementation
==============================================

FastMCP server implementation for LLM integration. This uses stdio transport
to communicate with Claude and other LLM clients through the Model Context Protocol.

Key MCP Implementation Details:
- stdio transport only (stdout for JSON-RPC, stderr for logging)
- Structured responses optimized for LLM parsing and error correction
- Attempt tracking to prevent infinite regeneration loops
- Comprehensive error messages with specific correction guidance

Usage:
    python mcp_server.py

For Claude Desktop integration, add to config:
{
  "mcpServers": {
    "guitar-tab-generator": {
      "command": "python",
      "args": ["/path/to/mcp_server.py"]
    }
  }
}
"""

import sys
import logging
import json
from typing import Dict, Any
from fastmcp import FastMCP
from pydantic import BaseModel

# Import our core functionality
from core import (
    TabRequest, TabResponse, 
    validate_tab_data, generate_tab_output, 
    check_attempt_limit
)

# Configure logging to stderr (stdout reserved for MCP JSON-RPC protocol)
logging.basicConfig(
    level=logging.INFO,  # Less verbose for production MCP server
    format='%(asctime)s - MCP-TAB - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# ============================================================================
# MCP Server Setup
# ============================================================================

# Initialize FastMCP server with descriptive metadata
mcp = FastMCP("Guitar Tab Generator")

@mcp.tool()
def generate_guitar_tab(tab_data: str) -> TabResponse:
    """
    Generate ASCII guitar tablature from structured JSON input.
    
    Converts guitar tab specifications (notes, chords, techniques) into properly
    formatted ASCII tablature with beat alignment. Provides structured error
    messages for LLM correction when input is invalid.
    
    Args:
        tab_data: Complete guitar tab specification with title, measures, and events
        
    Returns:
        TabResponse with generated tab content or structured error information
        
    Key Features:
    - Supports notes, chords, hammer-ons, pull-offs, slides, and bends
    - Validates timing against time signature constraints
    - Detects event conflicts (multiple notes on same string/beat)
    - Tracks attempt count to prevent infinite LLM regeneration loops
    - Provides warnings for formatting issues (multi-digit frets, etc.)

    JSON Structure:
    {
      "title": "string",
      "timeSignature": "4/4|3/4|6/8", 
      "measures": [{"events": [...]}]
    }
                                      
    Event types:
    - note: {"type": "note", "string": 1-6, "beat": 1.0-4.5, "fret": 0-24}
    - chord: {"type": "chord", "beat": 1.0-4.5, "frets": [{"string": 1-6, "fret": 0-24}]}
    - hammerOn: {"type": "hammerOn", "string": 1-6, "startBeat": 1.0-4.5, "fromFret": 0-24, "toFret": 0-24}
    - pullOff: {"type": "pullOff", "string": 1-6, "startBeat": 1.0-4.5, "fromFret": 0-24, "toFret": 0-24}  
    - slide: {"type": "slide", "string": 1-6, "startBeat": 1.0-4.5, "fromFret": 0-24, "toFret": 0-24, "direction": "up|down"}
    - bend: {"type": "bend", "string": 1-6, "beat": 1.0-4.5, "fret": 0-24, "bendType": "bend|release", "semitones": 0.5-2.0}
    """
    logger.info(f"Received data type: {type(tab_data)}")
    logger.info(f"Received data: {tab_data}")
    
    try:
        # Manually create TabRequest from dict
        data_dict = json.loads(tab_data)
        logger.info(f"Parsed data: {data_dict}")
        request = TabRequest(**data_dict)
        logger.info(f"Processing tab generation request: (attempt {request.attempt})")
                                
        # Check attempt limit first to prevent infinite loops
        attempt_error = check_attempt_limit(request.attempt)
        if attempt_error:
            logger.warning(f"Attempt limit exceeded: {request.attempt}")
            return TabResponse(success=False, error=attempt_error)
        
        # Validate input
        validation_result = validate_tab_data(data_dict)
        if validation_result["isError"]:
            logger.warning(f"Validation failed: {validation_result['message']}")
            return TabResponse(success=False, error=validation_result)
                                            
        # Generate tab with warnings
        tab_output, warnings = generate_tab_output(data_dict)
                                                  
        return TabResponse(success=True, content=tab_output, warnings=warnings)
    
    except Exception as e:
        logger.error(f"Unexpected error during tab generation: {e}")
        return TabResponse(
            success=False, 
            error={
                "isError": True,
                "errorType": "processing_error",
                "message": f"Unexpected error during tab generation: {str(e)}",
                "suggestion": "Check input format and try again"
            }
        )

# ============================================================================
# MCP Server Startup
# ============================================================================

def main():
    """
    Start the MCP server.

    This runs the FastMCP server in stdio mode for integration with
    Claude Desktop and other MCP clients.
    """
    logger.info("Starting Guitar Tab Generator MCP Server")
    mcp.run()

if __name__ == "__main__":
    main()
