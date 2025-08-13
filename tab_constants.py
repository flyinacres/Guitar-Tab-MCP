#!/usr/bin/env python3
"""
Guitar Tab Generator - Enhanced Constants and Definitions
========================================================

Constants and enums for enhanced guitar tab features including
strum patterns, dynamics, and emphasis markings.
"""

from enum import Enum
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# ============================================================================
# Strum Direction Constants
# ============================================================================

class StrumDirection(Enum):
    """Strum direction indicators for guitar tablature."""
    DOWN = "D"
    UP = "U"
    NONE = ""  # No strum indicator
    
    def __str__(self):
        return self.value

# Strum pattern validation - positions per measure by time signature
STRUM_POSITIONS_PER_MEASURE = {
    "4/4": 8,  # 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5
    "3/4": 6,  # 1.0, 1.5, 2.0, 2.5, 3.0, 3.5
    "2/4": 4,  # 1.0, 1.5, 2.0, 2.5
    "6/8": 6,  # 1.0, 1.33, 1.67, 2.0, 2.33, 2.67 (compound time)
}

class Instrument(Enum):
    """Supported string instruments."""
    GUITAR = "guitar"
    UKULELE = "ukulele"

class InstrumentConfig:
    """Configuration for string instruments."""
    
    def __init__(self, name: str, strings: int, tuning: List[str], max_fret: int = 24):
        self.name = name
        self.strings = strings
        self.tuning = tuning
        self.max_fret = max_fret
    
    def validate_string(self, string_num: int) -> bool:
        return 1 <= string_num <= self.strings

# Instrument configurations
INSTRUMENT_CONFIGS = {
    Instrument.GUITAR: InstrumentConfig(
        name="Guitar",
        strings=6,
        tuning=["E", "A", "D", "G", "B", "E"]
    ),
    Instrument.UKULELE: InstrumentConfig(
        name="Ukulele",
        strings=4, 
        tuning=["G", "C", "E", "A"]
    )
}

def get_instrument_config(instrument_str: str) -> InstrumentConfig:
    """Get configuration for instrument string."""
    instrument = Instrument(instrument_str)
    return INSTRUMENT_CONFIGS[instrument]

# Update existing constants to be instrument-aware
def get_max_string(instrument_str: str = "guitar") -> int:
    """Get maximum string number for instrument."""
    config = get_instrument_config(instrument_str)
    return config.strings

# ============================================================================
# Dynamic and Emphasis Constants
# ============================================================================

class DynamicLevel(Enum):
    """Standard musical dynamics from softest to loudest."""
    PIANISSIMO = "pp"      # Very soft
    PIANO = "p"            # Soft
    MEZZO_PIANO = "mp"     # Moderately soft
    MEZZO_FORTE = "mf"     # Moderately loud
    FORTE = "f"            # Loud
    FORTISSIMO = "ff"      # Very loud
    
    def __str__(self):
        return self.value

class ArticulationMark(Enum):
    """Articulation and emphasis markings."""
    ACCENT = ">"           # Strong emphasis
    TENUTO = "-"           # Hold full value
    STACCATO = "."         # Short, detached
    CRESCENDO = "<"        # Gradually louder
    DECRESCENDO = ">"      # Gradually softer (context-dependent)
    
    def __str__(self):
        return self.value

# Valid emphasis values (combination of dynamics and articulations)
VALID_EMPHASIS_VALUES = (
    [e.value for e in DynamicLevel] + 
    [e.value for e in ArticulationMark] +
    ["dim.", "cresc."]  # Additional text-based markings
)

# ============================================================================
# Enhanced Event Type Constants
# ============================================================================

class EventType(Enum):
    """All supported event types in guitar tablature."""
    # Musical events
    NOTE = "note"
    CHORD = "chord"
    
    # Techniques
    HAMMER_ON = "hammerOn"
    PULL_OFF = "pullOff"
    SLIDE = "slide"
    BEND = "bend"
    
    # Annotations
    PALM_MUTE = "palmMute"
    CHUCK = "chuck"
    
    # New enhancements
    STRUM_PATTERN = "strumPattern"
    EMPHASIS = "emphasis"  # Standalone emphasis event
    GRACE_NOTE = "graceNote"
    
    def __str__(self):
        return self.value

# ============================================================================
# Time Signature Enhancement Constants
# ============================================================================

@dataclass
class TimeSignatureInfo:
    """Enhanced time signature information including strum pattern support."""
    name: str
    beats_per_measure: int
    beat_subdivisions: int
    valid_beats: List[float]
    beat_markers: str
    char_positions: Dict[float, int]
    measure_width: int
    content_width: int
    strum_positions: int
    is_compound: bool = False  # True for 6/8, 9/8, 12/8, etc.
    swing_feel: bool = False   # True for compound times

