#!/usr/bin/env python3
"""
Guitar Tab Generator - Core Implementation
==========================================

Core functionality for converting structured JSON guitar tab specifications
into properly aligned ASCII tablature. This module handles data validation,
tab generation, and error reporting optimized for LLM interaction.

Key Design Decisions:
- Compact notation for techniques (3h5, 12p10) to minimize character usage
- Structured error messages with measure/beat context for LLM correction
- Flexible template system that can accommodate multi-digit frets
- Attempt tracking to prevent infinite LLM regeneration loops
"""

import sys
import json
import logging
from typing import Dict, List, Any, Tuple, Optional
from pydantic import BaseModel, Field, validator
from time_signatures import (
    get_time_signature_config,
    is_beat_valid,
    calculate_char_position,
    generate_beat_markers,
    create_beat_validation_error,
    create_time_signature_error,
    get_supported_time_signatures,
    get_content_width,
    calculate_total_width
)

# Configure logging to stderr only (stdout reserved for MCP protocol)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# ============================================================================
# Data Models
# ============================================================================

class TabRequest(BaseModel):
    """
    Complete guitar tab specification for processing.
    
    The attempt field enables LLM regeneration tracking - if an LLM gets
    validation errors, it can increment this field and try again, but
    we limit attempts to prevent infinite loops.
    """
    title: str
    description: str = ""
    timeSignature: str = Field(default="4/4", pattern=r"^(4/4|3/4|6/8|2/4)$")
    tempo: int = Field(default=120, ge=40, le=300)
    attempt: int = Field(default=1, ge=1, le=10)
    measures: List[Dict[str, Any]]

class TabResponse(BaseModel):
    """
    Response container for both successful tab generation and error reporting.
    
    Warnings are non-fatal issues (like multi-digit frets requiring more space)
    that the LLM should be aware of but don't prevent tab generation.
    """
    success: bool
    content: str = ""
    error: Optional[Dict[str, Any]] = None
    warnings: List[Dict[str, Any]] = []

# ============================================================================
# Validation Pipeline
# ============================================================================

def validate_tab_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Multi-stage validation pipeline for guitar tab data.
    
    This uses a fail-fast approach - we stop at the first error type
    to avoid overwhelming the LLM with multiple error categories.
    The staged approach also helps LLMs understand which aspect
    of their JSON needs fixing.
    
    Args:
        data: Raw tab specification dictionary
        
    Returns:
        Error dictionary if validation fails, or {"isError": False} if valid
    """
    logger.debug(f"Starting validation for attempt {data.get('attempt', 1)}")
    
    # Stage 1: Schema and structure validation
    schema_result = validate_schema(data)
    if schema_result["isError"]:
        logger.warning(f"Schema validation failed: {schema_result['message']}")
        return schema_result
    
    # Stage 2: Time signature and beat timing validation  
    timing_result = validate_timing(data)
    if timing_result["isError"]:
        logger.warning(f"Timing validation failed: {timing_result['message']}")
        return timing_result
    
    # Stage 3: Event conflict detection and technique validation
    conflict_result = validate_conflicts(data)
    if conflict_result["isError"]:
        logger.warning(f"Conflict validation failed: {conflict_result['message']}")
        return conflict_result
    
    logger.info("All validation stages passed")
    return {"isError": False}

def validate_schema(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate required fields, data types, and basic structure.
    
    We check the most critical fields first (title, measures) since
    these are most likely to be missing in malformed LLM output.
    """
    required_fields = ["title", "timeSignature", "measures"]
    
    for field in required_fields:
        if field not in data:
            return {
                "isError": True,
                "errorType": "validation_error",
                "message": f"Missing required field: {field}",
                "suggestion": f"Add '{field}' property to root object"
            }
    
    # Validate measures array structure
    if not isinstance(data["measures"], list) or len(data["measures"]) == 0:
        return {
            "isError": True,
            "errorType": "validation_error", 
            "message": "Measures array is empty or invalid",
            "suggestion": "Provide at least one measure with events array"
        }
    
    # Validate each measure has events array
    for measure_idx, measure in enumerate(data["measures"], 1):
        if not isinstance(measure, dict) or "events" not in measure:
            return {
                "isError": True,
                "errorType": "validation_error",
                "measure": measure_idx,
                "message": f"Measure {measure_idx} missing events array",
                "suggestion": "Each measure must have an 'events' array (can be empty)"
            }
        
        if not isinstance(measure["events"], list):
            return {
                "isError": True,
                "errorType": "validation_error",
                "measure": measure_idx,
                "message": f"Measure {measure_idx} events is not an array",
                "suggestion": "Events must be an array of event objects"
            }
    
    return {"isError": False}

