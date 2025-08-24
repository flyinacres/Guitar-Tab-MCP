#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Guitar Tab Generator -  MCP Server with Parts System
===========================================================

 FastMCP server implementation with support for:
- Song parts/sections with automatic numbering (Verse 1, Chorus 1, etc.)
- Complete song structure definition
- Backwards compatibility with legacy measures format
- All existing  features (strum patterns, dynamics, grace notes, etc.)

New Parts System Features:
- Named song sections (Intro, Verse, Chorus, Bridge, Outro, etc.)
- Automatic numbering for repeated parts
- Song structure with part ordering
- Part-specific tempo/key/time signature changes

Usage:
    python mcp_server_parts.py

For Claude Desktop integration, add to config:
{
  "mcpServers": {
    "guitar-tab-generator": {
      "command": "python",
      "args": ["/path/to/mcp_server_parts.py"]
    }
  }
}
"""

import sys
import logging
import json
from typing import Dict, Any, List, Optional
from fastmcp import FastMCP
from pydantic import BaseModel

# Import  functionality with parts support
from core_with_parts import (
    validate_tab_data, generate_tab_output, 
    check_attempt_limit as check_attempt_limit
)
from tab_models import (
    TabRequest, TabResponse, 
    SongPart, PartInstance, analyze_song_structure
)
from tab_constants import (
    StrumDirection, DynamicLevel, ArticulationMark,
    VALID_EMPHASIS_VALUES, STRUM_POSITIONS_PER_MEASURE
)

# Configure logging to stderr (stdout reserved for MCP JSON-RPC protocol)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - MCP-TAB-PARTS - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# ============================================================================
#  MCP Server Setup with Parts System
# ============================================================================

# Initialize FastMCP server
mcp = FastMCP(" Guitar Tab Generator with Parts System")

@mcp.tool()
def generate_guitar_tab(tab_data: str) -> TabResponse:
    """
    Generate UTF-8 guitar tablature from structured JSON input with  features including song parts/sections.
    
    Converts guitar tab specifications into properly formatted UTF-8 tablature with 
    comprehensive support for musical notation, dynamics, strum patterns, advanced 
    guitar techniques, and complete song structure with named parts.
    
    Args:
        tab_data: Complete guitar tab specification with title, parts/measures, and structure
        
    Returns:
        TabResponse with generated tab content, warnings
        
    
    ## QUICK SMOKE TESTS (Gold Standard)

    These tests must ALWAYS work. Run these after any code changes:

    ### Test 1: Basic Chord with Standard Strum
    ```json
    {
      "title": "Basic Test",
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
    }
    ```
    Expected: Single G chord with `D   D   D U D U` strum pattern

    ### Parts-Based Song Structure
    Define reusable song sections with automatic numbering:
    ```json
    {
      "title": "Complete Song",
      "timeSignature": "4/4",
      "tempo": 120,
      "parts": {
        "Intro": {
          "measures": [
            {"events": [{"type": "chord", "beat": 1.0, "chordName": "G", "frets": [...]}]}
          ]
        },
        "Verse": {
          "description": "Main verse melody",
          "measures": [
            {"events": [...]},
            {"events": [...]},
            {"events": [...]},
            {"events": [...]}
          ]
        },
        "Chorus": {
          "measures": [
            {"events": [...]},
            {"events": [...]}
          ]
        },
        "Bridge": {
          "tempo_change": 100,
          "measures": [
            {"events": [...]}
          ]
        }
      },
      "structure": ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Bridge", "Chorus", "Chorus"]
    }
    ```
    
    ### Automatic Part Numbering
    Parts are automatically numbered based on their occurrence in the structure:
    - **Structure**: ["Intro", "Verse", "Chorus", "Verse", "Chorus"]
    - **Generated**: Intro 1 → Verse 1 → Chorus 1 → Verse 2 → Chorus 2
    
    ### Part Variations
    For different versions of the same section, use distinct names:
    ```json
    {
      "parts": {
        "Chorus": { "measures": [...] },
        "Chorus Alt": { "measures": [...] },
        "Chorus Outro": { "measures": [...] }
      },
      "structure": ["Verse", "Chorus", "Verse", "Chorus Alt", "Chorus Outro"]
    }
    ```
    **Generated**: Verse 1 → Chorus 1 → Verse 2 → Chorus Alt 1 → Chorus Outro 1
    
    ### Part-Specific Changes
    Parts can override global settings:
    ```json
    {
      "tempo": 120,
      "key": "G major",
      "parts": {
        "Bridge": {
          "tempo_change": 100,
          "key_change": "E minor",
          "measures": [...]
        }
      }
    }
    ```
    
    ### Common Part Names
    Standard song section names (case-sensitive):
    - **Intro** - Song introduction
    - **Verse** - Main verse sections  
    - **Chorus** - Repeating chorus/refrain
    - **Bridge** - Contrasting bridge section
    - **Solo** - Instrumental solo section
    - **Outro** - Song ending
    - **Pre-Chorus** - Lead-in to chorus
    - **Interlude** - Instrumental break
    - **Coda** - Final section
    
    ### Generated Output Format
    ```
    # Song Title
    **Time Signature:** 4/4 | **Tempo:** 120 BPM | **Key:** G major
    
    **Song Structure:**
    Intro 1 → Verse 1 → Chorus 1 → Verse 2 → Chorus 2 → Bridge 1 → Chorus 3
    
    **Parts Defined:**
    - **Intro**: 2 measures
    - **Verse**: 4 measures - Main verse melody
    - **Chorus**: 2 measures
    - **Bridge**: 2 measures
    
    ## Intro 1
    [tab content for intro]
    
    ## Verse 1
    [tab content for verse]
    
    ## Chorus 1
    [tab content for chorus]
    
    ## Verse 2
    [identical tab content for verse]
    
    ## Chorus 2
    [identical tab content for chorus]
    
    ## Bridge 1
    **Tempo:** 100 BPM | **Key:** E minor
    [tab content for bridge]
    
    ## Chorus 3
    [identical tab content for chorus]
    ```
    
    ##  Features (All Still Available)
    
    ### Strum Patterns
    Add strum direction indicators below tablature:
    ```json
    {
      "type": "strumPattern",
      "pattern": ["D", "U", "", "D", "U", "", "D", "U"],
      "measures": 1
    }
    ```
    
    ### Dynamics and Emphasis  
    Add musical expression to notes and chords:
    ```json
    {
      "type": "note",
      "string": 1,
      "beat": 1.0,
      "fret": 3,
      "emphasis": "f"
    }
    ```
    **Available**: pp, p, mp, mf, f, ff, cresc., dim., >, -, .
    
    ### Grace Notes
    Ornamental notes with special notation:
    ```json
    {
      "type": "graceNote",
      "string": 1,
      "beat": 2.0,
      "fret": 5,
      "graceFret": 3,
      "graceType": "acciaccatura"
    }
    ```
    **Output**: "(3)5" for quick grace note
    
    ### Guitar Techniques
    All techniques support emphasis and vibrato:
    - **hammerOn**: `{"type": "hammerOn", "string": 1, "startBeat": 1.0, "fromFret": 3, "toFret": 5, "vibrato": true, "emphasis": "mf"}`
    - **pullOff**: `{"type": "pullOff", "string": 1, "startBeat": 1.0, "fromFret": 5, "toFret": 3, "emphasis": "p"}`  
    - **slide**: `{"type": "slide", "string": 1, "startBeat": 1.0, "fromFret": 3, "toFret": 7, "direction": "up", "vibrato": true}`
    - **bend**: `{"type": "bend", "string": 1, "beat": 1.0, "fret": 7, "semitones": 1.5, "vibrato": true, "emphasis": "ff"}`
    
    ###  Annotations
    - **palmMute**: `{"type": "palmMute", "beat": 1.0, "duration": 2.0, "intensity": "heavy"}` → "PM(H)----"
    - **chuck**: `{"type": "chuck", "beat": 2.0, "intensity": "heavy"}` → "XH"
    
    ## Complete Example: Parts-Based Song
    
    ```json
    {
      "title": "Complete Song Example",
      "artist": "Demo Artist", 
      "timeSignature": "4/4",
      "tempo": 120,
      "key": "G major",
      "parts": {
        "Intro": {
          "description": "Fingerpicked introduction",
          "measures": [
            {
              "events": [
                {"type": "strumPattern", "pattern": ["", "", "", "", "", "", "", ""]},
                {"type": "note", "string": 1, "beat": 1.0, "fret": 3, "emphasis": "p"},
                {"type": "note", "string": 2, "beat": 1.5, "fret": 0},
                {"type": "note", "string": 3, "beat": 2.0, "fret": 0},
                {"type": "note", "string": 1, "beat": 3.0, "fret": 3}
              ]
            }
          ]
        },
        "Verse": {
          "description": "Main verse with chord progression",
          "measures": [
            {
              "events": [
                {"type": "strumPattern", "pattern": ["D", "", "U", "", "D", "U", "D", "U"]},
                {"type": "chord", "beat": 1.0, "chordName": "G", "emphasis": "mf", "frets": [
                  {"string": 6, "fret": 3}, {"string": 5, "fret": 2}, {"string": 1, "fret": 3}
                ]}
              ]
            },
            {
              "events": [
                {"type": "chord", "beat": 1.0, "chordName": "C", "frets": [
                  {"string": 5, "fret": 3}, {"string": 4, "fret": 2}, {"string": 2, "fret": 1}
                ]}
              ]
            },
            {
              "events": [
                {"type": "chord", "beat": 1.0, "chordName": "Em", "frets": [
                  {"string": 5, "fret": 2}, {"string": 4, "fret": 2}
                ]}
              ]
            },
            {
              "events": [
                {"type": "chord", "beat": 1.0, "chordName": "D", "frets": [
                  {"string": 4, "fret": 0}, {"string": 3, "fret": 2}, {"string": 2, "fret": 3}, {"string": 1, "fret": 2}
                ]}
              ]
            }
          ]
        },
        "Chorus": {
          "description": "Energetic chorus with palm muting",
          "measures": [
            {
              "events": [
                {"type": "strumPattern", "pattern": ["D", "", "", "D", "", "U", "D", "U"]},
                {"type": "chord", "beat": 1.0, "chordName": "G", "emphasis": "f", "frets": [
                  {"string": 6, "fret": 3}, {"string": 5, "fret": 2}, {"string": 1, "fret": 3}
                ]},
                {"type": "palmMute", "beat": 2.5, "duration": 1.0, "intensity": "medium"}
              ]
            },
            {
              "events": [
                {"type": "chord", "beat": 1.0, "chordName": "C", "emphasis": "f", "frets": [
                  {"string": 5, "fret": 3}, {"string": 4, "fret": 2}, {"string": 2, "fret": 1}
                ]},
                {"type": "chuck", "beat": 3.0, "intensity": "heavy"}
              ]
            }
          ]
        },
        "Bridge": {
          "description": "Slower bridge section",
          "tempo_change": 90,
          "measures": [
            {
              "events": [
                {"type": "strumPattern", "pattern": ["D", "", "", "", "D", "", "", ""]},
                {"type": "chord", "beat": 1.0, "chordName": "Am", "emphasis": "mp", "frets": [
                  {"string": 5, "fret": 0}, {"string": 4, "fret": 2}, {"string": 3, "fret": 2}, {"string": 2, "fret": 1}
                ]},
                {"type": "bend", "string": 1, "beat": 3.0, "fret": 5, "semitones": 0.5, "vibrato": true, "emphasis": "mf"}
              ]
            }
          ]
        }
      },
      "structure": ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Bridge", "Chorus", "Chorus"]
    }
    ```
    
    ## Backwards Compatibility
    
    The parts system is fully backwards compatible. Existing tabs using the legacy "measures" format continue to work:
    
    ```json
    {
      "title": "Legacy Format Still Works",
      "timeSignature": "4/4",
      "measures": [
        {"events": [{"type": "chord", "beat": 1.0, "chordName": "G", "frets": [...]}]},
        {"events": [{"type": "note", "string": 1, "beat": 1.0, "fret": 3}]}
      ]
    }
    ```
    
    ## Time Signature Support
    
    All time signatures support parts system:
    - **4/4**: 8 strum positions per measure
    - **3/4**: 6 strum positions per measure  
    - **2/4**: 4 strum positions per measure
    - **6/8**: 6 strum positions per measure (compound time)
    
    ## Error Handling & Validation
    
     validation for parts system:
    - **Part references**: All structure references must exist in parts
    - **Part uniqueness**: Part names must be unique
    - **Musical consistency**: Validates tempo/key/time signature changes
    - **Structure validation**: Ensures structure array is not empty
    
    Error messages provide specific guidance:
    ```json
    {
      "isError": true,
      "errorType": "validation_error",
      "message": "Structure references undefined part 'Vers' (typo?)",
      "suggestion": "Available parts: ['Intro', 'Verse', 'Chorus']. Check spelling."
    }
    ```
    
    ## Use Cases
    
    1. **Complete Songs**: Full song structure with multiple sections
    2. **Practice Exercises**: Repeated patterns with variations
    3. **Song Analysis**: Break down complex songs into learnable parts
    4. **Performance Planning**: Clear section markers for live performance
    5. **Teaching Materials**: Structured lessons with named sections
    
    The  parts system transforms the tab generator from a simple measure processor into a complete song structure tool, while maintaining full compatibility with existing functionality.
    """
    logger.info(f"Received  tab generation request with parts support")
    logger.debug(f"Request data type: {type(tab_data)}")
    
    try:
        # Parse and validate JSON input
        data_dict = json.loads(tab_data)
        logger.debug(f"Parsed JSON successfully, keys: {list(data_dict.keys())}")
        
        # Determine format and log accordingly
        if "parts" in data_dict and "structure" in data_dict:
            logger.info("Using new parts format")
            format_type = "parts"
        elif "measures" in data_dict:
            logger.info("Using legacy measures format")
            format_type = "legacy"
        else:
            logger.warning("Format unclear, attempting validation")
            format_type = "unknown"
        
        # Create  request model for validation
        try:
            request = TabRequest(**data_dict)
            logger.info(f" request validated: '{request.title}' (attempt {request.attempt}) - {format_type} format")
        except Exception as validation_error:
            logger.warning(f" model validation failed, using basic validation: {validation_error}")
            # Fall back to basic validation for backwards compatibility
            if "title" not in data_dict:
                data_dict["title"] = "Untitled"
            
        # Check attempt limit first to prevent infinite loops
        attempt = data_dict.get('attempt', 1)
        attempt_error = check_attempt_limit(attempt)
        if attempt_error:
            logger.warning(f"Attempt limit exceeded: {attempt}")
            return TabResponse(success=False, error=attempt_error)
        
        #  validation pipeline with parts support
        logger.debug("Starting  validation pipeline with parts support")
        validation_result = validate_tab_data(data_dict)
        if validation_result["isError"]:
            logger.warning(f" validation failed: {validation_result['message']}")
            return TabResponse(success=False, error=validation_result)
        
        logger.info(" validation with parts support passed successfully")
                                            
        # Generate  tab with parts and all new features
        logger.debug("Starting  tab generation with parts support")
        tab_output, warnings = generate_tab_output(data_dict)
        

        return TabResponse(
            success=True, 
            content=tab_output, 
            warnings=warnings
        )
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        return TabResponse(
            success=False, 
            error={
                "isError": True,
                "errorType": "json_error",
                "message": f"Invalid JSON format: {str(e)}",
                "suggestion": "Check JSON syntax - ensure proper quotes, brackets, and commas. For parts format, ensure 'parts' is an object and 'structure' is an array."
            }
        )
    
    except Exception as e:
        logger.error(f"Unexpected error during  tab generation with parts: {e}")
        return TabResponse(
            success=False, 
            error={
                "isError": True,
                "errorType": "processing_error",
                "message": f"Unexpected error during tab generation: {str(e)}",
                "suggestion": "Check input format and try again. For parts format, ensure part names in structure match parts definitions. For complex tabs, consider simplifying or breaking into sections."
            }
        )


# ============================================================================
#  MCP Server Startup with Parts System
# ============================================================================

def main():
    """
    Start the  MCP server with parts system.

    This runs the FastMCP server in stdio mode for integration with
    Claude Desktop and other MCP clients, with full support for
     guitar tab features including song parts and structure.
    """
    logger.info("Starting  Guitar Tab Generator MCP Server with Parts System")
    logger.info(" features available:")
    logger.info("  • Song parts/sections with automatic numbering")
    logger.info("  • Complete song structure definition")
    logger.info("  • Part-specific tempo/key/time signature changes")
    logger.info("  • Strum patterns, dynamics, grace notes")
    logger.info("  • Multi-layer display system")
    logger.info("  • Full backwards compatibility")
    
    # Log available constants for debugging
    logger.debug(f"Strum directions available: {[d.value for d in StrumDirection]}")
    logger.debug(f"Dynamic levels available: {[d.value for d in DynamicLevel]}")
    logger.debug(f"Time signature strum positions: {STRUM_POSITIONS_PER_MEASURE}")
    
    # Log parts system capabilities
    logger.debug("Parts system capabilities:")
    logger.debug("  • Automatic part instance numbering")
    logger.debug("  • Musical consistency validation")
    logger.debug("  • Legacy format backwards compatibility")
    logger.debug("  •  song structure analysis")
    
    try:
        mcp.run()
    except KeyboardInterrupt:
        logger.info(" MCP server with parts system stopped by user")
    except Exception as e:
        logger.error(f" MCP server with parts system error: {e}")
        raise

if __name__ == "__main__":
    main()
