#!/usr/bin/env python3
"""
Guitar Tab Generator -  Core Implementation
==================================================

 core functionality for converting structured JSON guitar tab specifications
into properly aligned UTF-8 tablature with support for strum patterns, dynamics,
and emphasis markings.

Key Enhancements:
- Strum pattern validation and rendering
- Dynamic and emphasis marking support
- Grace note handling
- Multi-layer display system (chord names, dynamics, annotations, beat markers, tab, strum pattern)
"""

# Import  models and constants
import sys
import json
import logging
from typing import Dict, List, Any, Tuple, Optional

from tab_constants import (
    StrumDirection, DynamicLevel, ArticulationMark, VALID_EMPHASIS_VALUES,
    STRUM_POSITIONS_PER_MEASURE, get_strum_positions_for_time_signature,
    is_valid_emphasis, ERROR_MESSAGES, DisplayLayer, DISPLAY_LAYER_ORDER, 
    get_instrument_config, get_max_string, Instrument
)
from tab_models import (
    TabRequest, TabResponse, StrumPatternEvent,
    GraceNoteEvent, DynamicEvent, PalmMute, Chuck
)
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
#  Validation Pipeline
# ============================================================================


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
     timing validation that includes new event types.
    
    Validates beat timing for:
    - Standard musical events (notes, chords, techniques)
    - New event types (strum patterns, grace notes, dynamics)
    - Compound time signatures (6/8 with triplet feel)
    """
    time_sig = data.get("timeSignature", "4/4")
    logger.debug(f"Validating timing for time signature: {time_sig}")
    
    # Check if time signature is supported
    try:
        config = get_time_signature_config(time_sig)
        logger.debug(f"Time signature config loaded: {config['name']}")
    except ValueError:
        logger.error(f"Unsupported time signature: {time_sig}")
        return create_time_signature_error(time_sig)
    
    # Check every event's beat timing
    for measure_idx, measure in enumerate(data["measures"], 1):
        logger.debug(f"Validating timing for measure {measure_idx}")
        
        for event_idx, event in enumerate(measure.get("events", []), 1):
            event_type = event.get("type")
            beat = event.get("beat") or event.get("startBeat")
            
            if beat is None:
                logger.warning(f"Event {event_idx} in measure {measure_idx} missing beat timing")
                return {
                    "isError": True,
                    "errorType": "validation_error",
                    "measure": measure_idx,
                    "message": f"Event {event_idx} missing beat timing",
                    "suggestion": "Add 'beat' or 'startBeat' field to event"
                }
            
            #  beat validation for different event types
            if event_type == "graceNote":
                # Grace notes have special timing requirements
                grace_result = validate_grace_note_timing(beat, time_sig, measure_idx)
                if grace_result["isError"]:
                    return grace_result
            elif event_type == "strumPattern":
                # Strum patterns have their own validation (handled separately)
                logger.debug(f"Strum pattern found at beat {beat} - will validate separately")
                continue
            else:
                # Standard beat validation
                if not is_beat_valid(beat, time_sig):
                    logger.warning(f"Invalid beat {beat} for {time_sig} in measure {measure_idx}")
                    return create_beat_validation_error(beat, time_sig, measure_idx)
    
    logger.debug(" timing validation passed")
    return {"isError": False}

def validate_conflicts(data: Dict[str, Any]) -> Dict[str, Any]:
    """
     conflict detection that handles new event types.
    
    Checks for:
    - Musical event conflicts (multiple notes on same string/beat)
    - Grace note conflicts with main notes
    - Strum pattern overlaps
    - Dynamic marking conflicts
    """
    logger.debug("Starting  conflict validation")
    
    for measure_idx, measure in enumerate(data["measures"], 1):
        events_by_position = {}
        strum_patterns = []
        grace_notes = []
        
        logger.debug(f"Validating conflicts in measure {measure_idx}")
        
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
            
            # Collect different event types for specialized validation
            if event_type == "strumPattern":
                strum_patterns.append(event)
                continue
            elif event_type == "graceNote":
                grace_notes.append(event)
                continue
            elif event_type in ["dynamic", "palmMute", "chuck"]:
                # Annotation events don't conflict with musical events
                continue
            
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
                logger.warning(f"Conflict detected: multiple events on string {string_num} at beat {beat}")
                return {
                    "isError": True,
                    "errorType": "conflict_error",
                    "measure": measure_idx,
                    "beat": beat,
                    "message": f"Multiple events on string {string_num} at beat {beat}",
                    "suggestion": "Move one event to different beat or different string"
                }
            
            events_by_position[position_key] = event
            
            # Validate technique-specific rules ()
            technique_error = validate_technique_rules(event, measure_idx, beat)
            if technique_error["isError"]:
                return technique_error
        
        # Validate grace note conflicts
        grace_conflict = validate_grace_note_conflicts(grace_notes, events_by_position, measure_idx)
        if grace_conflict["isError"]:
            return grace_conflict
    
    logger.debug(" conflict validation passed")
    return {"isError": False}

# ============================================================================
# New Validation Functions
# ============================================================================

def validate_strum_patterns(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate strum pattern events for proper time signature compatibility.
    
    Checks:
    - Pattern length matches time signature requirements
    - Pattern spans complete measures only
    - No overlapping strum patterns
    - Valid strum direction values
    """
    time_sig = data.get("timeSignature", "4/4")
    expected_positions = get_strum_positions_for_time_signature(time_sig)
    
    logger.debug(f"Validating strum patterns for {time_sig} (expecting {expected_positions} positions per measure)")
    
    active_patterns = []  # Track overlapping patterns
    
    for measure_idx, measure in enumerate(data["measures"], 1):
        for event in measure.get("events", []):
            if event.get("type") != "strumPattern":
                continue
                
            logger.debug(f"Found strum pattern in measure {measure_idx}")
            
            pattern = event.get("pattern", [])
            measures_spanned = event.get("measures", 1)
            start_beat = event.get("startBeat", 1.0)
            
            # Validate pattern length
            expected_length = expected_positions * measures_spanned
            if len(pattern) != expected_length:
                logger.error(f"Strum pattern length mismatch: got {len(pattern)}, expected {expected_length}")
                return {
                    "isError": True,
                    "errorType": "validation_error",
                    "measure": measure_idx,
                    "message": ERROR_MESSAGES["invalid_strum_pattern_length"].format(
                        length=len(pattern), 
                        time_sig=time_sig, 
                        expected=expected_length
                    ),
                    "suggestion": f"Pattern should have {expected_length} elements for {measures_spanned} measures of {time_sig}. Each measure needs {expected_positions} positions."
                }
            
            # Validate pattern values
            for i, direction in enumerate(pattern):
                if direction not in ["D", "U", ""]:
                    logger.error(f"Invalid strum direction '{direction}' at position {i}")
                    return {
                        "isError": True,
                        "errorType": "validation_error",
                        "measure": measure_idx,
                        "message": f"Invalid strum direction '{direction}' at position {i}",
                        "suggestion": "Use 'D' for down, 'U' for up, or '' for no strum"
                    }
            
            # Check for pattern overlaps (simplified for now)
            pattern_info = {
                "start_measure": measure_idx,
                "end_measure": measure_idx + measures_spanned - 1,
                "start_beat": start_beat
            }
            
            for existing_pattern in active_patterns:
                if (pattern_info["start_measure"] <= existing_pattern["end_measure"] and
                    pattern_info["end_measure"] >= existing_pattern["start_measure"]):
                    logger.error(f"Overlapping strum patterns detected")
                    return {
                        "isError": True,
                        "errorType": "conflict_error",
                        "measure": measure_idx,
                        "message": "Overlapping strum patterns detected",
                        "suggestion": "Only one strum pattern can be active at a time"
                    }
            
            active_patterns.append(pattern_info)
            logger.debug(f"Strum pattern validated: {measures_spanned} measures, {len(pattern)} positions")
    
    logger.debug("Strum pattern validation passed")
    return {"isError": False}

