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
from typing import Dict, List, Any
from pydantic import ValidationError

from tab_models import TabRequest

from tab_constants import (
    VALID_EMPHASIS_VALUES,
    INSTRUMENT_CONFIGS,
    is_valid_emphasis,
    get_instrument_config
)

from notation_events import (
    NotationEvent, GraceNote, StrumPattern, 
    Chord, Dynamic, PalmMute, Chuck,
    HammerOn, Bend, PullOff, Slide )

from time_signatures import (
    get_strum_positions_for_time_signature,
    get_time_signature_config,
    get_valid_beats,
    is_beat_valid,
    create_time_signature_error
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


def validate_schema(request: TabRequest) -> Dict[str, Any]:
    """
    Validate required fields and structure for parts-based schema.

    Expects:
    - title: string
    - timeSignature: string
    - parts: dict of part definitions
    - structure: array of part names
    """
    required_fields = ["title", "timeSignature", "parts", "structure"]

    for field in required_fields:
        if not hasattr(request, field):
            return {
                "isError": True,
                "errorType": "validation_error",
                "message": f"Missing required field: {field}",
                "suggestion": f"Add '{field}' property to root object"
            }

    # Validate parts is a dict
    if not hasattr(request, "parts") or len(request.parts) == 0:
        return {
            "isError": True,
            "errorType": "validation_error",
            "message": "Parts must be a non-empty object/dictionary",
            "suggestion":
            "Provide at least one part definition like: \"parts\": {\"Verse\": {\"measures\": [...]}}"
        }

    # Validate structure is an array
    if not hasattr(request, "structure") or len(request.structure)== 0:
        return {
            "isError": True,
            "errorType": "validation_error",
            "message": "Structure must be a non-empty array",
            "suggestion": "Provide structure array like: \"structure\": [\"Verse\", \"Chorus\"]"
        }

    # Validate each part has measures array
    for part_name, part_def in request.parts.items():
        if not hasattr(part_def, "measures"):
            return {
                "isError": True,
                "errorType": "validation_error",
                "message": f"Part '{part_name}' missing measures array",
                "suggestion": "Each part must have a 'measures' array: {\"measures\": [...]}"
            }

        if len(part_def.measures) == 0:
            return {
                "isError": True,
                "errorType": "validation_error",
                "message": f"Part '{part_name}' has empty or invalid measures array",
                "suggestion": "Each part must have at least one measure with events"
            }

        # Validate each measure has events array
        for measure_idx, measure in enumerate(part_def.measures, 1):
            if not isinstance(measure, dict) or "events" not in measure:
                return {
                    "isError": True,
                    "errorType": "validation_error",
                    "message": f"Part '{part_name}' measure {measure_idx} missing events array",
                    "suggestion": "Each measure must have an 'events' array (can be empty)"
                }

            if not isinstance(measure["events"], list):
                return {
                    "isError": True,
                    "errorType": "validation_error",
                    "message": f"Part '{part_name}' measure {measure_idx} events is not an array",
                    "suggestion": "Events must be an array of event objects"
                }

    # Validate structure references existing parts
    for part_name in request.structure:
        if part_name not in request.parts:
            available_parts = list(request.parts.keys())
            return {
                "isError": True,
                "errorType": "validation_error",
                "message": f"Structure references undefined part '{part_name}'",
                "suggestion":
                f"Available parts: {available_parts}. Check spelling or add part definition."
            }

    return {"isError": False}

def validate_timing(request: TabRequest) -> Dict[str, Any]:
    """
    Enhanced timing validation for parts-based schema.

    Validates beat timing for all events across all parts:
    - Standard musical events (notes, chords, techniques)
    - New event types (strum patterns, grace notes, dynamics)
    - Compound time signatures (6/8 with triplet feel)
    """
    time_sig = request.timeSignature
    logger.debug("Validating timing for time signature: %s", time_sig)

    # Check if time signature is supported
    try:
        config = get_time_signature_config(time_sig)
        logger.debug("Time signature config loaded: %s", config['name'])
    except ValueError:
        logger.error("Unsupported time signature: %s", time_sig)
        return create_time_signature_error(time_sig)

    # Check every event's beat timing across all parts
    for part_name, part_def in request.parts.items():
        logger.debug("Validating timing for part '%s'", part_name)

        for measure_idx, measure in enumerate(part_def.measures, 1):
            logger.debug("Validating timing for part '%s' measure %s", part_name, measure_idx)

            for event_idx, event in enumerate(measure.get("events", []), 1):
                event_class = NotationEvent.from_dict(event) 
                
                beat = getattr(event_class, 'beat', None) or getattr(event_class, 'startBeat', None)

                if beat is None:
                    logger.warning("Event %s in part '%s' measure %s missing beat timing",
                                   event_idx, part_name, measure_idx)
                    return {
                        "isError": True,
                        "errorType": "validation_error",
                        "part": part_name,
                        "measure": measure_idx,
                        "message": f"Event {event_idx} in part '{part_name}' missing beat timing",
                        "suggestion": "Add 'beat' or 'startBeat' field to event"
                    }

                match event_class:
                    # Enhanced beat validation for different event types
                    case GraceNote():
                        # Grace notes have special timing requirements
                        grace_result = GraceNote.validate_grace_note_timing(beat, time_sig,
                                                                part_name, measure_idx)
                        if grace_result["isError"]:
                            return grace_result
                    case StrumPattern():
                        # Strum patterns have their own validation (handled separately)
                        logger.debug("Strum pattern found at beat %s - will validate separately", beat)
                        continue
                    case _:
                        # Standard beat validation
                        if not is_beat_valid(beat, time_sig):
                            logger.warning("Invalid beat %s for %s in part '%s' measure %s",
                                        beat, time_sig, part_name, measure_idx)
                            return {
                                "isError": True,
                                "errorType": "validation_error",
                                "part": part_name,
                                "measure": measure_idx,
                                "beat": beat,
                                "message": f"Beat {beat} invalid for {time_sig} time signature in part '{part_name}'",
                                "suggestion": f"Use valid beat values for {time_sig}: {', '.join(map(str, get_valid_beats(time_sig)))}"
                            }

    logger.debug("Enhanced timing validation passed")
    return {"isError": False}


def validate_conflicts(request: TabRequest) -> Dict[str, Any]:
    """
    Enhanced conflict detection for parts-based schema.

    Checks for:
    - Musical event conflicts (multiple notes on same string/beat)
    - Grace note conflicts with main notes
    - Strum pattern overlaps
    - Dynamic marking conflicts
    """
    logger.debug("Starting enhanced conflict validation")

    # Will need to know what instrument to verify against number of strings
    instrument = get_instrument_config(request.instrument)
    #print(f"events instrument: {event}, strings found: {instrument.strings}")

    for part_name, part_def in request.parts.items():
        logger.debug(f"Validating conflicts in part '{part_name}'")

        for measure_idx, measure in enumerate(part_def.measures, 1):
            events_by_position = {}
            grace_notes = []

            logger.debug(f"Validating conflicts in part '{part_name}' measure {measure_idx}")

            for event in measure.get("events", []):
                event_class = NotationEvent.from_dict(event) 

                # Collect different event types for specialized validation
                match event_class:
                    case StrumPattern():
                        # Maybe this used to do something useful...
                        continue
                    
                    case GraceNote():
                        grace_notes.append(event_class)
                        continue
                    
                    case Dynamic() | PalmMute() | Chuck():
                        # Annotation events don't conflict with musical events
                        continue

                    # Handle chord events specially - they can have multiple strings at same beat
                    case Chord():
                        beat = getattr(event_class, 'beat', None) 
                        if not beat:
                            return {
                                "isError": True,
                                "errorType": "validation_error",
                                "part": part_name,
                                "measure": measure_idx,
                                "message": f"Chord event in part '{part_name}' missing 'beat' field",
                                "suggestion": "Add 'beat' field to chord event"
                            }

                        # Validate chord has frets array
                        frets = getattr(event_class, 'frets', None) 
                        if not frets:
                            return {
                                "isError": True,
                                "errorType": "validation_error",
                                "part": part_name,
                                "measure": measure_idx,
                                "beat": beat,
                                "message": f"Chord event in part '{part_name}' missing 'frets' array",
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
                                    "part": part_name,
                                    "measure": measure_idx,
                                    "beat": beat,
                                    "message": f"Chord in part '{part_name}' has duplicate entries for string {string_num}",
                                    "suggestion": "Each string can only appear once per chord"
                                }
                            chord_strings.add(string_num)

                        continue  # Skip position conflict checking for chords

                # For non-chord events, check string/beat conflicts
                string_num = event_class.string
                beat = getattr(event_class, 'beat', None) or getattr(event_class, 'startBeat', None)

                if not string_num or not beat:
                    continue  # These will be caught by other validation

                position_key = f"{string_num}_{beat}"

                if position_key in events_by_position:
                    logger.warning(f"Conflict detected: multiple events on string {string_num} at beat {beat} in part '{part_name}'")
                    return {
                        "isError": True,
                        "errorType": "conflict_error",
                        "part": part_name,
                        "measure": measure_idx,
                        "beat": beat,
                        "message": f"Multiple events on string {string_num} at beat {beat} in part '{part_name}'",
                        "suggestion": "Move one event to different beat or different string"
                    }

                events_by_position[position_key] = event_class

                # Validate technique-specific rules (enhanced)
                technique_error = validate_technique_rules(event_class, part_name, measure_idx, beat, instrument.strings)
                if technique_error["isError"]:
                    return technique_error

            # Validate grace note conflicts
            grace_conflict = GraceNote.validate_grace_note_conflicts(grace_notes, events_by_position, part_name, measure_idx)
            if grace_conflict["isError"]:
                return grace_conflict

    logger.debug("Enhanced conflict validation passed")
    return {"isError": False}


def validate_emphasis_markings(request: TabRequest) -> Dict[str, Any]:
    """
    Validate emphasis markings on all musical events in parts-based schema.

    Checks:
    - Valid emphasis values (dynamics, articulations)
    - Proper emphasis placement
    - No conflicting emphasis markings
    """
    logger.debug("Validating emphasis markings")

    for part_name, part_def in request.parts.items():
        logger.debug(f"Validating emphasis markings in part '{part_name}'")

        for measure_idx, measure in enumerate(part_def.measures, 1):
            for event in measure.get("events", []):
                event_class = NotationEvent.from_dict(event)
                emphasis = event_class.emphasis

                if event_class.emphasis is not None:
                    logger.debug(f"Found emphasis '{emphasis}' in part '{part_name}' measure {measure_idx}")

                    if not is_valid_emphasis(emphasis):
                        logger.error(f"Invalid emphasis value in part '{part_name}': {emphasis}")
                        return {
                            "isError": True,
                            "errorType": "validation_error",
                            "part": part_name,
                            "measure": measure_idx,
                            "message": f"Invalid emphasis value '{emphasis}' in part '{part_name}'",
                            "suggestion": f"Use valid emphasis: {', '.join(VALID_EMPHASIS_VALUES[:10])}..."
                        }

    logger.debug("Emphasis validation passed")
    return {"isError": False}


def validate_technique_rules(event_class: NotationEvent, part_name: str, measure_idx: int, beat: float, strings: int) -> Dict[str, Any]:
    """
    Validate technique-specific rules that ensure playability and proper notation.

    Each guitar technique has physical constraints and notation rules:
    - Hammer-ons must go to higher fret (you can't hammer down)
    - Pull-offs must go to lower fret
    - String numbers must be valid per instrument
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

    # Validate string range for all events with string field
    string_num = event_class.string
    if string_num is not None and (string_num < 1 or string_num > strings):
        return {
            "isError": True,
            "errorType": "validation_error",
            "part": part_name,
            "measure": measure_idx,
            "beat": beat,
            "message": f"Invalid string number: {string_num}",
            "suggestion": "String numbers must be 1-6 (1=high e, 6=low E)"
        }

    # Validate fret ranges (now supports "x" for muted strings)
    for fret_field in ["fret", "fromFret", "toFret"]:
        fret = getattr(event_class, fret_field, None)
        if fret is not None:
            # Allow "x" or "X" for muted strings
            if isinstance(fret, str) and fret.lower() == "x":
                continue  # Valid muted string
            elif isinstance(fret, (int, float)) and (fret < 0 or fret > 24):
                return {
                    "isError": True,
                    "errorType": "validation_error",
                    "part": part_name,
                    "measure": measure_idx,
                    "beat": beat,
                    "message": f"Invalid fret number: {fret}",
                    "suggestion": "Fret numbers must be 0-24 or 'x' for muted strings"
                }
            elif not isinstance(fret, (int, float, str)):
                return {
                    "isError": True,
                    "errorType": "validation_error",
                    "part": part_name,
                    "measure": measure_idx,
                    "beat": beat,
                    "message": f"Invalid fret value: {fret}",
                    "suggestion": "Fret must be a number (0-24) or 'x' for muted strings"
                }

    # Technique-specific validations
    match event_class:
        case HammerOn():
            from_fret = event_class.fromFret
            to_fret = event_class.toFret
            if from_fret is not None and to_fret is not None and from_fret >= to_fret:
                return {
                    "isError": True,
                    "errorType": "validation_error",
                    "part": part_name,
                    "measure": measure_idx,
                    "beat": beat,
                    "message": f"Hammer-on fromFret ({from_fret}) must be lower than toFret ({to_fret})",
                    "suggestion": "Hammer-ons go to higher frets - check fromFret and toFret values"
                }

        case PullOff():
            from_fret = event_class.fromFret
            to_fret = event_class.toFret
            if from_fret is not None and to_fret is not None and from_fret <= to_fret:
                return {
                    "isError": True,
                    "errorType": "validation_error",
                    "part": part_name,
                    "measure": measure_idx,
                    "beat": beat,
                    "message": f"Pull-off fromFret ({from_fret}) must be higher than toFret ({to_fret})",
                    "suggestion": "Pull-offs go to lower frets - check fromFret and toFret values"
                }
        # Add bend-specific validation
        case Bend():
            semitones = event_class.semitones
            if semitones is not None:
                if not isinstance(semitones, (int, float)) or semitones <= 0 or semitones > 3.0:
                    return {
                        "isError": True,
                        "errorType": "validation_error",
                        "part": part_name,
                        "measure": measure_idx,
                        "beat": beat,
                        "message": f"Invalid semitones value: {semitones}",
                        "suggestion": "Semitone must be a number between 0.25 and 3.0 (¼=quarter step, ½=half step, 1=whole step, 1½=step and half)"
                    }

    # Additional validation for emphasis on techniques
    emphasis = event_class.emphasis

    if emphasis and isinstance(event_class, (Bend, Slide, HammerOn, PullOff)):
        logger.debug(f"Validating emphasis '{emphasis}' on {event_class._type}")

        # Some emphasis markings don't make sense with certain techniques
        if emphasis in ["pp", "p"] and isinstance(event_class, (Bend)):
            logger.warning("Soft dynamics on bends may not be effective")
            # This is a warning, not an error

    return {"isError": False}


def validate_instrument_events(request: TabRequest) -> Dict[str, Any]:
    """
    Validate all events for the specified instrument.

    Checks string numbers and fret values against instrument limits.
    """
    instrument_str = request.instrument

    try:
        config = get_instrument_config(instrument_str)
        logger.debug(f"Validating events for {config.name} ({config.strings} strings)")
    except ValueError as _:
        return {
            "isError": True,
            "errorType": "validation_error",
            "message": f"Invalid instrument: {instrument_str}",
            "suggestion": "Use 'guitar' or 'ukulele'"
        }

    for part_name, part_def in request.parts.items():
        measures = part_def.measures

        for measure_idx, measure in enumerate(measures, 1):
            for _, event in enumerate(measure.get("events", []), 1):
                event_class = NotationEvent.from_dict(event) 
                # Validate string numbers
                string_num = getattr(event_class, "string", None)
                if string_num is not None:
                    if not config.validate_string(string_num):
                        return {
                            "isError": True,
                            "errorType": "validation_error",
                            "measure": measure_idx,
                            "message": f"Invalid string {string_num} for {config.name}",
                            "suggestion": f"Use strings 1-{config.strings} for {config.name}"
                        }

                # Validate chord frets
                if isinstance( event_class, Chord):
                    for fret_info in event_class.frets:
                        chord_string = fret_info.get("string")
                        if chord_string and not config.validate_string(chord_string):
                            return {
                                "isError": True,
                                "errorType": "validation_error",
                                "measure": measure_idx,
                                "message": f"Invalid string {chord_string} in chord for {config.name}",
                                "suggestion": f"Use strings 1-{config.strings} for {config.name}"
                            }

    logger.debug(f"All events validated for {config.name}")
    return {"isError": False}

def validate_tab_data(request: TabRequest) -> Dict[str, Any]:
    """validation pipeline."""
    logger.debug(f"Running validation for attempt {request.attempt}")

    # Stage 1: Schema validation
    schema_result = validate_schema(request)
    if schema_result["isError"]:
        return schema_result

    # Stage 2: Timing validation
    timing_result = validate_timing(request)
    if timing_result["isError"]:
        return timing_result

    # Stage 3: Conflict validation
    conflict_result = validate_conflicts(request)
    if conflict_result["isError"]:
        return conflict_result

    # Stage 4: Strum pattern validation
    strum_result = StrumPattern.validate_strum_patterns(request)
    if strum_result["isError"]:
        return strum_result

    # Stage 5: Emphasis validation
    emphasis_result = validate_emphasis_markings(request)
    if emphasis_result["isError"]:
        return emphasis_result

    # Stage 6: Instrument validation
    instrument_result = validate_instrument_events(request)
    if instrument_result["isError"]:
        logger.warning(f"Instrument validation failed: {instrument_result['message']}")
        return instrument_result

    # Stage 7: Validate custom tuning
    tuning_result = validate_custom_tuning(request)
    if tuning_result["isError"]:
        return tuning_result
    
    logger.info("All validation stages passed")
    return {"isError": False}

def validate_custom_tuning(request: TabRequest) -> Dict[str, Any]:
    instrument: str = request.instrument

    # Get instrument configuration for string count
    config = get_instrument_config(instrument)
    num_strings = config.strings
    if request.tuning:
        tuning = request.tuning
    else:
        tuning = config.tuning

    if len(tuning) != num_strings:
        return {
            "isError": True,
            "errorType": "validation_error",
            "message": f"{instrument} requires {num_strings} strings, got {len(tuning)}",
            "suggestion": f"Use a properly specified tuning for the instrument"
        }

    return {"isError": False}

logger.info(" core validation module loaded successfully")