# Enhanced time signature configurations
ENHANCED_TIME_SIGNATURE_CONFIGS = {
    "4/4": TimeSignatureInfo(
        name="Common Time",
        beats_per_measure=4,
        beat_subdivisions=2,
        valid_beats=[1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5],
        beat_markers=" 1 & 2 & 3 & 4 & ",
        char_positions={
            1.0: 2, 1.5: 4, 2.0: 6, 2.5: 8,
            3.0: 10, 3.5: 12, 4.0: 14, 4.5: 16
        },
        measure_width=18,
        content_width=17,
        strum_positions=8
    ),
    
    "3/4": TimeSignatureInfo(
        name="Waltz Time",
        beats_per_measure=3,
        beat_subdivisions=2,
        valid_beats=[1.0, 1.5, 2.0, 2.5, 3.0, 3.5],
        beat_markers=" 1 & 2 & 3 & ",
        char_positions={
            1.0: 2, 1.5: 4, 2.0: 6, 2.5: 8, 3.0: 10, 3.5: 12
        },
        measure_width=14,
        content_width=13,
        strum_positions=6
    ),
    
    "2/4": TimeSignatureInfo(
        name="Cut Time",
        beats_per_measure=2,
        beat_subdivisions=2,
        valid_beats=[1.0, 1.5, 2.0, 2.5],
        beat_markers=" 1 & 2 & ",
        char_positions={
            1.0: 2, 1.5: 4, 2.0: 6, 2.5: 8
        },
        measure_width=9,
        content_width=8,
        strum_positions=4
    ),
    
    "6/8": TimeSignatureInfo(
        name="Compound Duple",
        beats_per_measure=2,
        beat_subdivisions=3,
        valid_beats=[1.0, 1.33, 1.67, 2.0, 2.33, 2.67],
        beat_markers=" 1 & a 2 & a ",
        char_positions={
            1.0: 2, 1.33: 4, 1.67: 6, 2.0: 8, 2.33: 10, 2.67: 12
        },
        measure_width=13,
        content_width=12,
        strum_positions=6,
        is_compound=True,
        swing_feel=True
    )
}

# ============================================================================
# Validation Constants
# ============================================================================

# Maximum values for validation
MAX_FRET = 24
MAX_STRING = 6
MIN_STRING = 1
MAX_SEMITONES = 3.0
MIN_SEMITONES = 0.25

# Strum pattern constraints
MAX_STRUM_PATTERN_MEASURES = 8  # Maximum measures a strum pattern can span
MIN_STRUM_PATTERN_MEASURES = 1  # Minimum measures (must be complete)

# Emphasis constraints
MAX_EMPHASIS_LENGTH = 10  # Maximum characters for emphasis marking

# ============================================================================
# Display Constants
# ============================================================================

class DisplayLayer(Enum):
    """Different layers of information displayed in tabs."""
    CHORD_NAMES = "chord_names"
    ANNOTATIONS = "annotations"  # PM, X, emphasis
    BEAT_MARKERS = "beat_markers"
    TAB_CONTENT = "tab_content"
    STRUM_PATTERN = "strum_pattern"
    DYNAMICS = "dynamics"
    
    def __str__(self):
        return self.value

# Display layer ordering (top to bottom)
DISPLAY_LAYER_ORDER = [
    DisplayLayer.CHORD_NAMES,
    DisplayLayer.DYNAMICS,
    DisplayLayer.ANNOTATIONS,
    DisplayLayer.BEAT_MARKERS,
    DisplayLayer.TAB_CONTENT,
]

# ============================================================================
# Error Message Constants
# ============================================================================

ERROR_MESSAGES = {
    "invalid_strum_pattern_length": "Strum pattern length ({length}) doesn't match time signature {time_sig} (expected {expected})",
    "invalid_emphasis_value": "Invalid emphasis value '{value}'. Use: {valid_values}",
    "strum_pattern_measure_mismatch": "Strum pattern spans {actual} measures but should span whole measures only",
    "grace_note_invalid_timing": "Grace note cannot be placed at beat {beat} - too close to measure boundary",
    "compound_time_beat_error": "Beat {beat} invalid for compound time {time_sig} - use triplet subdivisions",
}

# ============================================================================
# Utility Functions
# ============================================================================

def get_strum_positions_for_time_signature(time_signature: str) -> int:
    """Get number of strum positions per measure for a time signature."""
    return STRUM_POSITIONS_PER_MEASURE.get(time_signature, 8)

def is_valid_emphasis(emphasis: str) -> bool:
    """Check if an emphasis marking is valid."""
    return emphasis in VALID_EMPHASIS_VALUES

def is_compound_time(time_signature: str) -> bool:
    """Check if a time signature uses compound (triplet-based) subdivision."""
    config = ENHANCED_TIME_SIGNATURE_CONFIGS.get(time_signature)
    return config.is_compound if config else False

def get_beat_positions_for_strum_pattern(time_signature: str) -> List[float]:
    """Get the beat positions that correspond to strum pattern indices."""
    config = ENHANCED_TIME_SIGNATURE_CONFIGS.get(time_signature)
    if not config:
        return []
    return config.valid_beats
