#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Time Signature Support Module
============================

Handles all time signature definitions, validation, and calculations for the
guitar tab generator. This module provides a clean abstraction for working
with different time signatures while keeping the core tab generation logic
focused on rendering.

Supported Time Signatures:
- 4/4 (Common time)
- 3/4 (Waltz time) 
- 6/8 (Compound duple)
- 2/4 (Cut time variation)

Design Philosophy:
- Each time signature defines its own beat patterns and character positioning
- Beat validation is strict to ensure musical accuracy
- Character positioning accounts for different measure widths
- Easy to extend with new time signatures
"""

from typing import Dict, List, Any, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# Time Signature Definitions
# ============================================================================

TIME_SIGNATURE_CONFIGS = {
    "4/4": {
        "name": "Common Time",
        "beats_per_measure": 4,
        "beat_subdivisions": 2,  # Each beat divided into 2 (quarter and eighth)
        "valid_beats": [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5],
        "beat_markers": " 1 & 2 & 3 & 4 &  ",
        "char_positions": {
            1.0: 2, 1.5: 4, 2.0: 6, 2.5: 8,
            3.0: 10, 3.5: 12, 4.0: 14, 4.5: 16
        },
        "measure_width": 18,  # Total characters including separator
        "content_width": 17,  # Dashes between separators
        "strum_positions": 8
    },
    
    "4/4 - 16ths": {
        "name": "Common Time - 16ths",
        "beats_per_measure": 4,
        "beat_subdivisions": 4,  # Changed from 2 to 4
        "valid_beats": [1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.25, 3.5, 3.75, 4.0, 4.25, 4.5, 4.75],
        "beat_markers": " 1 e & a 2 e & a 3 e & a 4 e & a  ",
        "char_positions": {
            1.0: 2, 1.25: 4, 1.5: 6, 1.75: 8,
            2.0: 10, 2.25: 12, 2.5: 14, 2.75: 16,
            3.0: 18, 3.25: 20, 3.5: 22, 3.75: 24,
            4.0: 26, 4.25: 28, 4.5: 30, 4.75: 32
        },
        "measure_width": 34,  # Doubled width
        "content_width": 33,  # Doubled width
        "strum_positions": 16
    },
    
    "3/4": {
        "name": "Waltz Time", 
        "beats_per_measure": 3,
        "beat_subdivisions": 2,
        "valid_beats": [1.0, 1.5, 2.0, 2.5, 3.0, 3.5],
        "beat_markers": " 1 & 2 & 3 &  ",
        "char_positions": {
            1.0: 2, 1.5: 4, 2.0: 6, 2.5: 8, 3.0: 10, 3.5: 12
        },
        "measure_width": 14,
        "content_width": 13,
        "strum_positions": 6
    },
    
    "6/8": {
        "name": "Compound Duple",
        "beats_per_measure": 2,  # Two main beats, each subdivided into 3
        "beat_subdivisions": 3,  # Triplet subdivision
        "valid_beats": [1.0, 1.33, 1.67, 2.0, 2.33, 2.67],
        "beat_markers": " 1 & a 2 & a  ",
        "char_positions": {
            1.0: 2, 1.33: 4, 1.67: 6, 2.0: 8, 2.33: 10, 2.67: 12
        },
        "measure_width": 14,
        "content_width": 13,
        "strum_positions": 6 
    },
    
    "2/4": {
        "name": "Cut Time",
        "beats_per_measure": 2,
        "beat_subdivisions": 2,
        "valid_beats": [1.0, 1.5, 2.0, 2.5],
        "beat_markers": " 1 & 2 &  ",
        "char_positions": {
            1.0: 2, 1.5: 4, 2.0: 6, 2.5: 8
        },
        "measure_width": 10,
        "content_width": 9,
        "strum_positions": 4
    }
}


STRUM_POSITIONS_PER_MEASURE = {
    "4/4": 8,  # 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5
    "4/4 - 16ths": 16, # 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.25, 3.5, 3.75, 4.0, 4.25, 4.5, 4.75
    "3/4": 6,  # 1.0, 1.5, 2.0, 2.5, 3.0, 3.5
    "2/4": 4,  # 1.0, 1.5, 2.0, 2.5
    "6/8": 6,  # 1.0, 1.33, 1.67, 2.0, 2.33, 2.67 (compound time)
}

# ============================================================================
# Core Time Signature Functions
# ============================================================================

def get_supported_time_signatures() -> List[str]:
    """Return list of all supported time signatures."""
    return list(TIME_SIGNATURE_CONFIGS.keys())

def get_time_signature_config(time_signature: str) -> Dict[str, Any]:
    """
    Get complete configuration for a specific time signature.
    
    Args:
        time_signature: String like "4/4", "3/4", "6/8"
        
    Returns:
        Configuration dictionary with all time signature parameters
        
    Raises:
        ValueError: If time signature is not supported
        
    Example:
        config = get_time_signature_config("3/4")
        print(config["name"])  # "Waltz Time"
        print(config["valid_beats"])  # [1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
    """
    if time_signature not in TIME_SIGNATURE_CONFIGS:
        supported = ", ".join(get_supported_time_signatures())
        raise ValueError(f"Unsupported time signature: {time_signature}. Supported: {supported}")
    
    return TIME_SIGNATURE_CONFIGS[time_signature].copy()

def is_time_signature_supported(time_signature: str) -> bool:
    """Check if a time signature is supported."""
    return time_signature in TIME_SIGNATURE_CONFIGS

# ============================================================================
# Beat Validation Functions
# ============================================================================

def get_valid_beats(time_signature: str) -> List[float]:
    """Get list of valid beat positions for a time signature."""
    config = get_time_signature_config(time_signature)
    return config["valid_beats"].copy()

def is_beat_valid(beat: float, time_signature: str) -> bool:
    """
    Check if a beat value is valid for the given time signature.
    
    Args:
        beat: Beat position (e.g., 1.0, 1.5, 2.0)
        time_signature: Time signature string (e.g., "4/4")
        
    Returns:
        True if beat is valid, False otherwise
        
    Example:
        is_beat_valid(1.5, "4/4")  # True
        is_beat_valid(4.7, "4/4")  # False  
        is_beat_valid(3.5, "3/4")  # True
        is_beat_valid(4.0, "3/4")  # False
    """
    try:
        valid_beats = get_valid_beats(time_signature)
        return beat in valid_beats
    except ValueError:
        return False

def get_closest_valid_beat(beat: float, time_signature: str) -> float:
    """
    Find the closest valid beat for a given time signature.
    
    Useful for error correction or approximating invalid beat values.
    
    Args:
        beat: Target beat position
        time_signature: Time signature string
        
    Returns:
        Closest valid beat position
        
    Example:
        get_closest_valid_beat(1.7, "4/4")  # Returns 1.5
        get_closest_valid_beat(4.9, "4/4")  # Returns 4.5
    """
    valid_beats = get_valid_beats(time_signature)
    return min(valid_beats, key=lambda x: abs(x - beat))

# ============================================================================
# Character Position Calculations
# ============================================================================

def calculate_char_position(beat: float, measure_offset: int, time_signature: str) -> int:
    """
    Calculate character position for a beat in any time signature.
    
    This is the core function that maps musical time to visual position
    in the UTF-8 tablature format.
    
    Args:
        beat: Beat position within the measure (e.g., 1.0, 1.5)
        measure_offset: Which measure in the group (0-3)
        time_signature: Time signature string (e.g., "4/4")
        
    Returns:
        Character position in the tab line
        
    Example:
        # In 4/4 time, measure 0, beat 1.0 → position 2
        calculate_char_position(1.0, 0, "4/4")  # Returns 2
        
        # In 4/4 time, measure 1, beat 1.0 → position 20 (2 + 18)
        calculate_char_position(1.0, 1, "4/4")  # Returns 20
        
        # In 3/4 time, measure 1, beat 1.0 → position 16 (2 + 14)  
        calculate_char_position(1.0, 1, "3/4")  # Returns 16
    """
    config = get_time_signature_config(time_signature)
    
    # Get base position for this beat
    if beat in config["char_positions"]:
        base_position = config["char_positions"][beat]
    else:
        # Fallback: use closest valid beat
        logger.warning(f"Beat {beat} not valid for {time_signature}, using closest valid beat")
        closest_beat = get_closest_valid_beat(beat, time_signature)
        base_position = config["char_positions"][closest_beat]
    
    # Add offset for measure position. +1 for the string note name
    return 1 + base_position + (measure_offset * config["measure_width"])

# ============================================================================
# Beat Marker Generation
# ============================================================================

def generate_beat_markers(time_signature: str, num_measures: int) -> str:
    """
    Generate beat marker line for any time signature.
    
    Creates the rhythm counting line that appears above the tablature,
    showing where beats fall within each measure.
    
    Args:
        time_signature: Time signature string
        num_measures: Number of measures to generate markers for
        
    Returns:
        Complete beat marker line with leading space for alignment
        
    Example:
        generate_beat_markers("4/4", 2)
        # Returns: " 1 & 2 & 3 & 4 &   1 & 2 & 3 & 4 & "
        
        generate_beat_markers("3/4", 2)  
        # Returns: " 1 & 2 & 3 &   1 & 2 & 3 & "
        
        generate_beat_markers("6/8", 2)
        # Returns: " 1 & a 2 & a   1 & a 2 & a "
    """
    config = get_time_signature_config(time_signature)
    beat_pattern = config["beat_markers"] 
    
    # Repeat the pattern for each measure
    full_line = beat_pattern * num_measures
    # Add a space in front to account for the string name
    return " " + full_line 

# ============================================================================
# Measure Width Calculations
# ============================================================================

def get_measure_width(time_signature: str) -> int:
    """Get total character width for one measure including separator."""
    config = get_time_signature_config(time_signature)
    return config["measure_width"]

def get_content_width(time_signature: str) -> int:
    """Get content character width for one measure (excluding separators)."""
    config = get_time_signature_config(time_signature)
    return config["content_width"]

def calculate_total_width(time_signature: str, num_measures: int) -> int:
    """Calculate total character width for multiple measures."""
    measure_width = get_measure_width(time_signature)
    return 1 + (num_measures * measure_width)  # +1 for leading space and string name

# ============================================================================
# Advanced Time Signature Analysis
# ============================================================================

def analyze_time_signature(time_signature: str) -> Dict[str, Any]:
    """
    Provide detailed analysis of a time signature's characteristics.
    
    Useful for debugging, documentation, or advanced musical features.
    
    Args:
        time_signature: Time signature string
        
    Returns:
        Dictionary with detailed time signature analysis
    """
    config = get_time_signature_config(time_signature)
    
    # Calculate some derived properties
    total_beats = len(config["valid_beats"])
    beat_density = total_beats / config["beats_per_measure"]
    
    analysis = {
        "time_signature": time_signature,
        "name": config["name"],
        "classification": _classify_time_signature(time_signature),
        "beats_per_measure": config["beats_per_measure"],
        "subdivisions": config["beat_subdivisions"],
        "total_valid_positions": total_beats,
        "beat_density": round(beat_density, 2),
        "measure_width": config["measure_width"],
        "shortest_note_value": _get_shortest_note_value(config),
        "compound_time": config["beat_subdivisions"] > 2
    }
    
    return analysis

def _classify_time_signature(time_signature: str) -> str:
    """Classify time signature by musical characteristics."""
    classifications = {
        "4/4": "Simple quadruple",
        "3/4": "Simple triple", 
        "2/4": "Simple duple",
        "6/8": "Compound duple"
    }
    return classifications.get(time_signature, "Unknown")

def _get_shortest_note_value(config: Dict[str, Any]) -> str:
    """Determine the shortest note value representable."""
    if config["beat_subdivisions"] == 2:
        return "Eighth note"
    elif config["beat_subdivisions"] == 3:
        return "Eighth note triplet"
    else:
        return "Subdivision"

# ============================================================================
# Validation Helpers
# ============================================================================

def create_beat_validation_error(beat: float, time_signature: str, measure: int) -> Dict[str, Any]:
    """
    Create a standardized validation error for invalid beats.
    
    This ensures consistent error messages across the application.
    """
    valid_beats = get_valid_beats(time_signature)
    
    return {
        "isError": True,
        "errorType": "validation_error",
        "measure": measure,
        "beat": beat,
        "message": f"Beat {beat} invalid for {time_signature} time signature",
        "suggestion": f"Use valid beat values: {', '.join(map(str, valid_beats))}"
    }

def create_time_signature_error(time_signature: str) -> Dict[str, Any]:
    """Create a standardized error for unsupported time signatures."""
    supported = ", ".join(get_supported_time_signatures())
    
    return {
        "isError": True,
        "errorType": "validation_error", 
        "message": f"Unsupported time signature: {time_signature}",
        "suggestion": f"Use supported time signatures: {supported}"
    }

# ============================================================================
# Module Information
# ============================================================================

def get_module_info() -> Dict[str, Any]:
    """Get information about this time signature module."""
    return {
        "module": "time_signatures",
        "version": "1.0.0",
        "supported_time_signatures": get_supported_time_signatures(),
        "total_configurations": len(TIME_SIGNATURE_CONFIGS),
        "features": [
            "Beat validation",
            "Character position calculation", 
            "Beat marker generation",
            "Measure width calculation",
            "Time signature analysis"
        ]
    }


# ============================================================================
# Utility Functions
# ============================================================================

def get_strum_positions_for_time_signature(time_signature: str) -> int:
    """Get number of strum positions per measure for a time signature."""
    return STRUM_POSITIONS_PER_MEASURE.get(time_signature, 8)


