#!/usr/bin/env python3
"""
Core Tab Generation with Parts System
=====================================

Updated core functionality to support the new parts/sections system while
maintaining full backwards compatibility with the legacy measures format.
"""

import sys
import json
import logging
from typing import Dict, List, Any, Tuple, Optional
from tab_constants import get_instrument_config, get_max_string, Instrument

# Import existing functionality
from tab_constants import (
    StrumDirection, DynamicLevel, ArticulationMark, VALID_EMPHASIS_VALUES,
    STRUM_POSITIONS_PER_MEASURE, get_strum_positions_for_time_signature,
    is_valid_emphasis, ERROR_MESSAGES, DisplayLayer, DISPLAY_LAYER_ORDER
)
from tab_models import TabRequest, TabResponse
from time_signatures import (
    get_time_signature_config, is_beat_valid, calculate_char_position,
    generate_beat_markers, create_beat_validation_error, create_time_signature_error,
    get_supported_time_signatures, get_content_width, calculate_total_width
)

# Import parts system
from tab_models import (
    TabRequest, SongPart, PartInstance,
    process_song_structure, convert_parts_to_legacy_format,
    validate_parts_system, analyze_song_structure
)

# Import all existing functions from core.py
from core import (
    validate_schema, validate_timing, validate_conflicts,
    validate_strum_patterns, validate_emphasis_markings,
    validate_measure_strum_patterns,
    generate_measure_group, place_measure_events,
    generate_all_display_layers, process_measure_for_display_layers,
    place_annotation_text, generate_palm_mute_notation,
    generate_dynamic_notation, process_strum_pattern,
    place_grace_note_on_tab, place_event_on_tab,
    place_event_on_tab, replace_chars_at_position,
    format_semitone_string, check_attempt_limit,
    validate_grace_note_timing, validate_grace_note_conflicts,
    validate_technique_rules, validate_technique_rules
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# ============================================================================
# Enhanced Validation Pipeline with Parts Support
# ============================================================================


# Add this new validation function:
def validate_instrument_events(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate all events for the specified instrument.
    
    Checks string numbers and fret values against instrument limits.
    """
    instrument_str = data.get("instrument", "guitar")
    
    try:
        config = get_instrument_config(instrument_str)
        logger.debug(f"Validating events for {config.name} ({config.strings} strings)")
    except ValueError as e:
        return {
            "isError": True,
            "errorType": "validation_error",
            "message": f"Invalid instrument: {instrument_str}",
            "suggestion": "Use 'guitar' or 'ukulele'"
        }
    
    measures = data.get("measures", [])
    
    for measure_idx, measure in enumerate(measures, 1):
        for event_idx, event in enumerate(measure.get("events", []), 1):
            # Validate string numbers
            string_num = event.get("string")
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
            if event.get("type") == "chord":
                for fret_info in event.get("frets", []):
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

def validate_tab_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """validation pipeline for legacy measures format."""
    attempt = data.get('attempt', 1)
    logger.debug(f"Running legacy validation for attempt {attempt}")
    
    # Stage 1: Schema validation
    schema_result = validate_schema(data)
    if schema_result["isError"]:
        return schema_result
    
    # Stage 2: Timing validation
    timing_result = validate_timing(data)
    if timing_result["isError"]:
        return timing_result
    
    # Stage 3: Conflict validation
    conflict_result = validate_conflicts(data)
    if conflict_result["isError"]:
        return conflict_result
    
    # Stage 4: Strum pattern validation
    strum_result = validate_strum_patterns(data)
    if strum_result["isError"]:
        return strum_result
    
    # Stage 5: Emphasis validation
    emphasis_result = validate_emphasis_markings(data)
    if emphasis_result["isError"]:
        return emphasis_result
    
    # Stage 6: Measure strum pattern validation
    measures = data.get("measures", [])
    time_sig = data.get("timeSignature", "4/4")
    measure_strum_result = validate_measure_strum_patterns(measures, time_sig)
    if measure_strum_result["isError"]:
        logger.warning(f"Measure strum pattern validation failed: {measure_strum_result['message']}")
        return measure_strum_result
    
    # Stage 7: NEW - Instrument validation
    instrument_result = validate_instrument_events(data)
    if instrument_result["isError"]:
        logger.warning(f"Instrument validation failed: {instrument_result['message']}")
        return instrument_result
    
    logger.info("All validation stages passed")
    return {"isError": False}


# ============================================================================
# Enhanced Tab Generation with Parts Support
# ============================================================================

def generate_tab_output_with_parts(data: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    """Enhanced tab generation supporting both legacy and parts format."""
    title = data.get("title", "Untitled")
    logger.info(f"Generating tab with parts support for '{title}'")
    
    try:
        request = TabRequest(**data)
        
        if request.parts and request.structure:
            logger.info("Using parts format")
            return generate_tab_with_parts_format(request)
        else:
            logger.info("Using legacy format")
            legacy_data = convert_parts_to_legacy_format(request)
            return generate_tab_output_legacy(legacy_data)
            
    except Exception as e:
        logger.warning(f"Parts parsing failed, using legacy: {e}")
        return generate_tab_output_legacy(data)

def generate_tab_with_parts_format(request: TabRequest) -> Tuple[str, List[Dict[str, Any]]]:
    """Generate tab using parts format with section headers."""
    logger.info(f"Generating parts-based tab for '{request.title}'")
    
    warnings = []
    output_lines = []
    
    # Generate header
    header_lines = generate_header_with_parts(request)
    output_lines.extend(header_lines)
    output_lines.append("")
    
    # Process song structure
    try:
        instances = process_song_structure(request)
        logger.info(f"Generated {len(instances)} part instances")
    except Exception as e:
        logger.error(f"Failed to process song structure: {e}")
        return f"Error processing song structure: {e}", [{"error": str(e)}]
    
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
                "measures": measure_group
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

def generate_tab_output_legacy(data: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    """Original tab generation for legacy measures format."""
    title = data.get("title", "Untitled")
    logger.info(f"Generating legacy tab for '{title}'")
    
    measures = data["measures"]
    warnings = []
    output_lines = []
    
    # Generate header
    header_lines = generate_header_legacy(data)
    output_lines.extend(header_lines)
    output_lines.append("")
    
    # Process measures in groups of 4
    for measure_group_start in range(0, len(measures), 4):
        measure_group = measures[measure_group_start:measure_group_start + 4]
        time_sig = data.get("timeSignature", "4/4")
        
        # Generate measure group
        tab_section, section_warnings = generate_measure_group(
            measure_group, measure_group_start, time_sig, data
        )
        warnings.extend(section_warnings)
        output_lines.extend(tab_section)
        output_lines.append("")
    
    logger.info(f"Generated legacy tab with {len(warnings)} warnings")
    return "\n".join(output_lines), warnings

# ============================================================================
# Header Generation Functions
# ============================================================================

def generate_header_with_parts(request: TabRequest) -> List[str]:
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

def generate_header_legacy(data: Dict[str, Any]) -> List[str]:
    """Generate header for legacy format songs."""
    lines = []
    
    title = data.get("title", "Untitled")
    description = data.get("description", "")
    artist = data.get("artist", "")
    
    lines.append(f"# {title}")
    if artist:
        lines.append(f"**Artist:** {artist}")
    if description:
        lines.append(f"*{description}*")
    
    # Musical information
    info_parts = [f"**Time Signature:** {data.get('timeSignature', '4/4')}"]
    if data.get("tempo"):
        info_parts.append(f"**Tempo:** {data['tempo']} BPM")
    if data.get("key"):
        info_parts.append(f"**Key:** {data['key']}")
    if data.get("capo"):
        info_parts.append(f"**Capo:** {data['capo']}")
    
    lines.append(" | ".join(info_parts))
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

# ============================================================================
# Metadata Generation
# ============================================================================

def create_tab_metadata_with_parts(data_dict: Dict[str, Any], warnings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create metadata for parts-based tabs."""
    try:
        request = TabRequest(**data_dict)
        
        if request.parts and request.structure:
            return create_parts_metadata(request, warnings)
        else:
            return create_legacy_metadata(data_dict, warnings)
            
    except Exception as e:
        logger.warning(f"Error creating metadata: {e}")
        return create_legacy_metadata(data_dict, warnings)

def create_parts_metadata(request: TabRequest, warnings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create metadata for parts-based songs."""
    structure_analysis = analyze_song_structure(request)
    
    # Analyze features
    features_used = set()
    complexity_score = 0
    
    for part_name, part_def in request.parts.items():
        for measure in part_def.measures:
            for event in measure.get("events", []):
                event_type = event.get("type")
                features_used.add(event_type)
                
                if event_type == "strumPattern":
                    complexity_score += 1
                elif event.get("emphasis"):
                    complexity_score += 1
                elif event_type == "graceNote":
                    complexity_score += 2
                elif event_type in ["bend", "slide", "hammerOn", "pullOff"]:
                    complexity_score += 1
    
    if structure_analysis["total_parts_defined"] > 4:
        complexity_score += 1
    
    complexity = "advanced" if complexity_score >= 5 else "intermediate" if complexity_score >= 3 else "beginner"
    
    return {
        "format": "parts",
        "totalMeasures": structure_analysis["total_measures"],
        "totalParts": structure_analysis["total_parts_defined"],
        "totalPartInstances": structure_analysis["total_part_instances"],
        "complexity": complexity,
        "warningCount": len(warnings),
        "songStructure": structure_analysis,
        "featuresUsed": list(features_used)
    }

def create_legacy_metadata(data_dict: Dict[str, Any], warnings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create metadata for legacy format songs."""
    measures = data_dict.get("measures", [])
    
    return {
        "format": "legacy",
        "totalMeasures": len(measures),
        "warningCount": len(warnings),
        "complexity": "intermediate"  # Default
    }

# ============================================================================
# Backwards Compatibility Wrappers
# ============================================================================


def generate_tab_output(data: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    """Main tab generation entry point with parts support."""
    return generate_tab_output_with_parts(data)

def create_tab_metadata(data_dict: Dict[str, Any], warnings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Main metadata creation entry point with parts support."""
    return create_tab_metadata_with_parts(data_dict, warnings)

def check_attempt_limit(attempt: int) -> Optional[Dict[str, Any]]:
    """Enhanced attempt limit checking with parts-specific guidance."""
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

logger.info("Core module with parts system loaded successfully")
