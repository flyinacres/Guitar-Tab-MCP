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
def generate_guitar_tab(tab_data: TabRequest) -> TabResponse:
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
    """
    logger.info(f"Processing tab generation request: '{tab_data.title}' (attempt {tab_data.attempt})")
    
    try:
        # Check attempt limit first to prevent infinite loops
        attempt_error = check_attempt_limit(tab_data.attempt)
        if attempt_error:
            logger.warning(f"Attempt limit exceeded: {tab_data.attempt}")
            return TabResponse(success=False, error=attempt_error)
        
        # Convert Pydantic model to dict for