#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
    formatted ASCII tablature with beat alignment. Supports chord names, palm mutes,
    chucks, and string muting notation. Provides structured error messages for 
    LLM correction when input is invalid.
    
    Args:
        tab_data: Complete guitar tab specification with title, measures, and events
        
    Returns:
        TabResponse with generated tab content or structured error information
        
    Key Features:
    - Supports notes, chords, hammer-ons, pull-offs, slides, and bends (with semitone amounts)
    - Chord names displayed above tablature when provided
    - Palm mute notation (PM) with duration indicators above tab
    - Chuck notation (X) for percussive hits above tab
    - String muting using 'x' instead of fret numbers
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
                                      
    Event Types:
    
    Basic Events:
    - note: {"type": "note", "string": 1-6, "beat": 1.0-4.5, "fret": 0-24}
    - chord: {"type": "chord", "beat": 1.0-4.5, "frets": [{"string": 1-6, "fret": 0-24}]}
    
    Guitar Techniques:
    - hammerOn: {"type": "hammerOn", "string": 1-6, "startBeat": 1.0-4.5, "fromFret": 0-24, "toFret": 0-24}
    - pullOff: {"type": "pullOff", "string": 1-6, "startBeat": 1.0-4.5, "fromFret": 0-24, "toFret": 0-24}  
    - slide: {"type": "slide", "string": 1-6, "startBeat": 1.0-4.5, "fromFret": 0-24, "toFret": 0-24, "direction": "up|down"}
    - bend: {"type": "bend", "string": 1-6, "beat": 1.0-4.5, "fret": 0-24, "semitones": 0.25-3.0}
    
    Chord Names:
    - chord: {"type": "chord", "beat": 1.0-4.5, "chordName": "G", "frets": [{"string": 1-6, "fret": 0-24}]}
      Note: chordName is optional but will be displayed above tab when provided
    
    String Muting:
    - note: {"type": "note", "string": 1-6, "beat": 1.0-4.5, "fret": "x"}
    - chord: {"type": "chord", "beat": 1.0-4.5, "frets": [{"string": 1-6, "fret": "x"}]}
      Note: Use "x" instead of number for muted/dead strings
    
    Annotations (displayed above tablature):
    - palmMute: {"type": "palmMute", "beat": 1.0-4.5, "duration": 1.0-4.0}
      Creates "PM" with dashes showing duration: PM--------
    - chuck: {"type": "chuck", "beat": 1.0-4.5}
      Creates "X" above the specified beat for percussive hits
    
    Output Format Example:
    ```
    Chord:  G              Em        
    Annot:  PM------------ X    PM---
      1 & 2 & 3 & 4 &   1 & 2 & 3 & 4 &
    |-3---x---0-------|0---x---0---3---|
    |-0---x---0-------|0---x---0---0---|
    |-0---x---0-------|0---x---0---0---|
    |-0---x---2-------|2---x---2---0---|
    |-2---x---2-------|2---x---2---2---|
    |-3---x-----------|----x-----------|
    ```
    
    Notation Examples:
    - x = muted/dead string (no pitch)
    - 3h5 = hammer-on from 3rd to 5th fret
    - 5p3 = pull-off from 5th to 3rd fret
    - 3/5 = slide up from 3rd to 5th fret
    - 5\3 = slide down from 5th to 3rd fret

    Bend notation examples:
    - 7b½ = bend 7th fret up half semitone (quarter step)
    - 8b1 = bend 8th fret up 1 semitone (half step)
    - 9b1½ = bend 9th fret up 1.5 semitones (step and a half)
    - 12b2 = bend 12th fret up 2 semitones (whole step)
    - 5b¼ = quarter-tone bend at 5th fret
    
    Palm Mute Duration:
    - duration: 1.0 = PM covers 1 beat
    - duration: 2.5 = PM covers 2.5 beats (PM-----)
    - Dashes automatically calculated based on duration
    
    String Numbers:
    - 1 = high E string (thinnest)
    - 2 = B string  
    - 3 = G string
    - 4 = D string
    - 5 = A string
    - 6 = low E string (thickest)

    - 7~ = vibrato on 7th fret
    - 12b1½~ = bend with vibrato
    - 5h7~ = hammer-on with vibrato on destination note
    - 8/12~ = slide with vibrato on destination note

    JSON examples with vibrato:
    - note: {"type": "note", "string": 1, "beat": 1.0, "fret": 7, "vibrato": true}
    - bend: {"type": "bend", "string": 1, "beat": 1.0, "fret": 7, "semitones": 1.0, "vibrato": true}
    - hammerOn: {"type": "hammerOn", "string": 1, "startBeat": 1.0, "fromFret": 5, "toFret": 7, "vibrato": true}
    - slide: {"type": "slide", "string": 1, "startBeat": 1.0, "fromFret": 5, "toFret": 8, "direction": "up", "vibrato": true}

    Diminished chord examples:
    - C° = C diminished
    - F#°7 = F# diminished 7th
    - Bb° = Bb diminished
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
