#!/usr/bin/env python3
"""
Pydantic V2 Compatible Data Models for Guitar Tab Generator
==========================================================

Updated Pydantic models compatible with V2 syntax using:
- @field_validator instead of @validator
- Literal instead of const
- Updated Field syntax and validation patterns
"""

from typing import Dict, List, Any, Optional, Union, Literal
from pydantic import BaseModel, Field, field_validator
from enum import Enum

# Import our constants
from tab_constants import (
    StrumDirection, DynamicLevel, ArticulationMark,
    VALID_EMPHASIS_VALUES, MAX_FRET, MAX_STRING, MIN_STRING,
    MAX_SEMITONES, MIN_SEMITONES, get_strum_positions_for_time_signature
)

# ============================================================================
# Base Event Models
# ============================================================================

class BaseEvent(BaseModel):
    """Base class for all guitar tab events with common properties."""
    type: str
    emphasis: Optional[str] = Field(None, description="Dynamic or articulation marking")
    
    @field_validator('emphasis')
    @classmethod
    def validate_emphasis(cls, v):
        if v is not None and v not in VALID_EMPHASIS_VALUES:
            raise ValueError(f"Invalid emphasis '{v}'. Valid values: {VALID_EMPHASIS_VALUES}")
        return v

class MusicalEvent(BaseEvent):
    """Base class for events that occur at specific beats."""
    beat: Optional[float] = None
    startBeat: Optional[float] = None  # For techniques that span time
    
    @field_validator('beat', 'startBeat')
    @classmethod
    def validate_beat_positive(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Beat values must be positive")
        return v

# ============================================================================
# Enhanced Musical Events
# ============================================================================

class EnhancedNote(MusicalEvent):
    """Enhanced note event with dynamics and articulation."""
    type: Literal["note"] = "note"
    string: int = Field(..., ge=MIN_STRING, le=MAX_STRING)
    beat: float
    fret: Union[int, str]  # int for fret number, "x" for muted
    vibrato: bool = False
    
    @field_validator('fret')
    @classmethod
    def validate_fret(cls, v):
        if isinstance(v, str):
            if v.lower() not in ['x']:
                raise ValueError("String fret values must be 'x' for muted strings")
        elif isinstance(v, (int, float)):
            if v < 0 or v > MAX_FRET:
                raise ValueError(f"Fret must be 0-{MAX_FRET} or 'x' for muted")
        return v

class EnhancedChord(MusicalEvent):
    """Enhanced chord event with dynamics and emphasis."""
    type: Literal["chord"] = "chord"
    beat: float
    chordName: Optional[str] = None
    frets: List[Dict[str, Union[int, str]]]  # [{"string": 1, "fret": 3}, ...]
    
    @field_validator('frets')
    @classmethod
    def validate_frets(cls, v):
        if not v:
            raise ValueError("Chord must have at least one fret")
        
        strings_used = set()
        for fret_info in v:
            if 'string' not in fret_info or 'fret' not in fret_info:
                raise ValueError("Each fret must specify 'string' and 'fret'")
            
            string_num = fret_info['string']
            if string_num in strings_used:
                raise ValueError(f"Duplicate string {string_num} in chord")
            strings_used.add(string_num)
            
            if not (MIN_STRING <= string_num <= MAX_STRING):
                raise ValueError(f"String must be {MIN_STRING}-{MAX_STRING}")
        
        return v

# ============================================================================
# Technique Events
# ============================================================================

class EnhancedSlide(MusicalEvent):
    """Enhanced slide with emphasis support."""
    type: Literal["slide"] = "slide"
    string: int = Field(..., ge=MIN_STRING, le=MAX_STRING)
    startBeat: float
    fromFret: int = Field(..., ge=0, le=MAX_FRET)
    toFret: int = Field(..., ge=0, le=MAX_FRET)
    direction: Literal["up", "down"]
    vibrato: bool = False

class EnhancedBend(MusicalEvent):
    """Enhanced bend with emphasis and vibrato."""
    type: Literal["bend"] = "bend"
    string: int = Field(..., ge=MIN_STRING, le=MAX_STRING)
    beat: float
    fret: int = Field(..., ge=0, le=MAX_FRET)
    semitones: float = Field(..., ge=MIN_SEMITONES, le=MAX_SEMITONES)
    vibrato: bool = False

class EnhancedHammerOn(MusicalEvent):
    """Enhanced hammer-on with emphasis."""
    type: Literal["hammerOn"] = "hammerOn"
    string: int = Field(..., ge=MIN_STRING, le=MAX_STRING)
    startBeat: float
    fromFret: int = Field(..., ge=0, le=MAX_FRET)
    toFret: int = Field(..., ge=0, le=MAX_FRET)
    vibrato: bool = False
    
    @field_validator('toFret')
    @classmethod
    def validate_hammer_direction(cls, v, info):
        if 'fromFret' in info.data and v <= info.data['fromFret']:
            raise ValueError("Hammer-on toFret must be higher than fromFret")
        return v

class EnhancedPullOff(MusicalEvent):
    """Enhanced pull-off with emphasis."""
    type: Literal["pullOff"] = "pullOff"
    string: int = Field(..., ge=MIN_STRING, le=MAX_STRING)
    startBeat: float
    fromFret: int = Field(..., ge=0, le=MAX_FRET)
    toFret: int = Field(..., ge=0, le=MAX_FRET)
    vibrato: bool = False
    
    @field_validator('toFret')
    @classmethod
    def validate_pulloff_direction(cls, v, info):
        if 'fromFret' in info.data and v >= info.data['fromFret']:
            raise ValueError("Pull-off toFret must be lower than fromFret")
        return v

# ============================================================================
# New Event Types
# ============================================================================

class StrumPatternEvent(BaseEvent):
    """Strum pattern that can span multiple measures."""
    type: Literal["strumPattern"] = "strumPattern"
    startBeat: float = 1.0
    pattern: List[str]  # Array of strum directions: ["D", "U", "", "D", ...]
    measures: int = Field(default=1, ge=1, le=8)  # How many measures this pattern spans
    
    @field_validator('pattern')
    @classmethod
    def validate_pattern(cls, v):
        valid_values = ["D", "U", ""]
        for direction in v:
            if direction not in valid_values:
                raise ValueError(f"Invalid strum direction '{direction}'. Use 'D', 'U', or ''")
        return v

class GraceNoteEvent(MusicalEvent):
    """Grace note - small note played quickly before main note."""
    type: Literal["graceNote"] = "graceNote"
    string: int = Field(..., ge=MIN_STRING, le=MAX_STRING)
    beat: float  # Beat where the grace note leads into
    fret: Union[int, str]
    graceFret: Union[int, str]  # The grace note fret
    graceType: Literal["acciaccatura", "appoggiatura"] = "acciaccatura"

class DynamicEvent(BaseEvent):
    """Standalone dynamic marking that affects following notes/chords."""
    type: Literal["dynamic"] = "dynamic"
    beat: float
    dynamic: str = Field(..., description="Dynamic level (pp, p, mp, mf, f, ff)")
    duration: Optional[float] = None  # How long this dynamic lasts
    
    @field_validator('dynamic')
    @classmethod
    def validate_dynamic(cls, v):
        valid_dynamics = [d.value for d in DynamicLevel] + ["cresc.", "dim.", "<", ">"]
        if v not in valid_dynamics:
            raise ValueError(f"Invalid dynamic '{v}'. Valid: {valid_dynamics}")
        return v

# ============================================================================
# Enhanced Annotation Events
# ============================================================================

class EnhancedPalmMute(BaseEvent):
    """Enhanced palm mute with intensity levels."""
    type: Literal["palmMute"] = "palmMute"
    beat: float
    duration: float = Field(default=1.0, gt=0, le=8.0)
    intensity: Optional[Literal["light", "medium", "heavy"]] = None

class EnhancedChuck(BaseEvent):
    """Enhanced chuck with emphasis levels."""
    type: Literal["chuck"] = "chuck"
    beat: float
    intensity: Optional[Literal["light", "medium", "heavy"]] = None

# ============================================================================
# Tab Request Model
# ============================================================================

class EnhancedTabRequest(BaseModel):
    """Enhanced tab request with all new features."""
    title: str
    description: str = ""
    artist: Optional[str] = None
    timeSignature: Literal["4/4", "3/4", "6/8", "2/4"] = "4/4"
    tempo: Optional[int] = Field(None, ge=40, le=300)
    key: Optional[str] = None  # Musical key
    capo: Optional[int] = Field(None, ge=0, le=12)  # Capo position
    tuning: Optional[List[str]] = None  # Custom tuning
    attempt: int = Field(default=1, ge=1, le=10)
    measures: List[Dict[str, Any]]
    globalDynamic: Optional[str] = None  # Default dynamic level
    showStrumPattern: bool = Field(default=True)  # Whether to display strum pattern line
    showDynamics: bool = Field(default=True)  # Whether to display dynamics line

# ============================================================================
# Response Models
# ============================================================================

class EnhancedTabResponse(BaseModel):
    """Enhanced response with additional formatting information."""
    success: bool
    content: str = ""
    error: Optional[Dict[str, Any]] = None
    warnings: List[Dict[str, Any]] = []
    metadata: Optional[Dict[str, Any]] = None  # Additional info about the tab
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "content": "# Song Title\n...",
                "warnings": [
                    {
                        "warningType": "formatting_warning",
                        "measure": 1,
                        "beat": 2.0,
                        "message": "Complex strum pattern may require practice"
                    }
                ],
                "metadata": {
                    "totalMeasures": 4,
                    "hasStrumPattern": True,
                    "hasDynamics": True,
                    "complexity": "intermediate"
                }
            }
        }
    }