def validate_timing(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhanced timing validation using time signature module.
    """
    time_sig = data.get("timeSignature", "4/4")
    
    # Check if time signature is supported
    try:
        get_time_signature_config(time_sig)
    except ValueError:
        return create_time_signature_error(time_sig)
    
    # Check every event's beat timing
    for measure_idx, measure in enumerate(data["measures"], 1):
        for event_idx, event in enumerate(measure.get("events", []), 1):
            beat = event.get("beat") or event.get("startBeat")
            
            if beat is None:
                return {
                    "isError": True,
                    "errorType": "validation_error",
                    "measure": measure_idx,
                    "message": f"Event {event_idx} missing beat timing",
                    "suggestion": "Add 'beat' or 'startBeat' field to event"
                }
            
            if not is_beat_valid(beat, time_sig):
                return create_beat_validation_error(beat, time_sig, measure_idx)
    
    return {"isError": False}

def validate_conflicts(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check for conflicting events and validate technique-specific rules.
    
    This catches the subtle errors that make tabs unplayable:
    - Multiple notes on same string at same time
    - Invalid technique parameters (hammer-on going down, etc.)
    - String/fret range violations
    
    For chord events, we allow multiple strings at the same beat since
    that's the whole point of chords.
    """
    for measure_idx, measure in enumerate(data["measures"], 1):
        events_by_position = {}
        
        for event in measure.get("events", []):
            event_type = event.get("type")
            
            # Validate event has required type field
            if not event_type:
                return {
                    "isError": True,
                    "errorType": "validation_error",
                    "measure": measure_idx,
                    "message": "Event missing 'type' field",
                    "suggestion": "Add 'type' field with value like 'note', 'hammerOn', 'chord', etc."
                }
            
            # Handle chord events specially - they can have multiple strings at same beat
            if event_type == "chord":
                beat = event.get("beat")
                if not beat:
                    return {
                        "isError": True,
                        "errorType": "validation_error",
                        "measure": measure_idx,
                        "message": "Chord event missing 'beat' field",
                        "suggestion": "Add 'beat' field to chord event"
                    }
                
                # Validate chord has frets array
                frets = event.get("frets", [])
                if not frets:
                    return {
                        "isError": True,
                        "errorType": "validation_error",
                        "measure": measure_idx,
                        "beat": beat,
                        "message": "Chord event missing 'frets' array",
                        "suggestion": "Add 'frets' array with string/fret objects"
                    }
                
                # Check for duplicate strings within the chord
                chord_strings = set()
                for fret_info in frets:
                    string_num = fret_info.get("string")
                    if string_num in chord_strings:
                        return {
                            "isError": True,
                            "errorType": "conflict_error",
                            "measure": measure_idx,
                            "beat": beat,
                            "message": f"Chord has duplicate entries for string {string_num}",
                            "suggestion": "Each string can only appear once per chord"
                        }
                    chord_strings.add(string_num)
                
                continue  # Skip position conflict checking for chords
            
            # For non-chord events, check string/beat conflicts
            string_num = event.get("string")
            beat = event.get("beat") or event.get("startBeat")
            
            if not string_num or not beat:
                continue  # These will be caught by other validation
                
            position_key = f"{string_num}_{beat}"
            
            if position_key in events_by_position:
                return {
                    "isError": True,
                    "errorType": "conflict_error",
                    "measure": measure_idx,
                    "beat": beat,
                    "message": f"Multiple events on string {string_num} at beat {beat}",
                    "suggestion": "Move one event to different beat or different string"
                }
            
            events_by_position[position_key] = event
            
            # Validate technique-specific rules
            technique_error = validate_technique_rules(event, measure_idx, beat)
            if technique_error["isError"]:
                return technique_error
    
    return {"isError": False}

def validate_technique_rules(event: Dict[str, Any], measure_idx: int, beat: float) -> Dict[str, Any]:
    """
    Validate technique-specific rules that ensure playability and proper notation.
    
    Each guitar technique has physical constraints and notation rules:
    - Hammer-ons must go to higher fret (you can't hammer down)
    - Pull-offs must go to lower fret  
    - String numbers must be 1-6 (1=high e, 6=low E)
    - Fret numbers must be 0-24 or "x" for muted strings
    - Bend semitones must be 0.5-3.0 (quarter-step to step-and-a-half)
    - Palm mute duration must be positive and reasonable (0.5-8.0 beats)
    - Chuck events only need string and beat (no fret required)
    
    Special fret values:
    - "x" or "X" = muted/dead string (produces no pitch)
    - 0 = open string (no finger pressure needed)
    - 1-24 = fretted notes (standard guitar range)
    
    Annotation events:
    - palmMute: Requires beat and duration, no string/fret
    - chuck: Requires only beat, no string/fret (affects all strings)
    """
    event_type = event.get("type")
    
    # Validate string range for all events with string field
    string_num = event.get("string")
    if string_num is not None and (string_num < 1 or string_num > 6):
        return {
            "isError": True,
            "errorType": "validation_error",
            "measure": measure_idx,
            "beat": beat,
            "message": f"Invalid string number: {string_num}",
            "suggestion": "String numbers must be 1-6 (1=high e, 6=low E)"
        }
    
    # Validate fret ranges (now supports "x" for muted strings)
    for fret_field in ["fret", "fromFret", "toFret"]:
        fret = event.get(fret_field)
        if fret is not None:
            # Allow "x" or "X" for muted strings
            if isinstance(fret, str) and fret.lower() == "x":
                continue  # Valid muted string
            elif isinstance(fret, (int, float)) and (fret < 0 or fret > 24):
                return {
                    "isError": True,
                    "errorType": "validation_error",
                    "measure": measure_idx,
                    "beat": beat,
                    "message": f"Invalid fret number: {fret}",
                    "suggestion": "Fret numbers must be 0-24 or 'x' for muted strings"
                }
            elif not isinstance(fret, (int, float, str)):
                return {
                    "isError": True,
                    "errorType": "validation_error",
                    "measure": measure_idx,
                    "beat": beat,
                    "message": f"Invalid fret value: {fret}",
                    "suggestion": "Fret must be a number (0-24) or 'x' for muted strings"
                }
             
    # Technique-specific validations
    if event_type == "hammerOn":
        from_fret = event.get("fromFret")
        to_fret = event.get("toFret")
        if from_fret is not None and to_fret is not None and from_fret >= to_fret:
            return {
                "isError": True,
                "errorType": "validation_error",
                "measure": measure_idx,
                "beat": beat,
                "message": f"Hammer-on fromFret ({from_fret}) must be lower than toFret ({to_fret})",
                "suggestion": "Hammer-ons go to higher frets - check fromFret and toFret values"
            }
    
    elif event_type == "pullOff":
        from_fret = event.get("fromFret")
        to_fret = event.get("toFret")
        if from_fret is not None and to_fret is not None and from_fret <= to_fret:
            return {
                "isError": True,
                "errorType": "validation_error",
                "measure": measure_idx,
                "beat": beat,
                "message": f"Pull-off fromFret ({from_fret}) must be higher than toFret ({to_fret})",
                "suggestion": "Pull-offs go to lower frets - check fromFret and toFret values"
            }
    # Add bend-specific validation
    elif event_type == "bend":
        semitones = event.get("semitones")
        if semitones is not None:
            if not isinstance(semitones, (int, float)) or semitones <= 0 or semitones > 3.0:
                return {
                    "isError": True,
                    "errorType": "validation_error",
                    "measure": measure_idx,
                    "beat": beat,
                    "message": f"Invalid semitones value: {semitones}",
                    "suggestion": "Semitone must be a number between 0.25 and 3.0 (¼=quarter step, ½=half step, 1=whole step, 1½=step and half)" 
                }
        
    return {"isError": False}

# ============================================================================
# Tab Generation Engine
# ============================================================================

def generate_tab_output(data: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Generate formatted ASCII tablature from validated data.
    
    Returns both the tab string and any warnings about formatting issues.
    The warning system lets LLMs know about potential display problems
    without failing the entire generation.
    
    Key design choice: We process measures in groups of 4 for readability.
    This is a standard convention in printed music and keeps line lengths
    manageable for both human reading and LLM processing.
    """
    logger.info(f"Generating tab for '{data.get('title', 'Untitled')}'")
    
    measures = data["measures"]
    warnings = []
    output_lines = []
    
    # Generate header information
    title = data.get("title", "Untitled")
    description = data.get("description", "")
    time_sig = data.get("timeSignature", "4/4")
    tempo = data.get("tempo")
    
    output_lines.append(f"# {title}")
    if description:
        output_lines.append(f"*{description}*")
    
    # Add tempo/time signature info
    info_line = f"**Time Signature:** {time_sig}"
    if tempo:
        info_line += f" | **Tempo:** {tempo} BPM"
    output_lines.append(info_line)
    output_lines.append("")
    
    # Process measures in groups of 4 for formatting
    for measure_group_start in range(0, len(measures), 4):
        measure_group = measures[measure_group_start:measure_group_start + 4]
        tab_section, section_warnings = generate_measure_group(measure_group, measure_group_start, time_sig)
        warnings.extend(section_warnings)
        output_lines.extend(tab_section)
        output_lines.append("")  # Space between groups
    
    logger.info(f"Generated tab with {len(warnings)} warnings")
    return "\n".join(output_lines), warnings

# ============================================================================
# Annotation System Functions
# ============================================================================

def process_annotations(measures: List[Dict[str, Any]], num_measures: int, time_signature: str = "4/4") -> Tuple[str, str]:
    """
    Process chord names and annotations (palm mutes, chucks) for display above tab.
    
    This function creates two annotation lines that appear above the beat markers:
    1. Chord line: Shows chord names (e.g., "G", "Em", "C") above chord events
    2. Annotation line: Shows palm mutes (PM---), chucks (X), and other techniques
    
    The positioning system ensures annotations align exactly with their corresponding
    musical events using the same character position calculations as the tab content.
    
    Args:
        measures: List of measure objects containing events
        num_measures: Number of measures to process (typically 1-4 per group)
        
    Returns:
        Tuple of (chord_line, annotation_line) - two formatted strings ready for display
        
    Example output:
        annotation_line: " PM------------ X    PM---"
        chord_line:      " G              Em        "
    """
    # Calculate total character width (18 chars per measure + leading space)
    total_width = 1 + (num_measures * 18)
    
    # Initialize annotation arrays
    chord_chars = [' '] * total_width
    annotation_chars = [' '] * total_width
    
    # Process each measure
    for measure_idx, measure in enumerate(measures):
        for event in measure.get("events", []):
            event_type = event.get("type")
            beat = event.get("beat") or event.get("startBeat")
            
            if beat is None:
                continue
                
            char_position = calculate_char_position(beat, measure_idx, time_signature)
            
            # Process chord names
            if event_type == "chord" and "chordName" in event:
                chord_name = event["chordName"]
                place_annotation_text(chord_chars, char_position, chord_name, total_width)
            
            # Process palm mutes
            elif event_type == "palmMute":
                duration = event.get("duration", 1.0)
                pm_text = generate_palm_mute_notation(duration)
                place_annotation_text(annotation_chars, char_position, pm_text, total_width)
            
            # Process chucks
            elif event_type == "chuck":
                place_annotation_text(annotation_chars, char_position, "X", total_width)
    
    # Convert character arrays to strings with labels
    chord_line = "".join(chord_chars).rstrip()
    annotation_line = "".join(annotation_chars).rstrip()
    
    return chord_line, annotation_line

def place_annotation_text(char_array: List[str], position: int, text: str, max_width: int):
    """
    Place annotation text at specified position, avoiding overwrites.
    
    This is a utility function for positioning text within the annotation lines.
    It ensures that:
    - Text doesn't extend beyond the line boundaries
    - Existing text isn't overwritten (first-come, first-served basis)
    - Annotations align with their corresponding musical events
    
    Args:
        char_array: Mutable list of characters representing the annotation line
        position: Starting character position (calculated using calculate_char_position)
        text: Text to place (e.g., "G", "PM---", "X")
        max_width: Maximum line width to prevent array bounds errors
        
    Side Effects:
        Modifies char_array in place by setting characters at specified positions
    """
    for i, char in enumerate(text):
        target_pos = position + i
        if target_pos < max_width and target_pos >= 0:
            # Only place if the position is empty (space) to avoid overwrites
            if char_array[target_pos] == ' ':
                char_array[target_pos] = char

def generate_palm_mute_notation(duration: float) -> str:
    """
    Generate palm mute notation with appropriate number of dashes.
    
    Palm mutes are displayed as "PM" followed by dashes that indicate the
    duration of the muting effect. This provides visual feedback about
    how long to maintain the palm mute technique.
    
    The dash calculation uses approximately 2 characters per beat to provide
    reasonable visual representation within the ASCII tab format constraints.
    
    Args:
        duration: Duration in beats (e.g., 2.0 = 2 beats, 1.5 = beat and a half)
        
    Returns:
        String like "PM-" (short), "PM----" (medium), or "PM---------" (long)
        
    Examples:
        duration=0.5 ? "PM-"
        duration=1.0 ? "PM--" 
        duration=2.0 ? "PM----"
        duration=3.5 ? "PM-------"
    """
    # Calculate number of dashes based on duration
    # Each beat gets approximately 2 characters worth of dashes
    num_dashes = max(1, int(duration * 2))
    return "PM" + "-" * num_dashes


def generate_measure_group(measures: List[Dict[str, Any]], start_index: int, time_signature: str = "4/4") -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Generate tab section for up to 4 measures with enhanced annotation support.
    
    This is the core tab generation function that orchestrates the creation of
    a complete tab section including chord names, technique annotations, beat
    markers, and the actual tablature lines.
    
    The function now supports a three-tier display system:
    1. Chord names (when provided in chord events)
    2. Technique annotations (palm mutes, chucks, etc.)
    3. Standard tab content (beat markers + 6 string lines)
    
    Key enhancements over the basic version:
    - Processes annotation events (palmMute, chuck) for display above tab
    - Extracts chord names from chord events for chord line display
    - Only shows annotation lines when they contain actual content
    - Maintains backward compatibility with existing tab generation
    
    Args:
        measures: List of measure dictionaries containing events
        start_index: Starting measure number for this group (used in warnings)
        
    Returns:
        Tuple of (output_lines, warnings):
        - output_lines: List of strings forming the complete tab section
        - warnings: List of formatting warnings for complex notations
        
    Example output structure:
        [" PM------------ X    PM---",
         " G              Em        ",
         " 1 & 2 & 3 & 4 &   1 & 2 & 3 & 4 &",
         "|-3---x---0-------|0---x---0---3---|",
         ... (remaining 5 string lines)
        ]
    """
    warnings = []
    num_measures = len(measures)
    
    # Process annotations (chord names, palm mutes, chucks)
    chord_line, annotation_line = process_annotations(measures, num_measures, time_signature)
    
    # Generate beat markers using time signature module  
    beat_line = generate_beat_markers(time_signature, num_measures)
    beat_line = " " + beat_line
    
    # Initialize string lines with template dashes
    string_lines = []
    content_width = get_content_width(time_signature)
    for string_idx in range(6):
        line = "|"
        for measure_idx in range(num_measures):
            line += "-" * content_width + "|"
        string_lines.append(line)
    
    # Place events on appropriate string lines
    for measure_idx, measure in enumerate(measures):
        measure_warnings = place_measure_events(measure, string_lines, measure_idx, start_index + measure_idx + 1, time_signature)
        warnings.extend(measure_warnings)
    
    # Combine all lines: annotations + beat markers + string lines
    result = []
    
    # Only add annotation lines if they contain non-space content beyond the label
    chord_content = chord_line.strip()
    annotation_content = annotation_line.strip()
    
    if chord_content:
        result.append(chord_line)
    if annotation_content:
        result.append(annotation_line)
    
    result.append(beat_line)
    result.extend(string_lines)
    
    return result, warnings


def place_measure_events(measure: Dict[str, Any], string_lines: List[str], measure_offset: int, measure_number: int, time_signature: str = "4/4") -> List[Dict[str, Any]]:
    """
    Place all events from one measure onto the tab lines.
    
    Enhanced version that properly handles the separation between musical events
    (which appear on the string lines) and annotation events (which appear above
    the tab in the chord/annotation lines).
    
    This function now filters out annotation-only events (palmMute, chuck) and
    delegates their processing to the annotation system, preventing them from
    being incorrectly placed on string lines.
    
    The separation ensures clean code organization and proper visual layout:
    - Musical events ? String lines (handled here)
    - Annotation events ? Annotation lines (handled by process_annotations)
    
    This function handles the complex logic of converting abstract musical
    events into precise character positions in the ASCII tab. Each event type
    has different placement rules and character requirements.
    
    Args:
        measure: Single measure dictionary containing events list
        string_lines: Mutable list of 6 strings representing guitar tab lines
        measure_offset: Position of this measure within the current group (0-3)
        measure_number: Absolute measure number for error reporting (1-based)
        
    Returns:
        List of warning dictionaries for formatting issues (multi-digit frets, etc.)
        
    Side Effects:
        Modifies string_lines in place by placing event notation at calculated positions
    """
    warnings = []
    
    for event in measure.get("events", []):
        # Skip annotation events - they're handled separately
        if event.get("type") in ["palmMute", "chuck"]:
            continue
            
        event_warnings = place_event_on_tab(event, string_lines, measure_offset, measure_number, time_signature)
        warnings.extend(event_warnings)
    
    return warnings


def format_semitone_string(semitones: float) -> str:
    """
    Convert semitone float to clean notation using Unicode fractions.
    
    This function creates more compact and visually appealing bend notation
    by using Unicode fraction symbols instead of decimal representations.
    This matches traditional guitar tablature conventions where fractions
    are commonly used for bend amounts.
    
    Args:
        semitones: Numeric semitone value (0.5, 1.0, 1.5, 2.0, etc.)
        
    Returns:
        String representation using Unicode fractions where appropriate
        
    Examples:
        0.25 ? "¼"
        0.5  ? "½" 
        0.75 ? "¾"
        1.0  ? "1"
        1.5  ? "1½"
        2.0  ? "2"
        2.5  ? "2½"
        1.33 ? "1.33" (fallback for non-standard values)
    """
    # Handle common fraction cases with Unicode symbols
    if semitones == 0.25:
        return "¼"
    elif semitones == 0.5:
        return "½"
    elif semitones == 0.75:
        return "¾"
    elif semitones == 1.25:
        return "1¼"
    elif semitones == 1.5:
        return "1½"
    elif semitones == 1.75:
        return "1¾"
    elif semitones == 2.25:
        return "2¼"
    elif semitones == 2.5:
        return "2½"
    elif semitones == 2.75:
        return "2¾"
    elif semitones == 3.0:
        return "3"
    # Handle whole numbers (remove .0)
    elif semitones == int(semitones):
        return str(int(semitones))
    # Fallback for unusual decimal values
    else:
        return str(semitones)

def place_event_on_tab(event: Dict[str, Any], string_lines: List[str], measure_offset: int, measure_number: int, time_signature: str = "4/4") -> List[Dict[str, Any]]:
    """
    Place individual event on the appropriate tab line.
    
    This is the core algorithm that converts musical events to ASCII characters.
    Key challenges:
    - Multi-digit frets require multiple character positions
    - Techniques like "10h12" can be 5+ characters long
    - Must maintain precise beat alignment despite variable-width content
    - Need to detect when content won't fit in standard template
    """
    warnings = []
    event_type = event.get("type")
    
    if event_type == "note":
        string_num = event["string"]
        beat = event["beat"]
        fret = event["fret"]
        vibrato = event.get("vibrato", False)

        char_position = calculate_char_position(beat, measure_offset, time_signature)
        line_index = string_num - 1  # Convert 1-indexed to 0-indexed

        # Handle muted strings and vibrato
        if isinstance(fret, str) and fret.lower() == "x":
            fret_str = "x"
        else:
            fret_str = str(fret)
            if vibrato:
                fret_str += "~"
 
        print(f"DEBUG: Placing fret {fret} at position {char_position} on string {string_num}", file=sys.stderr) 
        string_lines[line_index] = replace_chars_at_position(string_lines[line_index], char_position, fret_str)
        print(f"DEBUG: Line after: {string_lines[line_index]}", file=sys.stderr)
        
        # Warn about multi-digit frets or vibrato that may cause alignment issues
        if len(fret_str) > 1:
            warnings.append({
                "warningType": "formatting_warning",
                "measure": measure_number,
                "beat": beat,
                "message": f"Multi-digit fret ({fret_str}) may affect template alignment",
                "suggestion": f"Fret {fret_str} uses {len(fret_str)} character positions"
            })
    
    elif event_type == "chord":
        beat = event["beat"]
        char_position = calculate_char_position(beat, measure_offset, time_signature)
        
        max_fret_width = 0
        for fret_info in event["frets"]:
            string_num = fret_info["string"] 
            fret = str(fret_info["fret"])
            line_index = string_num - 1
            
            string_lines[line_index] = replace_chars_at_position(string_lines[line_index], char_position, fret)
            max_fret_width = max(max_fret_width, len(fret))
        
        # Warn about chords with wide fret numbers
        if max_fret_width > 1:
            warnings.append({
                "warningType": "formatting_warning", 
                "measure": measure_number,
                "beat": beat,
                "message": f"Chord with multi-digit frets may affect alignment",
                "suggestion": f"Chord requires {max_fret_width} character positions"
            })
    
    elif event_type in ["hammerOn", "pullOff"]:
        string_num = event["string"]
        beat = event["startBeat"]
        from_fret = str(event["fromFret"])
        to_fret = str(event["toFret"])
        symbol = "h" if event_type == "hammerOn" else "p"
        vibrato = event.get("vibrato", False)

        char_position = calculate_char_position(beat, measure_offset, time_signature)
        line_index = string_num - 1
        
        # Compact format: "3h5" or "10p12"
        technique_str = f"{from_fret}{symbol}{to_fret}"

        # Add vibrato notation if specified (applies to the destination note)
        if vibrato:
            technique_str += "~"

        string_lines[line_index] = replace_chars_at_position(string_lines[line_index], char_position, technique_str)
        
        # Warn about wide technique notations
        if len(technique_str) > 3:
            warnings.append({
                "warningType": "formatting_warning",
                "measure": measure_number,
                "beat": beat,
                "message": f"Technique notation '{technique_str}' may require template adjustment",
                "suggestion": f"Technique uses {len(technique_str)} character positions"
            })
    
    elif event_type == "slide":
        string_num = event["string"]
        beat = event["startBeat"]
        from_fret = str(event["fromFret"])
        to_fret = str(event["toFret"])
        symbol = "/" if event["direction"] == "up" else "\\"
        vibrato = event.get("vibrato", False)

        char_position = calculate_char_position(beat, measure_offset, time_signature)
        line_index = string_num - 1
        
        # Compact format: "3/5" or "12\8"  
        technique_str = f"{from_fret}{symbol}{to_fret}"
            
        # Add vibrato notation if specified (applies to the destination note)
        if vibrato:
            technique_str += "~"

        string_lines[line_index] = replace_chars_at_position(string_lines[line_index], char_position, technique_str)
        
        if len(technique_str) > 3:
            warnings.append({
                "warningType": "formatting_warning",
                "measure": measure_number,
                "beat": beat,
                "message": f"Slide notation '{technique_str}' may require template adjustment",
                "suggestion": f"Slide uses {len(technique_str)} character positions"
            })

    elif event_type == "bend":
        string_num = event["string"]
        beat = event["beat"]
        fret = event["fret"]
        semitones = event.get("semitones", 1.0)
        vibrato = event.get("vibrato", False)
    
        char_position = calculate_char_position(beat, measure_offset, time_signature)
        line_index = string_num - 1
    
        # Handle muted strings in bends (unusual but possible)
        if isinstance(fret, str) and fret.lower() == "x":
            fret_str = "x"
        else:
            fret_str = str(fret)
    
        # Generate enhanced notation with Unicode fraction semitone amounts
        semitone_str = format_semitone_string(semitones)
        technique_str = f"{fret_str}b{semitone_str}"

        # Add vibrato notation if specified
        if vibrato:
            technique_str += "~"
    
        string_lines[line_index] = replace_chars_at_position(string_lines[line_index], char_position, technique_str)
    
        # Add warning for wide bend notations
        if len(technique_str) > 2:
            warnings.append({
                "warningType": "formatting_warning",
                "measure": measure_number,
                "beat": beat,
                "message": f"Bend notation '{technique_str}' may require template adjustment",
                "suggestion": f"Bend notation uses {len(technique_str)} character positions"
                }) 
    return warnings


def replace_chars_at_position(line: str, position: int, replacement: str) -> str:
    """
    Replace characters in string at specific position, maintaining string length.
    
    This is a critical utility that must preserve the exact character alignment
    of the tab template. We convert to list for efficient character replacement,
    then back to string.
    
    Edge case handling: If replacement is longer than remaining space,
    we truncate rather than extending the line (which would break alignment).
    """
    line_list = list(line)
    
    for i, char in enumerate(replacement):
        target_pos = position + i
        if target_pos < len(line_list):
            line_list[target_pos] = char
        else:
            # Character position beyond line length - this shouldn't happen
            # with proper template sizing, but we handle it gracefully
            logger.warning(f"Character position {target_pos} beyond line length {len(line_list)}")
            break
    
    return "".join(line_list)

# ============================================================================
# Error Handling Utilities
# ============================================================================

def check_attempt_limit(attempt: int) -> Optional[Dict[str, Any]]:
    """
    Check if LLM has exceeded regeneration attempt limit.
    
    This prevents infinite loops when an LLM repeatedly generates
    invalid JSON. After 5 attempts, we assume there's a fundamental
    misunderstanding and provide guidance to start over.
    """
    MAX_ATTEMPTS = 5
    
    if attempt > MAX_ATTEMPTS:
        return {
            "isError": True,
            "errorType": "attempt_limit_error",
            "attempt": attempt,
            "message": f"Maximum regeneration attempts reached ({attempt})",
            "suggestion": "Review input data structure or simplify the tab requirements. Consider starting with a basic single-measure example."
        }
    
    return None
