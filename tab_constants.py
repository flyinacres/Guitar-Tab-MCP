#!/usr/bin/env python3
"""
Guitar Tab Generator -  Constants and Definitions
========================================================

Constants and enums for  guitar tab features including
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
class Instrument(Enum):
    """Supported string instruments."""
    GUITAR = "guitar"
    UKULELE = "ukulele"
    BASS = "bass"         
    MANDOLIN = "mandolin"  
    BANJO = "banjo"  
    SEVEN_STRING = "seven string"      

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
        name="guitar",
        strings=6,
        tuning=["E", "A", "D", "G", "B", "E"]
    ),
    Instrument.UKULELE: InstrumentConfig(
        name="ukulele",
        strings=4, 
        tuning=["G", "C", "E", "A"]
    ),
        Instrument.BASS: InstrumentConfig(
        name="bass",
        strings=4,
        tuning=["E", "A", "D", "G"]  # Standard bass tuning
    ),
    Instrument.MANDOLIN: InstrumentConfig(
        name="mandolin", 
        strings=4,  # 4 courses, but 8 strings  Strings are what we specify in tabs
        tuning=["G", "D", "A", "E"]
    ),
    Instrument.BANJO: InstrumentConfig(
        name="banjo",
        strings=5,
        tuning=["D", "G", "B", "D", "g"]  # Open G tuning
    ),
    Instrument.SEVEN_STRING: InstrumentConfig(
        name="seven string",
        strings=7,
        tuning=["B", "E", "A", "D", "G", "b", "e"]
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
#  Event Type Constants
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
# Validation Constants
# ============================================================================

# Maximum values for validation
MAX_FRET = 24
MAX_STRING = 12
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


def is_valid_emphasis(emphasis: str) -> bool:
    """Check if an emphasis marking is valid."""
    return emphasis in VALID_EMPHASIS_VALUES
