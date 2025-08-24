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
import logging
from typing import Dict, List, Any, Tuple, Optional


from tab_constants import (
    DisplayLayer, DISPLAY_LAYER_ORDER,
    get_instrument_config
)
from tab_models import (
    TabRequest, PartInstance,
    process_song_structure
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



def generate_strum_line(measures: List[Dict[str, Any]],
                        num_measures: int, time_signature: str) -> str:
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


# ============================================================================
# Annotation System Functions
# ============================================================================


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

    for string_idx in range(tab_data["num_strings"]):
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
    if semitones == 0.5:
        return "½"
    if semitones == 0.75:
        return "¾"
    if semitones == 1.25:
        return "1¼"
    if semitones == 1.5:
        return "1½"
    if semitones == 1.75:
        return "1¾"
    if semitones == 2.25:
        return "2¼"
    if semitones == 2.5:
        return "2½"
    if semitones == 2.75:
        return "2¾"
    if semitones == 3.0:
        return "3"
    # Handle whole numbers (remove .0)
    if semitones == int(semitones):
        return str(int(semitones))
    # Fallback for unusual decimal values

    return str(semitones)




def generate_tab_output(data: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
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
        data: Validated tab specification dictionary

    Returns:
        Tuple of (tab_string, warnings_list)
    """
    request = TabRequest(**data)
    logger.info(f"Generating parts-based tab for '{request.title}'")

    warnings = []
    output_lines = []

    # Generate header
    header_lines = generate_header(request)
    output_lines.extend(header_lines)
    output_lines.append("")

    # Process song structure
    try:
        instances = process_song_structure(request)
        logger.info(f"Generated {len(instances)} part instances")
    except Exception as e:
        logger.error(f"Failed to process song structure: {e}")
        return f"Error processing song structure: {e}", [{"error": str(e)}]

    # Get instrument configuration for string count
    instrument_str = data.get("instrument", "guitar")
    try:
        config = get_instrument_config(instrument_str)
        num_strings = config.strings
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
        part_time_sig = instance.time_signature or request.timeSignature

        # Process measures in groups of 4
        for measure_group_start in range(0, len(part_measures), 4):
            measure_group = part_measures[measure_group_start:measure_group_start + 4]

            # Create temporary data for existing generation logic
            temp_data = {
                "title": f"{instance.display_name}",
                "timeSignature": part_time_sig,
                "measures": measure_group,
                "num_strings": num_strings
            }

            # Generate measure group
            tab_section, section_warnings = generate_measure_group(
                measure_group, measure_group_start, part_time_sig, temp_data
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
        for part_name, part_def in request.parts.items():
            measure_count = len(part_def.measures)
            part_info = f"- **{part_name}**: {measure_count} measure{'s' if measure_count != 1 else ''}"
            if part_def.description:
                part_info += f" - {part_def.description}"
            lines.append(part_info)

    return lines


def generate_part_header(instance: PartInstance, request: TabRequest) -> List[str]:
    """Generate header for individual song parts."""
    lines = []

    # Part name as section header
    lines.append(f"## {instance.display_name}")

    # Part-specific information
    part_def = request.parts[instance.part_name]

    if part_def.description:
        lines.append(f"*{part_def.description}*")

    # Musical changes for this part
    changes = []
    if instance.tempo != request.tempo:
        changes.append(f"**Tempo:** {instance.tempo} BPM")
    if instance.key != request.key:
        changes.append(f"**Key:** {instance.key}")
    if instance.time_signature != request.timeSignature:
        changes.append(f"**Time Signature:** {instance.time_signature}")

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
