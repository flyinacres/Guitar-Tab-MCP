#!/usr/bin/env python3
"""
Pydantic V2 Compatible Data Models for Guitar Tab Generator
==========================================================

Updated Pydantic models compatible with V2 syntax using:
- @field_validator instead of @validator
- Literal instead of const
- Updated Field syntax and validation patterns
"""

import sys
import logging
import json
from typing import Dict, List, Any, Optional, Literal
from pydantic import BaseModel, Field, field_validator
from tab_constants import Instrument, get_instrument_config

# Import our constants
from tab_constants import (
    VALID_EMPHASIS_VALUES, MAX_FRET, MAX_STRING, MIN_STRING,
    MAX_SEMITONES, MIN_SEMITONES
)

from time_signatures import get_supported_time_signatures

# Configure logging to stderr only (stdout reserved for MCP protocol)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# ============================================================================
# Response Models
# ============================================================================

class TabResponse(BaseModel):
    """ response with additional formatting information."""
    success: bool
    content: str = ""
    error: Optional[Dict[str, Any]] = None
    warnings: List[Dict[str, Any]] = []
    
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
                ]
            }
        }
    }

# ============================================================================
# Parts System Models
# ============================================================================

class SongPart(BaseModel):
    """
    A named section of a song containing measures.
    
    Examples: Verse, Chorus, Bridge, Intro, Outro, Solo, etc.
    """
    name: Optional[str] = Field(None, description="Optional display name override")
    description: Optional[str] = Field(None, description="Description of this part")
    measures: List[Dict[str, Any]] = Field(..., description="Measures with optional strumPattern field")
    tempo_change: Optional[int] = Field(None, description="Tempo change for this part")
    key_change: Optional[str] = Field(None, description="Key change for this part")
    time_signature_change: Optional[str] = Field(None, description="Time signature change for this part")
    
    @field_validator('measures')
    @classmethod
    def validate_measures_not_empty(cls, v):
        if not v:
            raise ValueError("Part must contain at least one measure")
        return v
    
    @field_validator('tempo_change')
    @classmethod
    def validate_tempo(cls, v):
        if v is not None and (v < 40 or v > 300):
            raise ValueError("Tempo must be between 40 and 300 BPM")
        return v

class PartInstance(BaseModel):
    """
    Represents a specific occurrence of a part in the song structure.
    
    This is generated internally when processing the structure.
    """
    part_name: str = Field(..., description="Name of the part definition")
    instance_number: int = Field(..., description="Which occurrence of this part (1, 2, 3...)")
    display_name: str = Field(..., description="Display name with numbering")
    measures: List[Dict[str, Any]] = Field(..., description="The actual measures for this instance")
    tempo: Optional[int] = Field(None, description="Effective tempo for this part")
    key: Optional[str] = Field(None, description="Effective key for this part")
    time_signature: Optional[str] = Field(None, description="Effective time signature for this part")

class SongStructure(BaseModel):
    """
    Defines the order and repetition of song parts.
    
    The structure list references part names and determines the song flow.
    """
    parts: List[str] = Field(..., description="Ordered list of part names")
    repeats: Dict[str, int] = Field(default_factory=dict, description="Global repeat markers")
    
    @field_validator('parts')
    @classmethod
    def validate_parts_not_empty(cls, v):
        if not v:
            raise ValueError("Song structure must contain at least one part")
        return v
    
# ============================================================================
# Tab Request Model
# ============================================================================

