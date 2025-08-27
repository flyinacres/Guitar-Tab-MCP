#!/usr/bin/env python3
"""
Tab Generator -  Core Implementation
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
import logging
from typing import Dict, List, Any, Tuple, Optional


from tab_constants import (
    DisplayLayer, DISPLAY_LAYER_ORDER,
    get_instrument_config
)
from tab_models import (
    TabRequest, SongPart, Measure, process_song_structure
)

from notation_events import (
    NotationEvent,
    Note, PalmMute, Chuck, Dynamic, StrumPattern, Chord,
    GraceNote, Slide, Bend, HammerOn, PullOff
)

from time_signatures import (
    get_time_signature_config,
    calculate_char_position,
    generate_beat_markers,
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
#  Tab Generation Engine
# ============================================================================



def generate_strum_line(measures: Measure,
                        num_measures: int, time_signature: str) -> str:
    """Generate strum line from measure strumPattern fields."""
    total_width = calculate_total_width(time_signature, num_measures)
    strum_chars = [' '] * total_width

    for measure_idx, measure in enumerate(measures):
        strum_pattern = measure.strumPattern
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



def generate_measure_group(
    measures: Measure,
    start_index: int,
    time_signature: str,
    measure_info: Dict[str, Any]
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Generate  tab section with multi-layer display.

    Creates all display layers:
    - Chord names (when present)
    - Dynamics (when present)
    - Annotations (PM, X, emphasis markings)
    - Beat markers
    - Tab content 
    - Strum patterns (when present)

    Args:
        measures: List of Measures
        start_index: Starting measure number for warnings
        time_signature: Time signature string
        measure_info: Data needed for measure info

    Returns:
        Tuple of (output_lines, warnings)
    """
    warnings = []
    num_measures = len(measures)

    # Combine all layers in proper order
    result = []

    logger.debug(f"Generating  measure group: {num_measures} measures of {time_signature}")

    # Generate all display layers
    display_layers = generate_all_display_layers(measures, num_measures, time_signature)

    # Generate beat markers using time signature module
    beat_line = generate_beat_markers(time_signature, num_measures)
    # Two spaces in front for note names like Db
    beat_line = "  " + beat_line


    # Initialize string lines with correct template for time signature
    string_lines = []
    result.extend(string_lines)

    content_width = get_content_width(time_signature)

    for string_idx in range(measure_info["num_strings"]):
        note = measure_info["tuning"][string_idx].ljust(2)
        line = note + "|"  # Start with opening separator
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
    show_beat_markers = measure_info.get("showBeatMarkers", True)
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
    measures: Measure,
    num_measures: int,
    time_signature: str
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
        process_measure_for_display_layers(measure, measure_idx, time_signature,
                                           layers, total_width)

    # Convert character arrays to strings and remove trailing spaces
    result = {}
    for layer, char_array in layers.items():
        content = "".join(char_array).rstrip()
        if content:  # Only include non-empty layers
            result[layer] = content
            logger.debug(f"Generated {layer.value}: '{content[:50]}{'...' if len(content) > 50 else ''}'")

    return result

def process_measure_for_display_layers(
    measure: Measure,
    measure_idx: int,
    time_signature: str,
    layers: Dict[DisplayLayer, List[str]],
    total_width: int
):
    """
    Process a single measure and populate all display layers.
    """
    for event in measure.events:
        event_class = NotationEvent.from_dict(event)
        beat = getattr(event_class, 'beat', None) or getattr(event_class, 'startBeat', None)

        # Only working with beat-based logic here
        if beat is None:
            continue

        char_position = calculate_char_position(beat, measure_idx, time_signature)

        # Process different event types for appropriate layers
        match event_class:
            case Chord():
                # Chord names layer
                if event_class.chordName:
                    place_annotation_text(layers[event_class.layer], char_position, event_class.chordName, total_width)

                # Emphasis on chords goes to dynamics layer
                if event_class.emphasis:
                    place_annotation_text(layers[DisplayLayer.DYNAMICS], char_position, event_class.emphasis, total_width)

            case Note():
                # Emphasis on notes goes to dynamics layer
                if event_class.emphasis:
                    place_annotation_text(layers[DisplayLayer.DYNAMICS], char_position, event_class.emphasis, total_width)

            case PalmMute():
                place_annotation_text(layers[event_class.layer], char_position, event_class.generate_notation(), total_width)

            case Chuck():
                place_annotation_text(layers[event_class.layer], char_position, event_class.generate_notation(), total_width)

            case Dynamic():
                if event_class.dynamic:
                    place_annotation_text(layers[event_class.layer], char_position, event_class.generate_notation(), total_width)

            case StrumPattern():
                event_class.process_strum_pattern(measure_idx, time_signature, layers[event_class.layer], total_width)


