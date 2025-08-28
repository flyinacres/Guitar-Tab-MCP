#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tab Generator - MCP Server Implementation
========================================================

FastMCP server implementation generates tabs for stringed instruments
Useful because LLMs struggle to align things like tabs properly, but seem
to be good at generating json that describes how the tabs should be layed out.


Usage:
    python mcp_server.py

For Claude Desktop integration, add to config:
{
  "mcpServers": {
    "tab-generator": {
      "command": "python",
      "args": ["/path/to/mcp_server.py"]
    }
  }
}
"""

import sys
import os
import logging
import json
import fastmcp
from typing import Dict, Any
from fastmcp import FastMCP

# Import  functionality
from tab_generation import (
    generate_tab_output,
    check_attempt_limit as check_attempt_limit
)

from time_signatures import STRUM_POSITIONS_PER_MEASURE
from validation import (
     validate_tab_data
)

from tab_models import (
  TabResponse, TabRequest, JSONError, ProcessingError, 
  analyze_song_structure, create_schema
)

from tab_constants import (
    StrumDirection, DynamicLevel
)

# Configure logging to stderr (stdout reserved for MCP JSON-RPC protocol)
logging.basicConfig(
    level=logging.DEBUG,  #  logging for new features
    format='%(asctime)s - MCP-TAB - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# ============================================================================
#  MCP Server Setup
# ============================================================================

# Initialize FastMCP server
mcp = FastMCP("Tab Generator")

@mcp.tool()
def generate_tab(tab_data: str) -> TabResponse:
    """
    Generate UTF-8 tablature for stringed instruments from structured JSON input.

    Converts tab specifications into properly formatted UTF-8 tablature with
    comprehensive support for musical notation, dynamics, strum patterns, and
    playing techniques. Provides structured error messages for correction
    when input is invalid.

    Args:
        tab_data: Complete tab specification with title, parts, and structure

    Returns:
        TabResponse with generated tab content and any warnings

    ## Input Format - Parts System

    The parts system allows definition of reusable song sections with automatic numbering:

    ```json
    {
      "title": "Song Title",
      "artist": "Artist Name",
      "instrument": "guitar",
      "timeSignature": "4/4",
      "tempo": 120,
      "key": "G major",
      "parts": {
        "Intro": {
          "description": "Song introduction",
          "measures": [
            {
              "strumPattern": ["D", "", "U", "", "D", "U", "D", "U"],
              "events": [
                {
                  "type": "chord",
                  "beat": 1.0,
                  "chordName": "G",
                  "frets": [
                    {"string": 6, "fret": 3},
                    {"string": 5, "fret": 2},
                    {"string": 1, "fret": 3}
                  ]
                }
              ]
            }
          ]
        },
        "Verse": {
          "measures": [...]
        },
        "Chorus": {
          "measures": [...]
        }
      },
      "structure": ["Intro", "Verse", "Chorus", "Verse", "Chorus"]
    }
    ```

    ## Supported Instruments

    ### Guitar (6-string)
    - Standard tuning: E-A-D-G-B-E
    - String numbering: 1 (high E) to 6 (low E)
    - Custom tunings supported

    ### Ukulele (4-string)
    ```json
    {
      "instrument": "ukulele",
      "parts": {
        "Main": {
          "measures": [
            {
              "events": [
                {
                  "type": "chord",
                  "beat": 1.0,
                  "chordName": "C",
                  "frets": [
                    {"string": 4, "fret": 0},
                    {"string": 3, "fret": 0},
                    {"string": 2, "fret": 0},
                    {"string": 1, "fret": 3}
                  ]
                }
              ]
            }
          ]
        }
      },
      "structure": ["Main"]
    }
    ```
    - Standard tuning: G-C-E-A
    - String numbering: 1 (A, highest) to 4 (G, lowest)

    ### Bass Guitar (4-string)
    - Standard tuning: E-A-D-G
    - String numbering: 1 (G, highest) to 4 (E, lowest)

    ### Mandolin (4-string)
    - Standard tuning: G-D-A-E
    - String numbering: 1 (E, highest) to 4 (G, lowest)

    ### Banjo (5-string)
    - Open G tuning: D-G-B-D-g
    - String numbering: 1 (high g) to 5 (drone string)

    ### Seven-String Guitar
    - Extended range: B-E-A-D-G-B-E
    - String numbering: 1 (high E) to 7 (low B)

    ## Song Structure System

    ### Automatic Part Numbering
    Parts are numbered based on their occurrence in the structure:
    - Structure: ["Intro", "Verse", "Chorus", "Verse", "Chorus"]
    - Generated: Intro 1 → Verse 1 → Chorus 1 → Verse 2 → Chorus 2

    ### Part Variations
    Create different versions using distinct names:
    ```json
    {
      "parts": {
        "Chorus": {"measures": [...]},
        "Chorus Alt": {"measures": [...]},
        "Chorus Outro": {"measures": [...]}
      },
      "structure": ["Verse", "Chorus", "Verse", "Chorus Alt", "Chorus Outro"]
    }
    ```

    ### Part-Specific Changes
    Override global settings per part:
    ```json
    {
      "tempo": 120,
      "key": "G major",
      "parts": {
        "Bridge": {
          "tempo_change": 90,
          "key_change": "E minor",
          "measures": [...]
        }
      }
    }
    ```

    ## Event Types

    ### Basic Events
    - **note**: `{"type": "note", "string": 1, "beat": 1.0, "fret": 3, "emphasis": "f"}`
    - **chord**: `{"type": "chord", "beat": 1.0, "chordName": "G", "frets": [...]}`

    ### Playing Techniques
    - **hammerOn**: `{"type": "hammerOn", "string": 1, "startBeat": 1.0, "fromFret": 3, "toFret": 5, "vibrato": true}`
    - **pullOff**: `{"type": "pullOff", "string": 1, "startBeat": 1.0, "fromFret": 5, "toFret": 3, "emphasis": "p"}`
    - **slide**: `{"type": "slide", "string": 1, "startBeat": 1.0, "fromFret": 3, "toFret": 7, "direction": "up"}`
    - **bend**: `{"type": "bend", "string": 1, "beat": 1.0, "fret": 7, "semitones": 1.5, "vibrato": true}`

    ### Ornamental Elements
    - **graceNote**: `{"type": "graceNote", "string": 1, "beat": 1.0, "fret": 5, "graceFret": 3, "graceType": "acciaccatura"}`
    - **palmMute**: `{"type": "palmMute", "beat": 1.0, "duration": 2.0, "intensity": "heavy"}`
    - **chuck**: `{"type": "chuck", "beat": 1.0, "intensity": "medium"}`

    ## Musical Expression

    ### Dynamics and Emphasis
    Available markings: `pp`, `p`, `mp`, `mf`, `f`, `ff`, `cresc.`, `dim.`, `<`, `>`, `-`, `.`

    ```json
    {
      "type": "chord",
      "beat": 1.0,
      "chordName": "G",
      "emphasis": "f",
      "frets": [...]
    }
    ```

    ### Grace Notes
    Ornamental notes with Unicode superscript notation:
    ```json
    {
      "type": "graceNote",
      "string": 1,
      "beat": 1.0,
      "fret": 5,
      "graceFret": 3,
      "graceType": "acciaccatura"
    }
    ```
    - **Acciaccatura**: ³5 (quick grace note)
    - **Appoggiatura**: ₃5 (grace note that takes time)

    ### Performance Techniques
    Palm muting and chucks with intensity levels:
    ```json
    {
      "type": "palmMute",
      "beat": 1.0,
      "duration": 2.0,
      "intensity": "heavy"
    }
    ```
    Output: Shows "PM(H)----" with intensity indicator

    ## Strum Patterns

    ### Measure-Level Strum Patterns
    Specify strum patterns per measure:
    ```json
    {
      "strumPattern": ["D", "", "U", "", "D", "U", "D", "U"],
      "events": [...]
    }
    ```

    ### Time Signature Support
    - **4/4**: 8 positions `["D","","U","","D","U","D","U"]`
    - **3/4**: 6 positions `["D","","U","","D","U"]`
    - **2/4**: 4 positions `["D","","U",""]`
    - **6/8**: 6 positions `["D","","","U","",""]`

    ### Strum Pattern Guidelines
    - Use "strumPattern" field at measure level, not as events
    - Valid values: "D" (down), "U" (up), "" (no strum/silence)
    - Pattern length must match time signature requirements
    - Empty positions ("") are required for proper spacing

    ### Common Strum Patterns
    - All down: `["D","","D","","D","","D",""]`
    - Down-up basic: `["D","","D","U","D","","D","U"]`
    - Chuck + strums: `["","","D","","D","","D","U"]` + chuck event

    ## Bend Notation

    Precise semitone control with Unicode fractions:
    - `0.25` → "¼" (quarter step)
    - `0.5` → "½" (half step)
    - `1.0` → "1" (whole step)
    - `1.5` → "1½" (step and a half)
    - `2.0` → "2" (whole tone)

    ## String Techniques

    ### Muted Strings
    Use `"fret": "x"` for dead/muted strings:
    ```json
    {
      "type": "chord",
      "beat": 1.0,
      "chordName": "D5",
      "frets": [
        {"string": 6, "fret": "x"},
        {"string": 5, "fret": "x"},
        {"string": 4, "fret": 0},
        {"string": 3, "fret": 2}
      ]
    }
    ```

    ### Custom Tunings
    Support for alternate tunings with validation:
    ```json
    {
      "instrument": "guitar",
      "tuning": ["D", "A", "D", "G", "B", "E"],
      "tuning_name": "Drop D",
      "parts": {...}
    }
    ```

    ## Output Format

    Generated tabs include multiple display layers:
    1. **Chord names** (when present)
    2. **Dynamics** (when present)
    3. **Annotations** (PM, X, emphasis markings)
    4. **Beat markers**
    5. **Tab content** (string lines)
    6. **Strum patterns** (when present)

    ```
    # Song Title
    **Time Signature:** 4/4 | **Tempo:** 120 BPM | **Key:** G major

    **Song Structure:**
    Intro 1 → Verse 1 → Chorus 1 → Verse 2 → Chorus 2

    ## Verse 1
    *Main verse section*

     G                 Em
     mf
      1 & 2 & 3 & 4 &   1 & 2 & 3 & 4 &
    E |-3---------------|-0---------------|
    B |-0---------------|-0---------------|
    G |-0---------------|-0---------------|
    D |-0---------------|-2---------------|
    A |-2---------------|-2---------------|
    E |-3---------------|-0---------------|
      D   D U   U D U   D   D U   U D U
    ```

    ## Error Handling

    Provides structured error messages for validation issues:
    ```json
    {
      "isError": true,
      "errorType": "validation_error",
      "measure": 1,
      "beat": 4.7,
      "message": "Beat 4.7 invalid for 4/4 time signature",
      "suggestion": "Use valid beat values: 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5"
    }
    ```

    ### Common Validation Errors
    - **Invalid beats**: Beat values that don't match time signature
    - **Technique direction**: Hammer-ons must go up, pull-offs must go down
    - **String ranges**: Must match instrument (Guitar: 1-6, Ukulele: 1-4, etc.)
    - **Part references**: Structure must reference defined parts
    - **Strum pattern length**: Must match time signature requirements

    ## Musical Theory Guidelines

    ### Chord Placement and Timing
    - Single chord measures: Place chord on beat 1.0
    - Split chord measures: Place first chord on beat 1.0, second on beat 3.0
    - Down strums typically occur on numbered beats: 1, 2, 3, 4
    - Up strums typically occur on & beats: 1&, 2&, 3&, 4&
    - Chuck events: Always use beat 1.0 with empty strum position

    ### Performance Instructions
    Use description fields for playing guidance:
    ```json
    {
      "title": "Song Title",
      "description": "Overall style guidance",
      "parts": {
        "Intro": {
          "description": "Fingerpick arpeggios",
          "measures": [...]
        },
        "Verse": {
          "description": "Strum loosely, palm mute on downbeats",
          "measures": [...]
        }
      }
    }
    ```

    Common performance instructions:
    - Chord techniques: "Let chords ring", "Strum arpeggios", "Fingerpick chord notes"
    - Timing: "Syncopated rhythm", "Chord pushed from previous measure"
    - Touch: "Palm mute throughout", "Light strum", "Aggressive picking"
    - Style: "Country fingerpicking", "Classical technique", "Blues shuffle feel"

    ## Usage Examples

    ### Basic Chord Progression
    ```json
    {
      "title": "Basic Chord Test",
      "timeSignature": "4/4",
      "parts": {
        "Main": {
          "measures": [
            {
              "strumPattern": ["D", "", "D", "", "D", "U", "D", "U"],
              "events": [
                {
                  "type": "chord",
                  "beat": 1.0,
                  "chordName": "G",
                  "frets": [
                    {"string": 6, "fret": 3},
                    {"string": 5, "fret": 2},
                    {"string": 1, "fret": 3}
                  ]
                }
              ]
            }
          ]
        }
      },
      "structure": ["Main"]
    }
    ```

    ### Playing Techniques Example
    ```json
    {
      "title": "Technique Showcase",
      "timeSignature": "4/4",
      "parts": {
        "Main": {
          "measures": [
            {
              "events": [
                {
                  "type": "hammerOn",
                  "string": 1,
                  "startBeat": 1.0,
                  "fromFret": 3,
                  "toFret": 5,
                  "vibrato": true
                },
                {
                  "type": "bend",
                  "string": 2,
                  "beat": 2.0,
                  "fret": 7,
                  "semitones": 1.5,
                  "emphasis": "f"
                },
                {
                  "type": "slide",
                  "string": 3,
                  "startBeat": 3.0,
                  "fromFret": 5,
                  "toFret": 8,
                  "direction": "up"
                }
              ]
            }
          ]
        }
      },
      "structure": ["Main"]
    }
    ```

    ### Multi-Instrument Song
    ```json
    {
      "title": "Ukulele Song",
      "instrument": "ukulele",
      "timeSignature": "3/4",
      "parts": {
        "Main": {
          "measures": [
            {
              "strumPattern": ["D", "", "D", "", "D", "U"],
              "events": [
                {
                  "type": "chord",
                  "beat": 1.0,
                  "chordName": "C",
                  "frets": [
                    {"string": 4, "fret": 0},
                    {"string": 3, "fret": 0},
                    {"string": 2, "fret": 0},
                    {"string": 1, "fret": 3}
                  ]
                }
              ]
            }
          ]
        }
      },
      "structure": ["Main"]
    }
    ```

    ## Technique Formatting

    Control the visual style of musical techniques:

    ```json
    {
      "title": "Compact Solo",
      "techniqueStyle": "alternating",
      "parts": {
        "Solo": {
          "measures": [
            {
              "events": [
                {"type": "hammerOn", "string": 1, "startBeat": 1.0, "fromFret": 3, "toFret": 5},
                {"type": "bend", "string": 2, "startBeat": 2.0, "fret": 7, "semitones": 1.5}
              ]
            }
          ]
        }
      }
    }
    ```

    Available styles:

    "regular": Standard notation (3h5, 7b1½)
    "superscript": All superscript (³ʰ⁵, ⁷ᵇ¹½)
    "subscript": All subscript (₃ₕ₅, ₇ᵦ₁½)
    "alternating": Alternates to prevent collisions (³ʰ⁵, ₇ᵦ₁½)

    Recommended: Use "alternating" for dense solo passages with many techniques.


    ## Important Notes

    - Display the generated tab content exactly as returned without modification
    - Use fixed-width/monospace font for proper alignment
    - Tab content requires precise character positioning for musical accuracy
    - The tool handles complex musical notation automatically
    - Multiple display layers provide comprehensive musical information
    - Warnings indicate potential formatting issues but don't prevent generation
    """
    logger.info(f"Received tab generation request")
    logger.debug(f"Request data type: {type(tab_data)}")

    try:
        # Parse and validate JSON input
        data_dict = json.loads(tab_data)
        logger.debug(f"Parsed JSON successfully, keys: {list(data_dict.keys())}")

        # Create  request model for validation
        try:
            request = TabRequest(**data_dict)
            logger.info(f" request validated: '{request.title}' (attempt {request.attempt})")
        except Exception as validation_error:
            logger.error(f" model validation failed, using basic validation: {validation_error}")
            return None

        # Check attempt limit first to prevent infinite loops
        attempt = request.attempt
        attempt_error = check_attempt_limit(attempt)
        if attempt_error:
            logger.warning(f"Attempt limit exceeded: {attempt}")
            return TabResponse(success=False, error=attempt_error)

        #  validation pipeline
        logger.debug("Starting  validation pipeline")
        validation_result = validate_tab_data(request)
        if validation_result:
            logger.warning(f" validation failed: {validation_result.message}")
            return TabResponse(success=False, error=validation_result)

        logger.info("Validation passed successfully")

        # Generate  tab with all new features
        logger.debug("Starting  tab generation")
        return generate_tab_output(request)

    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        return TabResponse(
            success = False,
            error = JSONError(
                message = f"Invalid JSON format: {str(e)}",
                suggestion = "Check JSON syntax - ensure proper quotes, brackets, and commas"
            )
        )

    except Exception as e:
        logger.error(f"Unexpected error during tab generation: {e}")
        return TabResponse(
            success = False,
            error = ProcessingError(
                message = f"Unexpected error during tab generation: {str(e)}",
                suggestion = "Check input format and try again. For complex tabs, consider simplifying or breaking into sections."
            )
        )


@mcp.tool()
def analyze_song_structure_tool(tab_data: str) -> Dict[str, Any]:
    """
    Analyze song structure without generating tablature.

    Useful for validating parts format and understanding song organization
    before generating the full tab.

    Args:
        tab_data: tab specification in parts format

    Returns:
        Dictionary with detailed song structure analysis
    """
    logger.info("Received song structure analysis request")

    try:
        data_dict = json.loads(tab_data)
        request = TabRequest(**data_dict)

        if not (request.parts and request.structure):
            return {
                "error": "Song structure analysis requires parts format (parts + structure)",
                "suggestion": "Use parts format with 'parts' object and 'structure' array"
            }

        analysis = analyze_song_structure(request)
        logger.info(f"Generated structure analysis for '{request.title}': {analysis['total_part_instances']} instances")

        # Add additional analysis
        analysis["validation"] = validate_tab_data(request)
        analysis["title"] = request.title
        analysis["inputValid"] = not analysis["validation"]["isError"]

        return {
            "success": True,
            "analysis": analysis,
            "partsPreview": {
                part_name: {
                    "measureCount": len(part_def.measures),
                    "description": part_def.description,
                    "hasTempoChange": part_def.tempo_change is not None,
                    "hasKeyChange": part_def.key_change is not None
                }
                for part_name, part_def in request.parts.items()
            }
        }

    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error in structure analysis: {e}")
        return {
            "success": False,
            "error": f"Invalid JSON format: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Error in structure analysis: {e}")
        return {
            "success": False,
            "error": f"Analysis error: {str(e)}"
        }

@mcp.tool()
def get_json_schema() -> Dict[str, Any]:
    """
    Get the JSON Schema for the Tab Generator API.
    
    Returns the complete JSON Schema specification that defines the valid
    input format for tab generation, including all event types, instruments,
    time signatures, and the parts system structure.
    
    Returns:
        Complete JSON Schema for guitar tab generation requests
    """
    return {
        "schema": create_schema(),
        "version": "1.0.0",  # Version goes here, not in schema
        "api_version": "2024.1",
        "documentation": "https://github.com/yourusername/guitar-tab-generator"
    }

# ============================================================================
#  MCP Server Startup
# ============================================================================

def main():
    """Start the MCP server in appropriate mode based on environment."""
    
    # Detect if running in production (common environment variables)
    is_production = any([
        os.getenv('RENDER'),           # Render
        os.getenv('PORT'),             # Most cloud platforms
    ])
    
    # Check if stdio is available (local testing)
    has_stdio = sys.stdin.isatty() and sys.stdout.isatty()
    
    if is_production or not has_stdio:
        # For hosting on Render, use these values
        port = int(os.environ.get("PORT", 8001))

        # Production: use SSE mode
        logger.info("Starting MCP server in SSE mode")
        mcp.run(transport='sse', host="0.0.0.0", port=port)
    else:
        # Local: use stdio mode  
        logger.info("Starting MCP server in stdio mode")
        mcp.run()

if __name__ == "__main__":
    main()