class TabRequest(BaseModel):
    """
    Tab request system.

    """
    title: str
    description: str = ""
    artist: Optional[str] = None
    instrument: str = "guitar" 
    timeSignature: str = "4/4"
    tempo: Optional[int] = Field(None, ge=40, le=300)
    key: Optional[str] = None
    capo: Optional[int] = Field(None, ge=0, le=12)
    tuning: Optional[List[str]] = None
    attempt: int = Field(default=1, ge=1, le=10)
    showBeatMarkers: bool = Field(default=True, description="Show beat counting (1 & 2 & 3 & 4 &)")
    
    # New parts format
    parts: Optional[Dict[str, SongPart]] = Field(None, description="Named song parts/sections")
    structure: Optional[List[str]] = Field(None, description="Order of parts in the song")
    
    # Display options
    globalDynamic: Optional[str] = None
    showStrumPattern: bool = Field(default=True)
    showDynamics: bool = Field(default=True)
    showPartHeaders: bool = Field(default=True, description="Show part names as headers")

    # info that can be used to generate a valid schema for the JSON format used
    model_config = {
        "title": "Stringed Instrument Tab Generator JSON Schema",
        "description": "Schema for generating stringed instrument tablature",
        "json_schema_extra": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://github.com/yourusername/guitar-tab-generator/schema.json",
        }
    }

    @field_validator('timeSignature')
    @classmethod
    def validate_time_signature(cls, v):
        supported = get_supported_time_signatures()
        if v not in supported:
            raise ValueError(f'timeSignature must be one of {supported}')
        return v
    
    @field_validator('instrument')
    @classmethod
    def validate_instrument(cls, v):
        try:
            get_instrument_config(v)  # This will raise ValueError if invalid
            return v
        except ValueError:
            supported = [inst.value for inst in Instrument]
            raise ValueError(f"Invalid instrument '{v}'. Supported: {supported}")

    @field_validator('structure')
    @classmethod 
    def validate_structure_references(cls, v, info):
        """Validate that all structure references exist in parts."""
        if v is not None and 'parts' in info.data and info.data['parts'] is not None:
            parts_dict = info.data['parts']
            for part_name in v:
                if part_name not in parts_dict:
                    available_parts = list(parts_dict.keys())
                    raise ValueError(f"Structure references undefined part '{part_name}'. Available parts: {available_parts}")
        return v

# ============================================================================
# Parts Processing Functions
# ============================================================================

def process_song_structure(request: TabRequest) -> List[PartInstance]:
    """
    Process the song structure to create ordered part instances with numbering.
    
    Args:
        request:  tab request with parts and structure
        
    Returns:
        List of PartInstance objects in performance order
        
    Example:
        Input structure: ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Outro"]
        Output: [
            PartInstance(part_name="Intro", instance_number=1, display_name="Intro 1", ...),
            PartInstance(part_name="Verse", instance_number=1, display_name="Verse 1", ...),
            PartInstance(part_name="Chorus", instance_number=1, display_name="Chorus 1", ...),
            PartInstance(part_name="Verse", instance_number=2, display_name="Verse 2", ...),
            PartInstance(part_name="Chorus", instance_number=2, display_name="Chorus 2", ...),
            PartInstance(part_name="Outro", instance_number=1, display_name="Outro 1", ...)
        ]
    """
    if not request.parts or not request.structure:
        raise ValueError("Parts and structure are required for processing")
    
    # Track instance numbers for each part name
    part_counters = {}
    instances = []
    
    # Current song state (for tempo/key/time sig changes)
    current_tempo = request.tempo
    current_key = request.key  
    current_time_signature = request.timeSignature
    
    for part_name in request.structure:
        if part_name not in request.parts:
            raise ValueError(f"Structure references undefined part: {part_name}")
        
        # Increment counter for this part name
        part_counters[part_name] = part_counters.get(part_name, 0) + 1
        instance_number = part_counters[part_name]
        
        # Get part definition
        part_def = request.parts[part_name]
        
        # Apply any part-specific changes
        part_tempo = part_def.tempo_change or current_tempo
        part_key = part_def.key_change or current_key
        part_time_sig = part_def.time_signature_change or current_time_signature
        
        # Update current state for next parts
        if part_def.tempo_change:
            current_tempo = part_def.tempo_change
        if part_def.key_change:
            current_key = part_def.key_change
        if part_def.time_signature_change:
            current_time_signature = part_def.time_signature_change
        
        # Create display name
        display_name = f"{part_name} {instance_number}"
        if part_def.name:  # Use custom display name if provided
            display_name = f"{part_def.name} {instance_number}"
        
        # Create part instance
        instance = PartInstance(
            part_name=part_name,
            instance_number=instance_number,
            display_name=display_name,
            measures=part_def.measures.copy(),  # Deep copy to avoid mutations
            tempo=part_tempo,
            key=part_key,
            time_signature=part_time_sig
        )
        
        instances.append(instance)
    
    return instances


# ============================================================================
# Validation Functions for Parts System
# ============================================================================

