#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tab Generator - MCP Server Implementation
========================================================

FastMCP server implementation with support for:
- Song parts/sections with automatic numbering (Verse 1, Chorus 1, etc.)
- Complete song structure definition
- Strum patterns and direction indicators
- Dynamic and emphasis markings  
- Grace notes and advanced techniques
- Multi-layer display system
- Validation and error reporting

Key MCP Implementation Details:
- stdio transport only (stdout for JSON-RPC, stderr for logging)
- Structured responses optimized for LLM parsing and error correction
- Attempt tracking to prevent infinite regeneration loops
- Comprehensive documentation with examples for all new features

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
from typing import Dict, Any, List, Optional
from fastmcp import FastMCP
from pydantic import BaseModel

# Import  functionality
from core import (
    generate_tab_output, 
    check_attempt_limit as check_attempt_limit
)

from validation import (
     validate_tab_data
)

from tab_models import TabResponse, TabRequest
from tab_constants import (
    StrumDirection, DynamicLevel, ArticulationMark,
    VALID_EMPHASIS_VALUES, STRUM_POSITIONS_PER_MEASURE
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
mcp = FastMCP(" Guitar Tab Generator")

@mcp.tool()
def generate_guitar_tab(tab_data: str) -> TabResponse:
    """
    Generate UTF-8 guitar tablature from structured JSON input with  features.
    
    Converts guitar tab specifications into properly formatted UTF-8 tablature with 
    comprehensive support for musical notation, dynamics, strum patterns, and 
    advanced guitar techniques. Provides structured error messages for LLM correction 
    when input is invalid.
    
    Args:
        tab_data: Complete guitar tab specification with title, measures, and events
        
    Returns:
        TabResponse with generated tab content, warnings
        
    ##  Features (NEW)
    
    ### Strum Patterns
    Create strum direction indicators below the tablature:
    ```json
    {
      "type": "strumPattern",
      "startBeat": 1.0,
      "pattern": ["D", "U", "", "D", "U", "", "D", "U"],
      "measures": 1
    }
    ```
    **Output:** Shows "D U  D U  D U" below the tab content

    STRUM PATTERN GUIDELINES FOR LLM USAGE:

    Per-Measure Strum Patterns (RECOMMENDED APPROACH):
    - Use "strumPattern" field at measure level, not as events
    - Each measure gets exactly 8 positions for 4/4 time: ["D","","U","","D","U","D","U"]
    - Position mapping: [1, &, 2, &, 3, &, 4, &]
    - Valid values: "D" (down), "U" (up), "" (no strum/silence)

    Common LLM Mistakes to Avoid:
    - Don't use "X" in strum patterns - use chuck events + empty strum position
    - Map musical patterns to beat grid: "D D DU" = ["D","","D","","D","U","",""]
    - "DU" always means down on one beat, up on the next (&) beat
    - Empty positions ("") are required for proper spacing

    Example Correct Usage:
    {
      "strumPattern": ["", "", "D", "", "D", "", "D", "U"],  // Chuck on 1, strums on 2,3,4&
      "events": [
        {"type": "chuck", "beat": 1.0},
        {"type": "chord", "beat": 1.0, "chordName": "Em", "frets": [...]}
      ]
    }


    CHORD PLACEMENT AND STRUM PATTERN ALIGNMENT:

    Musical Theory Rules (CRITICAL):
    - Assume D (down strums) occur on numbered beats: 1, 2, 3, 4 unless the chord pattern clearly states otherwise (such as all down strums for all beats)
    - Assume U (up strums) occur on & beats: 1&, 2&, 3&, 4&, unless otherwise specified
    - Chords are often placed on downbeats (numbered beats) unless specifically noted
    - Never place chords on & beats without explicit instruction

    - If the measure has multiple chords you may need to ask to understand where to place the chords in the measure. Two chords often (but not always) split a measure evenly.

    Common LLM Errors to Avoid:
    - Always verify chord placement matches the intended strum positions

    Verification Steps:
    1. Check that chord placement beats match the intended strum positions

    ### Dynamics and Emphasis
    Add musical dynamics to any note or chord:
    ```json
    {
      "type": "note",
      "string": 1,
      "beat": 1.0,
      "fret": 3,
      "emphasis": "f"
    }
    ```
    **Dynamics:** pp, p, mp, mf, f, ff, cresc., dim., <, >
    **Articulations:** >, -, ., staccato markings
    
    ### Grace Notes
    Add ornamental grace notes with clean superscript notation:
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
   Output:

   Acciaccatura: ³5 (quick grace note)
   Appoggiatura: ₃5 (grace note that takes time)

   Benefits: Cleaner, more compact, musical notation using Unicode superscripts.

    ###  Annotations
    Improved palm mutes and chucks with intensity:
    ```json
    {
      "type": "palmMute",
      "beat": 1.0,
      "duration": 2.0,
      "intensity": "heavy"
    }
    ```
    **Output:** Shows "PM(H)----" with intensity indicator
    
    ## Core Features ()
    
    ### Basic Events
    - **note**: `{"type": "note", "string": 1-6, "beat": 1.0-4.5, "fret": 0-24, "emphasis": "f"}`
    - **chord**: `{"type": "chord", "beat": 1.0-4.5, "chordName": "G", "frets": [...], "emphasis": ">"}`
    
    ### Guitar Techniques (All support emphasis and vibrato)
    - **hammerOn**: `{"type": "hammerOn", "string": 1-6, "startBeat": 1.0, "fromFret": 3, "toFret": 5, "vibrato": true, "emphasis": "mf"}`
    - **pullOff**: `{"type": "pullOff", "string": 1-6, "startBeat": 1.0, "fromFret": 5, "toFret": 3, "emphasis": "p"}`  
    - **slide**: `{"type": "slide", "string": 1-6, "startBeat": 1.0, "fromFret": 3, "toFret": 7, "direction": "up", "vibrato": true}`
    - **bend**: `{"type": "bend", "string": 1-6, "beat": 1.0, "fret": 7, "semitones": 1.5, "vibrato": true, "emphasis": "ff"}`
    
    ### Advanced Bend Notation ()
    Precise semitone control with Unicode fractions:
    - `0.25` → "¼" (quarter step)
    - `0.5` → "½" (half step) 
    - `1.0` → "1" (whole step)
    - `1.5` → "1½" (step and a half)
    - `2.0` → "2" (whole tone)
    
    ###  Annotations
    - **palmMute**: `{"type": "palmMute", "beat": 1.0, "duration": 2.0, "intensity": "light|medium|heavy"}`
    - **chuck**: `{"type": "chuck", "beat": 2.0, "intensity": "heavy"}` → Shows "XH"
    
    ### String Muting ()
    - **Muted strings**: Use `"fret": "x"` for dead/muted strings in notes and chords
    - **Emphasis on muted**: `{"type": "note", "string": 1, "beat": 1.0, "fret": "x", "emphasis": ">"}`
    
    ## Time Signature Support ()
    
    ### Supported Time Signatures
    - **4/4**: 8 strum positions per measure `["D","","U","","D","U","D","U"]`
    - **3/4**: 6 strum positions per measure `["D","","U","","D","U"]`
    - **2/4**: 4 strum positions per measure `["D","","U",""]`  
    - **6/8**: 6 strum positions per measure `["D","","","U","",""]` (compound time)
    
    ### Strum Pattern Validation
    - Pattern length must match time signature requirements
    - Patterns can span multiple measures evenly
    - Valid directions: "D" (down), "U" (up), "" (no strum)
    
    ##  JSON Structure
    
    ```json
    {
      "title": "Song Title",
      "artist": "Artist Name",
      "description": "Song description",
      "timeSignature": "4/4",
      "tempo": 120,
      "key": "G major",
      "capo": 2,
      "attempt": 1,
      "showStrumPattern": true,
      "showDynamics": true,
      "measures": [
        {
          "events": [
            {
              "type": "strumPattern",
              "pattern": ["D", "", "U", "", "D", "U", "D", "U"],
              "measures": 2
            },
            {
              "type": "chord",
              "beat": 1.0,
              "chordName": "G",
              "emphasis": "mf",
              "frets": [
                {"string": 6, "fret": 3},
                {"string": 5, "fret": 2},
                {"string": 1, "fret": 3}
              ]
            },
            {
              "type": "palmMute",
              "beat": 2.5,
              "duration": 1.0,
              "intensity": "medium"
            },
            {
              "type": "graceNote",
              "string": 1,
              "beat": 3.0,
              "fret": 5,
              "graceFret": 3,
              "graceType": "acciaccatura"
            }
          ]
        }
      ]
    }
    ```
    
    ##  Output Format
    
    ```
    # Song Title
    **Artist:** Artist Name
    *Song description*
    **Time Signature:** 4/4 | **Tempo:** 120 BPM | **Key:** G major | **Capo:** 2
    
      G              Em            
      mf             p             
          PM(M)--        X     >   
      1 & 2 & 3 & 4 &   1 & 2 & 3 & 4 &  
    |-3------(3)5------|0---x---7b1½~----|
    |-0---------------|0---x------------|
    |-0---------------|0---x------------|
    |-0---------------|2---x------------|
    |-2---------------|2---x------------|
    |-3---------------|0---x------------|
      D   U   D U D U   D   U   D U D U
    ```
    
    ##  Error Messages
    
    The system provides detailed error messages for:
    - **Invalid strum patterns**: Length mismatches, invalid directions
    - **Emphasis validation**: Invalid dynamic markings, incompatible combinations  
    - **Grace note conflicts**: Missing target notes, timing issues
    - **Advanced technique validation**: Complex bend/vibrato/emphasis combinations
    
    ## Musical Examples
    
    ### Rock Power Chord with Strum Pattern
    ```json
    {
      "title": "Power Chord Rock",
      "timeSignature": "4/4", 
      "measures": [
        {
          "events": [
            {"type": "strumPattern", "pattern": ["D","","","D","","U","D","U"]},
            {"type": "chord", "beat": 1.0, "chordName": "E5", "emphasis": "f", "frets": [{"string": 6, "fret": 0}, {"string": 5, "fret": 2}]},
            {"type": "chord", "beat": 2.5, "chordName": "E5", "emphasis": ">", "frets": [{"string": 6, "fret": 0}, {"string": 5, "fret": 2}]},
            {"type": "palmMute", "beat": 3.0, "duration": 1.0, "intensity": "heavy"}
          ]
        }
      ]
    }
    ```
    
    ### Classical Grace Note Passage  
    ```json
    {
      "title": "Classical Ornaments",
      "timeSignature": "3/4",
      "measures": [
        {
          "events": [
            {"type": "graceNote", "string": 1, "beat": 1.0, "fret": 5, "graceFret": 3, "emphasis": "p"},
            {"type": "note", "string": 1, "beat": 2.0, "fret": 7, "emphasis": "cresc."},
            {"type": "bend", "string": 1, "beat": 3.0, "fret": 9, "semitones": 0.5, "vibrato": true, "emphasis": "f"}
          ]
        }
      ]
    }
    ```
    
    ### Jazz Chord Progression with Dynamics
    ```json
    {
      "title": "Jazz Changes", 
      "timeSignature": "4/4",
      "measures": [
        {
          "events": [
            {"type": "chord", "beat": 1.0, "chordName": "Cmaj7", "emphasis": "mp", "frets": [{"string": 5, "fret": 3}, {"string": 4, "fret": 2}, {"string": 3, "fret": 0}, {"string": 2, "fret": 0}]},
            {"type": "chord", "beat": 3.0, "chordName": "Am7", "emphasis": "mf", "frets": [{"string": 5, "fret": 0}, {"string": 4, "fret": 2}, {"string": 3, "fret": 0}, {"string": 2, "fret": 1}]}
          ]
        }
      ]
    }
    ```
    
    ## Compatibility Notes
    
    - **Backwards Compatible**: All existing JSON structures continue to work
    - **Progressive Enhancement**: New features are optional - tabs work without them
    - **Graceful Degradation**: Invalid emphasis/strum patterns generate warnings, not errors
    - **LLM Optimized**: Error messages designed for easy LLM understanding and correction
    
    ## Common Use Cases
    
    1. **Learning Strum Patterns**: Add strum direction indicators for practice
    2. **Musical Expression**: Use dynamics to indicate volume and articulation changes  
    3. **Advanced Techniques**: Combine bends, vibrato, and emphasis for realistic notation
    4. **Educational Content**: Grace notes and ornaments for classical guitar instruction
    5. **Genre-Specific Notation**: Palm mutes for metal, chucks for reggae, dynamics for classical
    
    The  system maintains full compatibility while adding professional-level 
    musical notation capabilities to UTF-8 guitar tablature.

    ## Strum Patterns (Measure Level)

    Specify strum patterns per measure for maximum flexibility:

    ```json
    {
      "timeSignature": "4/4",
      "measures": [
        {
          "strumPattern": ["D", "", "U", "", "D", "U", "D", "U"],
          "events": [{"type": "chord", ...}]
        },
        {
          "strumPattern": ["D", "", "", "D", "", "U", "D", "U"], 
          "events": [{"type": "chord", ...}]
        },
        {
          "events": [{"type": "chord", ...}]  // No strum pattern
        }
      ]
    }

    Strum Pattern Length Requirements:

    4/4 time: 8 positions ["D","","U","","D","U","D","U"]
    3/4 time: 6 positions ["D","","U","","D","U"]
    2/4 time: 4 positions ["D","","U",""]
    6/8 time: 6 positions ["D","","","U","",""]

    Valid Values:

    "D" = Down strum
    "U" = Up strum
    "" = No strum (silence)

    Notes:

    Strum patterns are optional per measure
    Each measure can have different patterns
    Length must exactly match time signature

    ### Performance Instructions and Comments

    Use description fields to provide playing instructions and style guidance:

    ```json
    {
      "title": "Song Title",
      "description": "Overall style guidance (e.g., 'Let chords ring throughout')",
      "parts": {
        "Intro": {
          "description": "Specific technique for this part (e.g., 'Fingerpick arpeggios')",
          "measures": [...]
        },
        "Verse": {
          "description": "Style changes (e.g., 'Strum loosely, palm mute on downbeats')",
          "measures": [...]
        }
      }
    }
    Common Performance Instructions:

    Chord techniques: "Let chords ring", "Strum arpeggios", "Fingerpick chord notes"
    Timing: "Chord pushed from previous measure", "Syncopated rhythm"
    Touch: "Palm mute throughout", "Light strum", "Aggressive picking"
    Style: "Country fingerpicking", "Classical technique", "Blues shuffle feel"
    Arpeggio: "Inital chords in each verse measure are played as a quick arpeggio"

    Note that if the Arpeggio is quite slow, the chord can be broken into individual notes and added to the tab


    ### Lyrics Support

    Lyrics can be manually added below guitar tabs. Since lyrics timing rarely matches measure boundaries, manual formatting provides the best results.

    **Basic Format:**
    Add lyrics after the tab content using natural spacing and line breaks.

    **Guidelines for LLMs:**
    - Add lyrics AFTER generating the complete tab
    - Use manual spacing - don't force alignment with measures  
    - Break lyrics naturally across multiple lines if needed
    - Use part descriptions for vocal techniques ("harmony", "falsetto")
    - Show verse/chorus structure clearly

    **Example Output:**
    Song Title
    [complete tab here]
    Verse 1: "First line of lyrics here
    Second line continues here"
    Chorus: "Chorus lyrics with natural breaks
    Don't worry about measure alignment"

    **Chord-Lyric Timing:**
    Only attempt alignment when chords clearly match lyric syllables. Most songs work better with separate lyric sections below the tab.
    
    **Multiple Verses:**
    Verse 1
    [tab content]
    Verse 1 lyrics...
    Chorus 1
    [tab content]
    Chorus lyrics...
    Verse 2
    [tab content]
    Verse 2 lyrics (different words, same chords)...


    ## Ukulele Support

    The tab generator now supports both guitar and ukulele with automatic string count and validation.

    ### Basic Usage
    ```json
    {
      "title": "Ukulele Song",
      "instrument": "ukulele",
      "timeSignature": "4/4",
      "measures": [
        {
          "events": [
            {"type": "chord", "beat": 1.0, "chordName": "C", "frets": [
              {"string": 4, "fret": 0},
              {"string": 3, "fret": 0},
              {"string": 2, "fret": 0},
              {"string": 1, "fret": 3}
            ]}
          ]
        }
      ]
    }
    Instrument Field
    
    "guitar" (default) - 6 strings, standard tuning
    "ukulele" - 4 strings, high G tuning (G-C-E-A)
    
    Ukulele String Numbering

    String 1: A (highest pitch)
    String 2: E
    String 3: C
    String 4: G (lowest pitch)
    
    Common Ukulele Chords
    json// C major - easiest ukulele chord
    {
      "type": "chord",
      "chordName": "C",
      "frets": [
        {"string": 4, "fret": 0},
        {"string": 3, "fret": 0},
        {"string": 2, "fret": 0},
        {"string": 1, "fret": 3}
      ]
    }

    // G major
    {
      "type": "chord", 
      "chordName": "G",
      "frets": [
        {"string": 4, "fret": 3},
        {"string": 3, "fret": 2},
        {"string": 2, "fret": 0},
        {"string": 1, "fret": 2}
      ]
    }

    // A minor
    {
      "type": "chord",
      "chordName": "Am", 
      "frets": [
        {"string": 4, "fret": 2},
        {"string": 3, "fret": 0},
        {"string": 2, "fret": 0},
        {"string": 1, "fret": 0}
      ]
    }

    // F major
    {
      "type": "chord",
      "chordName": "F",
      "frets": [
        {"string": 4, "fret": 2},
        {"string": 3, "fret": 0}, 
        {"string": 2, "fret": 1},
        {"string": 1, "fret": 0}
      ]
    }
    Ukulele Techniques
    All guitar techniques work on ukulele:
    json// Hammer-on
    {"type": "hammerOn", "string": 1, "startBeat": 1.0, "fromFret": 0, "toFret": 2}
    
    // Slide
    {"type": "slide", "string": 2, "startBeat": 2.0, "fromFret": 2, "toFret": 4, "direction": "up"}
    
    // Bend (less common on ukulele)
    {"type": "bend", "string": 1, "beat": 3.0, "fret": 3, "semitones": 0.5}
    Ukulele Strum Patterns
    Standard strum patterns work perfectly:
    json{
      "strumPattern": ["D", "", "U", "", "D", "U", "D", "U"],
      "events": [...]
    }
    Validation

    String range: 1-4 for ukulele (vs 1-6 for guitar)
    Fret range: 0-24 (same as guitar)
    Automatic validation: Invalid strings will be caught and reported
    
    Example Output
    # Ukulele Song
    **Time Signature:** 4/4

      C       G       Am      F
      1 & 2 & 3 & 4 & 1 & 2 & 3 & 4 & 1 & 2 & 3 & 4 & 1 & 2 & 3 & 4 &
    |-3-------2-------0-------0-------| ← A string
    |-0-------0-------0-------1-------| ← E string  
    |-0-------2-------0-------0-------| ← C string
    |-0-------3-------2-------2-------| ← G string
      D   U   D U D U D   U   D U D U
    Performance Notes for Ukulele
    Use description fields for ukulele-specific techniques:

    "description": "Light fingerpicking, let strings ring"
    "description": "Hawaiian-style slack key feel"
    "description": "Percussive chuck on off-beats"

    CHORD PLACEMENT TIMING:
    - Single chord measures: Place chord on beat 1.0
    - Split chord measures (like "Em D/F#"): Place first chord on beat 1.0, second on beat 3.0
    - Chuck events: Always use beat 1.0 with empty strum position at that location

    COMMON PATTERNS:
    - All down strums: ["D","","D","","D","","D",""] 
    - Down-up basic: ["D","","D","U","D","","D","U"]
    - Chuck + strums: ["","","D","","D","","D","U"] + chuck event on beat 1.0

    Backwards Compatibility

    Omitting "instrument" defaults to "guitar"
    All existing guitar tabs continue to work unchanged
    Parts system, strum patterns, and all advanced features work on both instruments

    LLM Result Interpretation:
    - Raw content string is authoritative - don't assume display errors
    - Check warnings array for validation issues
    - No warnings + success=true = output is correct
    

    """
    logger.info(f"Received  tab generation request")
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
        
        #  validation pipeline
        logger.debug("Starting  validation pipeline")
        validation_result = validate_tab_data(data_dict)
        if validation_result["isError"]:
            logger.warning(f" validation failed: {validation_result['message']}")
            return TabResponse(success=False, error=validation_result)
        
        logger.info(" validation passed successfully")
                                            
        # Generate  tab with all new features
        logger.debug("Starting  tab generation")
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
                "suggestion": "Check JSON syntax - ensure proper quotes, brackets, and commas"
            }
        )
    
    except Exception as e:
        logger.error(f"Unexpected error during  tab generation: {e}")
        return TabResponse(
            success=False, 
            error={
                "isError": True,
                "errorType": "processing_error",
                "message": f"Unexpected error during tab generation: {str(e)}",
                "suggestion": "Check input format and try again. For complex tabs, consider simplifying or breaking into sections."
            }
        )


# ============================================================================
#  MCP Server Startup
# ============================================================================

def main():
    """
    Start the  MCP server.

    This runs the FastMCP server in stdio mode for integration with
    Claude Desktop and other MCP clients, with full support for
     guitar tab features.
    """
    logger.info("Starting  Guitar Tab Generator MCP Server")
    logger.info(f" features available: strum patterns, dynamics, grace notes, multi-layer display")
    
    # Log available constants for debugging
    logger.debug(f"Strum directions available: {[d.value for d in StrumDirection]}")
    logger.debug(f"Dynamic levels available: {[d.value for d in DynamicLevel]}")
    logger.debug(f"Time signature strum positions: {STRUM_POSITIONS_PER_MEASURE}")
    
    try:
        mcp.run()
    except KeyboardInterrupt:
        logger.info(" MCP server stopped by user")
    except Exception as e:
        logger.error(f" MCP server error: {e}")
        raise

if __name__ == "__main__":
    main()