def place_measure_events(
    measure: Measure,
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
    # Grace notes should always be followed by a target note, which should not be placed
    graceNotePlaced = False

    logger.debug(f"Placing events for measure {measure_number} (offset {measure_offset})")

    for event in measure.events:
        event_class = NotationEvent.from_dict(event)

        if isinstance(event_class, (PalmMute, Chuck, StrumPattern, Dynamic)):
            logger.debug(f"Skipping {event_class._type} - handled in display layers")
            graceNotePlaced = False
            continue

        # Handle grace notes specially
        if isinstance(event_class, (GraceNote)):
            char_position = calculate_char_position(event_class.beat, measure_offset, time_signature)
            notation = event_class.generate_notation()
            string_lines[event_class.string - 1] = replace_chars_at_position(string_lines[event_class.string - 1], char_position, notation)

            # Update warning for new shorter notation
            if len(notation) > 2:
                warnings.append({
                    "warningType": "formatting_warning",
                    "measure": measure_number,
                    "beat": event_class.beat,
                    "message": f"Grace note notation '{notation}' may require template adjustment",
                    "suggestion": f"Grace note uses {len(notation)} character positions"
                })

            logger.debug(f"Placed grace note '{notation}' at position {char_position}")
            
            graceNotePlaced = True
            continue

        if isinstance(event_class, (Note)) and graceNotePlaced:
            graceNotePlaced = False
            continue
        
        # Handle regular musical events
        event_warnings = place_event_on_tab(event_class, string_lines, measure_offset, measure_number, time_signature)
        warnings.extend(event_warnings)
        graceNotePlaced = False

    logger.debug(f"Placed events for measure {measure_number}, generated {len(warnings)} warnings")
    return warnings


def place_event_on_tab(
    event_class: NotationEvent,
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
    emphasis = event_class.emphasis

    match event_class:
        case Note():
            char_position = calculate_char_position(event_class.beat, measure_offset, time_signature)
            fret_str = event_class.generate_notation()
            string_lines[event_class.string - 1] = replace_chars_at_position(string_lines[event_class.string - 1], char_position, fret_str)

            # Warn about multi-digit frets or vibrato that may cause alignment issues
            if len(fret_str) > 1:
                warnings.append({
                    "warningType": "formatting_warning",
                    "measure": measure_number,
                    "beat": event_class.beat,
                    "message": f"Multi-digit fret ({fret_str}) may affect template alignment",
                    "suggestion": f"Fret {fret_str} uses {len(fret_str)} character positions"
                })

        case Chord():
            char_position = calculate_char_position(event_class.beat, measure_offset, time_signature)

            max_fret_width = 0
            for fret_info in event_class.frets:
                # These are not strings and frets on the class, they are in the frets object
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
                    "beat": event_class.beat,
                    "message": f"Chord with multi-digit frets may affect alignment",
                    "suggestion": f"Chord requires {max_fret_width} character positions"
                })

        case HammerOn() | PullOff():
            char_position = calculate_char_position(event_class.startBeat, measure_offset, time_signature)
            technique_str = event_class.generate_notation()
            string_lines[event_class.string - 1] = replace_chars_at_position(string_lines[event_class.string - 1], char_position, technique_str)

            # Warn about wide technique notations
            if len(technique_str) > 3:
                warnings.append({
                    "warningType": "formatting_warning",
                    "measure": measure_number,
                    "beat": event_class.beat,
                    "message": f"Technique notation '{technique_str}' may require template adjustment",
                    "suggestion": f"Technique uses {len(technique_str)} character positions"
                })

        case Slide():
            char_position = calculate_char_position(event_class.startBeat, measure_offset, time_signature)
            technique_str = event_class.generate_notation()

            string_lines[event_class.string - 1] = replace_chars_at_position(string_lines[event_class.string - 1], char_position, technique_str)

            if len(technique_str) > 3:
                warnings.append({
                    "warningType": "formatting_warning",
                    "measure": measure_number,
                    "beat": event_class.beat,
                    "message": f"Slide notation '{technique_str}' may require template adjustment",
                    "suggestion": f"Slide uses {len(technique_str)} character positions"
                })

        case Bend():
            char_position = calculate_char_position(event_class.beat, measure_offset, time_signature)
            # Generate notation with Unicode fraction semitone amounts
            technique_str = event_class.generate_notation()
            string_lines[event_class.string - 1] = replace_chars_at_position(string_lines[event_class.string - 1], char_position, technique_str)

            # Add warning for wide bend notations
            if len(technique_str) > 2:
                warnings.append({
                    "warningType": "formatting_warning",
                    "measure": measure_number,
                    "beat": event_class.beat,
                    "message": f"Bend notation '{technique_str}' may require template adjustment",
                    "suggestion": f"Bend notation uses {len(technique_str)} character positions"
                    })

    # Add emphasis-related warnings if needed
    if emphasis and isinstance(event_class, (Bend, Slide, HammerOn, PullOff)):
        # Complex techniques with emphasis may need special attention
        if len(emphasis) > 2:  # Long emphasis markings
            beat = getattr(event_class, 'beat', None) or getattr(event_class, 'startBeat', None)
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