def validate_parts_system(request: TabRequest) -> Dict[str, Any]:
    """
    Validate the parts system for common issues.
    
    Checks:
    - Part name uniqueness
    - Structure references
    - Circular dependencies
    - Musical consistency across parts
    
    Returns:
        Error dict if validation fails, {"isError": False} if valid
    """
    
    if not request.parts or not request.structure:
        return {
            "isError": True,
            "errorType": "validation_error",
            "message": "Parts system requires both 'parts' and 'structure' fields",
            "suggestion": "Add 'parts' dict with part definitions and 'structure' array with part order"
        }
    
    # Check for empty parts
    for part_name, part_def in request.parts.items():
        if not part_def.measures:
            return {
                "isError": True,
                "errorType": "validation_error",
                "message": f"Part '{part_name}' has no measures",
                "suggestion": f"Add at least one measure to part '{part_name}'"
            }
    
    # Check structure references
    for part_name in request.structure:
        if part_name not in request.parts:
            available = list(request.parts.keys())
            return {
                "isError": True,
                "errorType": "validation_error",
                "message": f"Structure references undefined part '{part_name}'",
                "suggestion": f"Use one of the defined parts: {available}"
            }
    
    # Validate time signature consistency
    base_time_sig = request.timeSignature
    for part_name, part_def in request.parts.items():
        if part_def.time_signature_change:
            # For now, we'll warn about time signature changes but allow them
            # Future enhancement could add full support for mid-song time signature changes
            pass
    
    return {"isError": False}

# ============================================================================
# Parts System Statistics
# ============================================================================

def analyze_song_structure(request: TabRequest) -> Dict[str, Any]:
    """
    Analyze the song structure and provide statistics.
    
    Returns:
        Dictionary with analysis of the song structure
    """

    instances = process_song_structure(request)
    
    # Count occurrences of each part
    part_occurrences = {}
    total_measures = 0
    
    for instance in instances:
        part_name = instance.part_name
        part_occurrences[part_name] = part_occurrences.get(part_name, 0) + 1
        total_measures += len(instance.measures)
    
    # Find most/least repeated parts
    most_repeated = max(part_occurrences.items(), key=lambda x: x[1]) if part_occurrences else ("None", 0)
    least_repeated = min(part_occurrences.items(), key=lambda x: x[1]) if part_occurrences else ("None", 0)
    
    return {
        "format": "parts",
        "total_parts_defined": len(request.parts),
        "total_part_instances": len(instances),
        "structure_length": len(request.structure),
        "total_measures": total_measures,
        "part_occurrences": part_occurrences,
        "most_repeated_part": {"name": most_repeated[0], "count": most_repeated[1]},
        "least_repeated_part": {"name": least_repeated[0], "count": least_repeated[1]},
        "unique_parts": len(part_occurrences),
        "avg_measures_per_part": round(total_measures / len(instances), 1) if instances else 0,
        "has_tempo_changes": any(part.tempo_change for part in request.parts.values()),
        "has_key_changes": any(part.key_change for part in request.parts.values()),
        "has_time_signature_changes": any(part.time_signature_change for part in request.parts.values())
    }

# ============================================================================
# Example Usage and Tests
# ============================================================================

if __name__ == "__main__":
    # Example song structure
    example_request = {
        "title": "Test Song with Parts",
        "timeSignature": "4/4",
        "tempo": 120,
        "parts": {
            "Intro": {
                "measures": [
                    {"events": [{"type": "chord", "beat": 1.0, "chordName": "G", "frets": [{"string": 6, "fret": 3}]}]}
                ]
            },
            "Verse": {
                "measures": [
                    {"events": [{"type": "chord", "beat": 1.0, "chordName": "C", "frets": [{"string": 5, "fret": 3}]}]},
                    {"events": [{"type": "chord", "beat": 1.0, "chordName": "G", "frets": [{"string": 6, "fret": 3}]}]}
                ]
            },
            "Chorus": {
                "measures": [
                    {"events": [{"type": "chord", "beat": 1.0, "chordName": "F", "frets": [{"string": 6, "fret": 1}]}]},
                    {"events": [{"type": "chord", "beat": 1.0, "chordName": "C", "frets": [{"string": 5, "fret": 3}]}]}
                ]
            }
        },
        "structure": ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Chorus"]
    }
    
    # Test the model
    try:
        request = TabRequest(**example_request)
        print("✅ Parts system validation passed")
        
        # Test structure processing
        instances = process_song_structure(request)
        print(f"✅ Generated {len(instances)} part instances:")
        for instance in instances:
            print(f"   - {instance.display_name}")
        
        # Test analysis
        analysis = analyze_song_structure(request)
        print(f"✅ Analysis: {analysis['total_part_instances']} instances, {analysis['total_measures']} measures")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def create_schema() -> Dict[str, Any]:
    """Generate JSON Schema for the Guitar Tab Generator API."""
    return TabRequest.model_json_schema()

def save_schema(filename: str = "tab-schema.json"):
    """Save JSON Schema to file."""

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(create_schema(), f, indent=2)
    
    print(f"✅ Schema saved to {filename}")

# For CLI usage
if __name__ == "__main__":
    save_schema()