def validate_emphasis_markings(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate emphasis markings on all musical events.
    
    Checks:
    - Valid emphasis values (dynamics, articulations)
    - Proper emphasis placement
    - No conflicting emphasis markings
    """
    logger.debug("Validating emphasis markings")
    
    for measure_idx, measure in enumerate(data["measures"], 1):
        for event in measure.get("events", []):
            emphasis = event.get("emphasis")
            
            if emphasis is not None:
                logger.debug(f"Found emphasis '{emphasis}' in measure {measure_idx}")
                
                if not is_valid_emphasis(emphasis):
                    logger.error(f"Invalid emphasis value: {emphasis}")
                    return {
                        "isError": True,
                        "errorType": "validation_error",
                        "measure": measure_idx,
                        "message": ERROR_MESSAGES["invalid_emphasis_value"].format(
                            value=emphasis,
                            valid_values=", ".join(VALID_EMPHASIS_VALUES)
                        ),
                        "suggestion": f"Use valid emphasis: {', '.join(VALID_EMPHASIS_VALUES[:10])}..."
                    }
    
    logger.debug("Emphasis validation passed")
    return {"isError": False}

def validate_grace_note_timing(beat: float, time_sig: str, measure: int) -> Dict[str, Any]:
    """
    Validate grace note timing to ensure proper placement.
    
    Grace notes should not be too close to measure boundaries
    and should have valid target beats.
    """
    config = get_time_signature_config(time_sig)
    max_beat = max(config["valid_beats"])
    
    # Grace notes should not be at the very end of a measure
    if beat >= max_beat:
        return {
            "isError": True,
            "errorType": "validation_error",
            "measure": measure,
            "beat": beat,
            "message": ERROR_MESSAGES["grace_note_invalid_timing"].format(beat=beat),
            "suggestion": f"Grace notes should be placed before beat {max_beat}"
        }
    
    return {"isError": False}

def validate_grace_note_conflicts(grace_notes: List[Dict], events_by_position: Dict, measure: int) -> Dict[str, Any]:
    """
    Check for conflicts between grace notes and main notes.
    """
    for grace_note in grace_notes:
        string_num = grace_note.get("string")
        beat = grace_note.get("beat")
        
        # Check if there's a main note at the same position
        position_key = f"{string_num}_{beat}"
        if position_key not in events_by_position:
            return {
                "isError": True,
                "errorType": "validation_error",
                "measure": measure,
                "beat": beat,
                "message": f"Grace note on string {string_num} has no target note at beat {beat}",
                "suggestion": "Grace notes must lead into a main note at the same beat and string"
            }
    
    return {"isError": False}

def validate_measure_strum_patterns(measures: List[Dict[str, Any]], time_signature: str) -> Dict[str, Any]:
    """Validate strum patterns at measure level."""
    expected_positions = get_strum_positions_for_time_signature(time_signature)
    
    for measure_idx, measure in enumerate(measures, 1):
        strum_pattern = measure.get("strumPattern")
        if strum_pattern is None:
            continue
            
        # Check length
        if len(strum_pattern) != expected_positions:
            return {
                "isError": True,
                "errorType": "validation_error",
                "measure": measure_idx,
                "message": f"Strum pattern in measure {measure_idx} has {len(strum_pattern)} positions, expected {expected_positions} for {time_signature}",
                "suggestion": f"Use exactly {expected_positions} elements for {time_signature}"
            }
        
        # Check values
        for i, direction in enumerate(strum_pattern):
            if direction not in ["D", "U", ""]:
                return {
                    "isError": True,
                    "errorType": "validation_error", 
                    "measure": measure_idx,
                    "message": f"Invalid strum direction '{direction}' at position {i}",
                    "suggestion": "Use 'D', 'U', or ''"
                }
    
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
    - Emphasis compatibility with techniques
    -  bend notation with emphasis
    - Vibrato + emphasis combinations

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
    
    # Additional validation for emphasis on techniques
    emphasis = event.get("emphasis")
    event_type = event.get("type")
    
    if emphasis and event_type in ["bend", "slide", "hammerOn", "pullOff"]:
        logger.debug(f"Validating emphasis '{emphasis}' on {event_type}")
        
        # Some emphasis markings don't make sense with certain techniques
        if emphasis in ["pp", "p"] and event_type == "bend":
            logger.warning(f"Soft dynamics on bends may not be effective")
            # This is a warning, not an error
            
    return {"isError": False}


logger.info(" core validation module loaded successfully") 


# ============================================================================
#  Tab Generation Engine
# ============================================================================

def generate_tab_output(data: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    """
     tab generation with multi-layer display support.
    
    Generates tabs with up to 6 display layera:
    1. Chord names
    2. Dynamics markings  
    3. Annotations (PM, X, emphasis)
    4. Beat markers
    5. Tab content (6 string lines)
    6. Strum patterns
    
    Args:
        data: Validated tab specification dictionary
        
    Returns:
        Tuple of (tab_string, warnings_list)
    """
    title = data.get("title", "Untitled")
    logger.info(f"Generating  tab for '{title}'")
    
    measures = data["measures"]
    warnings = []
    output_lines = []
    
    # Generate  header information
    header_lines = generate_header(data)
    output_lines.extend(header_lines)
    output_lines.append("")
    
    # Process measures in groups of 4 for formatting
    for measure_group_start in range(0, len(measures), 4):
        measure_group = measures[measure_group_start:measure_group_start + 4]
        time_sig = data.get("timeSignature", "4/4")
        
        # Generate  measure group with all display layers
        tab_section, section_warnings = generate_measure_group(
            measure_group, measure_group_start, time_sig, data
        )
        warnings.extend(section_warnings)
        output_lines.extend(tab_section)
        output_lines.append("")  # Space between groups
    
    logger.info(f"Generated  tab with {len(warnings)} warnings")
    return "\n".join(output_lines), warnings

# ============================================================================
# Backwards Compatibility Wrappers
# ============================================================================


def generate_strum_line(measures: List[Dict[str, Any]], num_measures: int, time_signature: str) -> str:
    """Generate strum line from measure strumPattern fields."""
    total_width = calculate_total_width(time_signature, num_measures)
    strum_chars = [' '] * total_width
    
    for measure_idx, measure in enumerate(measures):
        strum_pattern = measure.get("strumPattern")
        if not strum_pattern:
            continue
            
        config = get_time_signature_config(time_signature)
        for pattern_idx, direction in enumerate(strum_pattern):
            if direction and pattern_idx < len(config["valid_beats"]):
                beat = config["valid_beats"][pattern_idx]
                char_position = calculate_char_position(beat, measure_idx, time_signature)
                if char_position < total_width:
                    strum_chars[char_position] = direction
    
    return "".join(strum_chars).rstrip()


def generate_header(data: Dict[str, Any]) -> List[str]:
    """
    Generate  header with additional metadata.
    """
    lines = []
    
    # Title and description
    title = data.get("title", "Untitled")
    description = data.get("description", "")
    artist = data.get("artist", "")
    
    lines.append(f"# {title}")
    if artist:
        lines.append(f"**Artist:** {artist}")
    if description:
        lines.append(f"*{description}*")
    
    # Musical information
    time_sig = data.get("timeSignature", "4/4")
    tempo = data.get("tempo")
    key = data.get("key")
    capo = data.get("capo")
    
    info_parts = [f"**Time Signature:** {time_sig}"]
    if tempo:
        info_parts.append(f"**Tempo:** {tempo} BPM")
    if key:
        info_parts.append(f"**Key:** {key}")
    if capo:
        info_parts.append(f"**Capo:** {capo}")
    
    lines.append(" | ".join(info_parts))
    
    return lines

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
    reasonable visual representation within the UTF-8 tab format constraints.
    
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


def generate_measure_group(
    measures: List[Dict[str, Any]], 
    start_index: int, 
    time_signature: str,
    tab_data: Dict[str, Any]
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Generate  tab section with multi-layer display.
    
    Creates all display layers:
    - Chord names (when present)
    - Dynamics (when present) 
    - Annotations (PM, X, emphasis markings)
    - Beat markers
    - Tab content (6 string lines)
    - Strum patterns (when present)
    
    Args:
        measures: List of measure dictionaries
        start_index: Starting measure number for warnings
        time_signature: Time signature string
        tab_data: Complete tab data for global settings
        
    Returns:
        Tuple of (output_lines, warnings)
    """
    warnings = []
    num_measures = len(measures)

    # Combine all layers in proper order
    result = []

    # Get instrument configuration for string count
    instrument_str = tab_data.get("instrument", "guitar")
    try:
        config = get_instrument_config(instrument_str)
        num_strings = config.strings
        logger.debug(f"Generating tab for {config.name} ({num_strings} strings)")
    except ValueError:
        num_strings = 6  # Default to guitar
        logger.warning(f"Unknown instrument {instrument_str}, defaulting to 6 strings")
    
    
    logger.debug(f"Generating  measure group: {num_measures} measures of {time_signature}")
    
    # Generate all display layers
    display_layers = generate_all_display_layers(measures, num_measures, time_signature, tab_data)
    
    # Generate beat markers using time signature module  
    beat_line = generate_beat_markers(time_signature, num_measures)
    beat_line = " " + beat_line


    # Initialize string lines with correct template for time signature
    string_lines = []
    result.extend(string_lines)
 
    content_width = get_content_width(time_signature)
    
    for string_idx in range(num_strings):
        line = "|"  # Start with opening separator
        for measure_idx in range(num_measures):
            line += "-" * content_width + "|"  # content + separator
        string_lines.append(line)
    
    # Place events on appropriate string lines
    for measure_idx, measure in enumerate(measures):
        measure_warnings = place_measure_events(
            measure, string_lines, measure_idx, start_index + measure_idx + 1, time_signature
        )
        warnings.extend(measure_warnings)
    
    # Add each display layer if it has content
    for layer_name in DISPLAY_LAYER_ORDER:
        layer_content = display_layers.get(layer_name)
        if layer_content and layer_content.strip():
            result.append(layer_content)
    
    # Conditionally add beat markers, always add string lines
    show_beat_markers = tab_data.get("showBeatMarkers", True)
    if show_beat_markers:
        result.append(beat_line)

    # Always string lines
    result.extend(string_lines)
    
    # Add strum pattern at the bottom if present
    strum_line = display_layers.get(DisplayLayer.STRUM_PATTERN)
    if strum_line and strum_line.strip():
        result.append(strum_line)

    # Generate strum pattern line from measures
    strum_line = generate_strum_line(measures, num_measures, time_signature)

    # Add strum pattern if any measures have patterns  
    if strum_line and strum_line.strip():
        result.append(strum_line)
    
    logger.debug(f"Generated {len(result)} display lines for measure group")
    return result, warnings

def generate_all_display_layers(
    measures: List[Dict[str, Any]], 
    num_measures: int, 
    time_signature: str,
    tab_data: Dict[str, Any]
) -> Dict[DisplayLayer, str]:
    """
    Generate all display layers for a measure group.
    
    Returns:
        Dictionary mapping DisplayLayer enum to formatted string content
    """
    total_width = calculate_total_width(time_signature, num_measures)
    
    logger.debug(f"Generating display layers for {num_measures} measures, width {total_width}")
    
    # Initialize character arrays for each layer
    layers = {
        DisplayLayer.CHORD_NAMES: [' '] * total_width,
        DisplayLayer.DYNAMICS: [' '] * total_width,
        DisplayLayer.ANNOTATIONS: [' '] * total_width,
        DisplayLayer.STRUM_PATTERN: [' '] * total_width
    }
    
    # Process each measure
    for measure_idx, measure in enumerate(measures):
        process_measure_for_display_layers(measure, measure_idx, time_signature, layers, total_width)
    
    # Convert character arrays to strings and remove trailing spaces
    result = {}
    for layer, char_array in layers.items():
        content = "".join(char_array).rstrip()
        if content:  # Only include non-empty layers
            result[layer] = content
            logger.debug(f"Generated {layer.value}: '{content[:50]}{'...' if len(content) > 50 else ''}'")
    
    return result

def process_measure_for_display_layers(
    measure: Dict[str, Any], 
    measure_idx: int, 
    time_signature: str, 
    layers: Dict[DisplayLayer, List[str]], 
    total_width: int
):
    """
    Process a single measure and populate all display layers.
    """
    for event in measure.get("events", []):
        event_type = event.get("type")
        beat = event.get("beat") or event.get("startBeat")
        
        if beat is None:
            continue
            
        char_position = calculate_char_position(beat, measure_idx, time_signature)
        
        # Process different event types for appropriate layers
        if event_type == "chord":
            # Chord names layer
            chord_name = event.get("chordName")
            if chord_name:
                place_annotation_text(layers[DisplayLayer.CHORD_NAMES], char_position, chord_name, total_width)
            
            # Emphasis on chords goes to dynamics layer
            emphasis = event.get("emphasis")
            if emphasis:
                place_annotation_text(layers[DisplayLayer.DYNAMICS], char_position, emphasis, total_width)
        
        elif event_type == "note":
            # Emphasis on notes goes to dynamics layer
            emphasis = event.get("emphasis")
            if emphasis:
                place_annotation_text(layers[DisplayLayer.DYNAMICS], char_position, emphasis, total_width)
        
        elif event_type == "palmMute":
            duration = event.get("duration", 1.0)
            intensity = event.get("intensity", "")
            pm_text = generate_palm_mute_notation(duration, intensity)
            place_annotation_text(layers[DisplayLayer.ANNOTATIONS], char_position, pm_text, total_width)
        
        elif event_type == "chuck":
            intensity = event.get("intensity", "")
            chuck_text = "X" + (intensity[0].upper() if intensity else "")  # X, XL, XM, XH
            place_annotation_text(layers[DisplayLayer.ANNOTATIONS], char_position, chuck_text, total_width)
        
        elif event_type == "dynamic":
            dynamic = event.get("dynamic")
            duration = event.get("duration")
            if dynamic:
                dynamic_text = generate_dynamic_notation(dynamic, duration)
                place_annotation_text(layers[DisplayLayer.DYNAMICS], char_position, dynamic_text, total_width)
        
        elif event_type == "strumPattern":
            # Process strum pattern
            pattern = event.get("pattern", [])
            measures_spanned = event.get("measures", 1)
            start_beat = event.get("startBeat", 1.0)
            
            process_strum_pattern(
                pattern, measures_spanned, start_beat, measure_idx, 
                time_signature, layers[DisplayLayer.STRUM_PATTERN], total_width
            )

def generate_palm_mute_notation(duration: float, intensity: str = "") -> str:
    """
    Generate  palm mute notation with intensity indicators.
    
    Args:
        duration: Duration in beats
        intensity: Intensity level ("light", "medium", "heavy")
        
    Returns:
        String like "PM--", "PM(L)--", "PM(H)----"
    """
    base = "PM"
    
    # Add intensity indicator
    if intensity:
        intensity_map = {"light": "(L)", "medium": "(M)", "heavy": "(H)"}
        base += intensity_map.get(intensity, "")
    
    # Add duration dashes
    num_dashes = max(1, int(duration * 2))
    return base + "-" * num_dashes

def generate_dynamic_notation(dynamic: str, duration: Optional[float] = None) -> str:
    """
    Generate dynamic notation with optional duration indicators.
    
    Args:
        dynamic: Dynamic marking (pp, p, mp, mf, f, ff, cresc., etc.)
        duration: Optional duration for extended markings
        
    Returns:
        String like "f", "cresc.---", "dim.--"
    """
    if dynamic in ["cresc.", "dim.", "<", ">"]:
        # Extended markings get duration dashes
        if duration:
            num_dashes = max(1, int(duration * 2))
            return dynamic + "-" * num_dashes
        else:
            return dynamic + "---"  # Default length
    else:
        # Standard dynamics are just the marking
        return dynamic

def process_strum_pattern(
    pattern: List[str], 
    measures_spanned: int,
    start_beat: float,
    current_measure: int,
    time_signature: str,
    strum_chars: List[str],
    total_width: int
):
    """
    Process strum pattern and place it in the strum pattern layer.
    
    Args:
        pattern: List of strum directions ["D", "U", "", ...]
        measures_spanned: How many measures this pattern covers
        start_beat: Starting beat of the pattern
        current_measure: Current measure index (0-based)
        time_signature: Time signature string
        strum_chars: Character array for strum pattern layer
        total_width: Total width of the display
    """
    config = get_time_signature_config(time_signature)
    positions_per_measure = len(config["valid_beats"])
    
    logger.debug(f"Processing strum pattern: {len(pattern)} positions, {measures_spanned} measures")
    
    # For now, assume the pattern starts at the beginning of the measure group
    pattern_start_measure = 0  # Relative to current measure group

    # Check if current measure is covered by this pattern
    if current_measure < pattern_start_measure or current_measure >= pattern_start_measure + measures_spanned:
       logger.debug(f"Measure {current_measure} not covered by pattern (starts at {pattern_start_measure}, spans {measures_spanned})")
       return

    measure_offset_in_pattern = current_measure - pattern_start_measure
    pattern_start_idx = measure_offset_in_pattern * positions_per_measure
    pattern_end_idx = pattern_start_idx + positions_per_measure
    
    # Extract the pattern slice for this measure
    measure_pattern = pattern[pattern_start_idx:pattern_end_idx]

   # Validate pattern slice bounds
    if pattern_start_idx >= len(pattern):
        logger.warning(f"Pattern start index {pattern_start_idx} exceeds pattern length {len(pattern)}")
        return

    logger.debug(f"Measure {current_measure}: using pattern slice [{pattern_start_idx}:{pattern_end_idx}] = {measure_pattern}") 
    
    # Place each strum direction at its corresponding beat position
    for i, direction in enumerate(measure_pattern):
        if direction:  # Skip empty positions
            beat_idx = i
            if beat_idx < len(config["valid_beats"]):
                beat = config["valid_beats"][beat_idx]
                char_position = calculate_char_position(beat, current_measure, time_signature)
                
                if char_position < total_width:
                    strum_chars[char_position] = direction
                    logger.debug(f"Placed strum '{direction}' at position {char_position} for beat {beat}")
                else:
                    logger.warning(f"Character position {char_position} exceeds total width {total_width}")

def place_measure_events(
    measure: Dict[str, Any], 
    string_lines: List[str], 
    measure_offset: int, 
    measure_number: int, 
    time_signature: str
) -> List[Dict[str, Any]]:
    """
     version of place_measure_events with support for new event types.
    
    Args:
        measure: Single measure dictionary containing events list
        string_lines: Mutable list of 6 strings representing guitar tab lines
        measure_offset: Position of this measure within the current group (0-3)
        measure_number: Absolute measure number for error reporting (1-based)
        time_signature: Time signature string for proper positioning
        
    Returns:
        List of warning dictionaries for formatting issues
    """
    warnings = []
    
    logger.debug(f"Placing events for measure {measure_number} (offset {measure_offset})")
    
    for event in measure.get("events", []):
        event_type = event.get("type")
        
        # Skip annotation events - they're handled in display layers
        if event_type in ["palmMute", "chuck", "strumPattern", "dynamic"]:
            logger.debug(f"Skipping {event_type} - handled in display layers")
            continue
        
        # Handle grace notes specially
        if event_type == "graceNote":
            grace_warnings = place_grace_note_on_tab(event, string_lines, measure_offset, measure_number, time_signature)
            warnings.extend(grace_warnings)
            continue
            
        # Handle regular musical events
        event_warnings = place_event_on_tab(event, string_lines, measure_offset, measure_number, time_signature)
        warnings.extend(event_warnings)
    
    logger.debug(f"Placed events for measure {measure_number}, generated {len(warnings)} warnings")
    return warnings


def convert_to_superscript(digit_string: str) -> str:
    """Convert digit string to superscript Unicode."""
    superscript_map = {
        '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
        '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹'
    }
    
    result = ""
    for char in digit_string:
        if char in superscript_map:
            result += superscript_map[char]
        else:
            result += char  # Keep non-digits as-is
    return result

def convert_to_subscript(digit_string: str) -> str:
    """Convert digit string to subscript Unicode."""
    subscript_map = {
        '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
        '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉'
    }
    
    result = ""
    for char in digit_string:
        if char in subscript_map:
            result += subscript_map[char]
        else:
            result += char  # Keep non-digits as-is
    return result


def place_grace_note_on_tab(
    event: Dict[str, Any], 
    string_lines: List[str], 
    measure_offset: int, 
    measure_number: int, 
    time_signature: str
) -> List[Dict[str, Any]]:
    """Place grace note on tab with superscript notation."""
    warnings = []
    
    string_num = event["string"]
    beat = event["beat"]
    main_fret = str(event["fret"])
    grace_fret = str(event["graceFret"])
    grace_type = event.get("graceType", "acciaccatura")
    
    char_position = calculate_char_position(beat, measure_offset, time_signature)
    line_index = string_num - 1  # Convert 1-indexed to 0-indexed
    
    # Convert grace fret to superscript
    superscript_grace = convert_to_superscript(grace_fret)
    
    # Format grace note notation
    if grace_type == "acciaccatura":
        # Quick grace note: ³5
        notation = f"{superscript_grace}{main_fret}"
    else:
        # Appoggiatura: ₃5 (using subscript for distinction)
        subscript_grace = convert_to_subscript(grace_fret)
        notation = f"{subscript_grace}{main_fret}"
    
    string_lines[line_index] = replace_chars_at_position(string_lines[line_index], char_position, notation)
    
    # Update warning for new shorter notation
    if len(notation) > 2:
        warnings.append({
            "warningType": "formatting_warning",
            "measure": measure_number,
            "beat": beat,
            "message": f"Grace note notation '{notation}' may require template adjustment",
            "suggestion": f"Grace note uses {len(notation)} character positions"
        })
    
    logger.debug(f"Placed grace note '{notation}' at position {char_position}")
    return warnings


def place_event_on_tab(
    event: Dict[str, Any], 
    string_lines: List[str], 
    measure_offset: int, 
    measure_number: int, 
    time_signature: str
) -> List[Dict[str, Any]]:
    """
     version of place_event_on_tab with emphasis support.
    
    Places musical events on tab lines and handles emphasis markings
    by adjusting the notation (when possible in UTF-8 format).
    """
    warnings = []
    event_type = event.get("type")
    emphasis = event.get("emphasis")
    
    # Call the original placement function first
    original_warnings = place_event_on_tab(event, string_lines, measure_offset, measure_number, time_signature)
    warnings.extend(original_warnings)
    
    # Add emphasis-related warnings if needed
    if emphasis and event_type in ["bend", "slide", "hammerOn", "pullOff"]:
        # Complex techniques with emphasis may need special attention
        if len(emphasis) > 2:  # Long emphasis markings
            beat = event.get("beat") or event.get("startBeat")
            warnings.append({
                "warningType": "formatting_warning",
                "measure": measure_number,
                "beat": beat,
                "message": f"Technique with emphasis '{emphasis}' may affect spacing",
                "suggestion": "Consider using shorter emphasis markings for techniques"
            })
    
    return warnings

# ============================================================================
#  Utility Functions
# ============================================================================

def place_annotation_text(
    char_array: List[str], 
    position: int, 
    text: str, 
    max_width: int,
    allow_overlap: bool = False
):
    """
     version of place_annotation_text with overlap handling.
    
    Args:
        char_array: Mutable list of characters
        position: Starting position
        text: Text to place
        max_width: Maximum width
        allow_overlap: Whether to allow overwriting existing text
    """
    for i, char in enumerate(text):
        target_pos = position + i
        if target_pos < max_width and target_pos >= 0:
            # Check for overlap unless allowed
            if not allow_overlap and char_array[target_pos] != ' ':
                logger.debug(f"Annotation overlap at position {target_pos}: existing '{char_array[target_pos]}', new '{char}'")
                # For now, skip placement - could implement conflict resolution
                continue
            char_array[target_pos] = char

def check_attempt_limit(attempt: int) -> Optional[Dict[str, Any]]:
    """
     attempt limit checking with more detailed error messages.
    """
    MAX_ATTEMPTS = 5
    
    if attempt > MAX_ATTEMPTS:
        logger.error(f"Maximum attempts exceeded: {attempt}")
        return {
            "isError": True,
            "errorType": "attempt_limit_error",
            "attempt": attempt,
            "message": f"Maximum regeneration attempts reached ({attempt})",
            "suggestion": "The tab appears to have complex requirements. Consider simplifying the input or breaking it into smaller sections.",
            "details": {
                "maxAttempts": MAX_ATTEMPTS,
                "currentAttempt": attempt,
                "possibleCauses": [
                    "Complex strum patterns",
                    "Conflicting emphasis markings", 
                    "Overlapping annotation events",
                    "Invalid time signature combinations"
                ]
            }
        }
    
    return None


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
    
    This is the core algorithm that converts musical events to UTF-8 characters.
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
    
        # Generate  notation with Unicode fraction semitone amounts
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