def place_annotation_text_wEvent(event: NotationEvent, char_array: List[str],):
    {
        #layerToUse = layers[event.layer]
        #place_annotation_text(char_array, char_position, pm_text, total_width)
    }

def place_annotation_text(
    char_array: List[str],
    position: int,
    text: str,
    max_width: int,
    allow_overlap: bool = False
):
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
            # Check for overlap unless allowed
            if not allow_overlap and char_array[target_pos] != ' ':
                logger.debug(f"Annotation overlap at position {target_pos}: existing '{char_array[target_pos]}', new '{char}'")
                # For now, skip placement - could implement conflict resolution
                continue
            char_array[target_pos] = char


def generate_tab_output(request: TabRequest) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Generate tab using parts format with section headers.

    Generates tabs with up to 6 display layers:
    1. Chord names
    2. Dynamics markings
    3. Annotations (PM, X, emphasis)
    4. Beat markers
    5. Tab content (6 string lines)
    6. Strum patterns

    Args:
        request: Validated tab specification dictionary

    Returns:
        Tuple of (tab_string, warnings_list)
    """
    logger.info(f"Generating parts-based tab for '{request.title}'")

    warnings = []
    output_lines = []

    # Generate header
    header_lines = generate_header(request)
    output_lines.extend(header_lines)
    output_lines.append("")

    # Set technique formatting style for all events
    NotationEvent.set_technique_style(request.techniqueStyle)
    
    # Reset count for new tab generation
    NotationEvent._technique_count = 0

    # Process song structure
    try:
        instances = process_song_structure(request)
        logger.info(f"Generated {len(instances)} part instances")
    except Exception as e:
        logger.error(f"Failed to process song structure: {e}")
        return f"Error processing song structure: {e}", [{"error": str(e)}]

    # Get instrument configuration for string count
    instrument_str = request.instrument
    try:
        config = get_instrument_config(instrument_str)
        num_strings = config.strings
        if request.tuning:
            tuning = request.tuning
        else:
            tuning = config.tuning
        logger.debug(f"Generating tab for {config.name} ({num_strings} strings)")
    except ValueError:
        num_strings = 6  # Default to guitar
        logger.warning(f"Unknown instrument {instrument_str}, defaulting to 6 strings")

    # Generate each part instance
    for instance in instances:
        logger.debug(f"Generating tab for {instance.display_name}")

        # Add part header
        if request.showPartHeaders:
            part_header_lines = generate_part_header(instance, request)
            output_lines.extend(part_header_lines)
            output_lines.append("")

        # Generate measures for this part
        part_measures = instance.measures
        part_time_sig = instance.time_signature_change or request.timeSignature

        # Process measures in groups of 4
        for measure_group_start in range(0, len(part_measures), 4):
            measure_group = part_measures[measure_group_start:measure_group_start + 4]

            # Create temporary data for existing generation logic
            measure_info = {
                "title": f"{instance.display_name}",
                "timeSignature": part_time_sig,
                "measures": measure_group,
                "num_strings": num_strings,
                "tuning": tuning
            }

            # Generate measure group
            tab_section, section_warnings = generate_measure_group(
                measure_group, measure_group_start, part_time_sig, measure_info
            )
            warnings.extend(section_warnings)
            output_lines.extend(tab_section)
            output_lines.append("")

        output_lines.append("")  # Extra space between parts

    logger.info(f"Generated parts-based tab with {len(warnings)} warnings")
    return "\n".join(output_lines), warnings


# ============================================================================
# Header Generation Functions
# ============================================================================

def generate_header(request: TabRequest) -> List[str]:
    """Generate header for parts-based songs."""
    lines = []

    # Title and basic info
    lines.append(f"# {request.title}")
    if request.artist:
        lines.append(f"**Artist:** {request.artist}")
    if request.description:
        lines.append(f"*{request.description}*")

    # Musical information
    info_parts = [f"**Time Signature:** {request.timeSignature}"]
    if request.tempo:
        info_parts.append(f"**Tempo:** {request.tempo} BPM")
    if request.tuning_name:
        info_parts.append(f"**Custom Tuning:** {request.tuning_name}")
    if request.key:
        info_parts.append(f"**Key:** {request.key}")
    if request.capo:
        info_parts.append(f"**Capo:** {request.capo}")

    lines.append(" | ".join(info_parts))

    # Song structure overview
    if request.parts and request.structure:
        lines.append("")
        lines.append("**Song Structure:**")

        # Show structure with numbering
        structure_display = []
        part_counters = {}

        for part_name in request.structure:
            part_counters[part_name] = part_counters.get(part_name, 0) + 1
            numbered_name = f"{part_name} {part_counters[part_name]}"
            structure_display.append(numbered_name)

        lines.append(" → ".join(structure_display))

        # Show part definitions
        lines.append("")
        lines.append("**Parts Defined:**")
        for part in request.parts:
            measure_count = len(part.measures)
            part_info = f"- **{part.name}**: {measure_count} measure{'s' if measure_count != 1 else ''}"
            if part.description:
                part_info += f" - {part.description}"
            lines.append(part_info)

    return lines


def generate_part_header(instance: SongPart, request: TabRequest) -> List[str]:
    """Generate header for individual song parts."""
    lines = []

    # Part name as section header
    lines.append(f"## {instance.display_name}")

    # Part-specific information
    part_def = next((part for part in request.parts if part.name == instance.name), None)

    if part_def.description:
        lines.append(f"*{part_def.description}*")

    # Musical changes for this part
    changes = []
    if instance.tempo_change != None and instance.tempo_change != request.tempo:
        changes.append(f"**Tempo:** {instance.tempo_change} BPM")
    if instance.key_change != None and instance.key_change != request.key:
        changes.append(f"**Key:** {instance.key_change}")
    if instance.time_signature_change != None and instance.time_signature_change != request.timeSignature:
        changes.append(f"**Time Signature:** {instance.time_signature_change}")

    if changes:
        lines.append(" | ".join(changes))

    return lines


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
    """ attempt limit checking with parts-specific guidance."""
    MAX_ATTEMPTS = 5

    if attempt > MAX_ATTEMPTS:
        return {
            "isError": True,
            "errorType": "attempt_limit_error",
            "attempt": attempt,
            "message": f"Maximum regeneration attempts reached ({attempt})",
            "suggestion": "Consider simplifying the song structure or breaking into smaller sections.",
            "details": {
                "possibleCauses": [
                    "Complex song structure with many parts",
                    "Invalid part references in structure",
                    "Complex strum patterns",
                    "Conflicting emphasis markings"
                ]
            }
        }

    return None

logger.info("Core module with system loaded successfully")
