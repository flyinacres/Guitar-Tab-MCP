#!/usr/bin/env python3
"""
Pydantic V2 Compatible Notation Models for  Tab Generator
==========================================================

Updated Pydantic models compatible with V2 syntax using:
- @field_validator instead of @validator
- Literal instead of const
- Updated Field syntax and validation patterns
"""

import sys
import logging
from typing import Dict, ClassVar, Type, List, Any, Optional, Union, Literal
from pydantic import BaseModel, Field, field_validator, ValidationError
from time_signatures import ( get_time_signature_config, get_strum_positions_for_time_signature, calculate_char_position )
from tab_models import TabRequest, TabError, TabFormatError, ConflictError

# Import our constants
from tab_constants import (
    DynamicLevel, DisplayLayer,
    VALID_EMPHASIS_VALUES, MAX_FRET, MAX_STRING, MIN_STRING,
    MAX_SEMITONES, MIN_SEMITONES, SUPERSCRIPT_SYMBOLS, SUBSCRIPT_SYMBOLS,
    DEFAULT_SYMBOLS
)

# Configure logging to stderr only (stdout reserved for MCP protocol)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)



# ============================================================================
# Base Event Models
# ============================================================================

class NotationEvent(BaseModel):
    """Base class for all tab events with common properties."""
    emphasis: Optional[str] = Field(None, description="Dynamic or articulation marking")
    _registry: ClassVar[Dict[str, Type]] = {}

    # Helpers for generating notation
    _technique_toggle : ClassVar[int] = 0
    _display_style = "regular"
    
    @classmethod
    def set_technique_style(cls, style: str):
        """Set the default technique formatting style for all events."""
        valid_styles = ["regular", "superscript", "subscript", "alternating"]
        if style in valid_styles:
            cls._display_style = style
        else:
            raise ValueError(f"Invalid style '{style}'. Valid: {valid_styles}")
    
    def get_alternating_style(self) -> str:
        """Get the current style for alternating mode."""
        self.__class__._technique_toggle += 1
        return "superscript" if self.__class__._technique_toggle % 2 == 0 else "subscript"
    
    def map_str(self, text: str, char_map: Dict) -> str:
        """Convert entire string (digits and technique symbols) to superscript."""
        result = ""
        for char in text:
            result += char_map.get(char, char)

        return result
    
    def format_technique(self, technique_type: str, part1: str, 
                        part2: str, style: Optional[str] = None
                        ) -> str:
        """
        Format a musical technique with specified style.
        
        Args:
            technique_type: Type of technique ("h", "p", "b", "/", "\\")
            part1: First part (from_fret for hammer-on, fret for bend, etc.)
            part2: Second part (to_fret for hammer-on, semitones for bend, etc.)
            style: Formatting style ("superscript", "subscript", "alternating", "regular")
            
        Returns:
            Formatted technique string
            
        Examples:
            format_technique("h", 3, 5, "superscript") -> "³ʰ⁵"
            format_technique("p", 7, 5, "subscript") -> "₇ₚ₅"  
            format_technique("b", 12, 1.5, "alternating") -> varies based on count
        """
        if style is None:
            style = self.__class__._display_style
        
        style_selector = style
        if style_selector == "alternating":
            # Set the style to either sub or super script
            style_selector = self.get_alternating_style()
        
        # Choose proper mapping method for chars
        char_map: Dict = DEFAULT_SYMBOLS
        if style_selector == "superscript":
            char_map = SUPERSCRIPT_SYMBOLS
        elif style_selector == "subscript":
            char_map = SUBSCRIPT_SYMBOLS

        return (self.map_str(f"{part1}{technique_type}{part2}", char_map))
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NotationEvent":
        """
        Factory method: build the right Event subclass from a dict.
        Looks up the 'type' field and delegates to the proper subclass.
        """
        event_type = data.get("type")
        subclass = cls._registry.get(event_type)
        if not subclass:
            raise ValueError(f"Unknown event type: {event_type}")

        # Use Pydantic validation when constructing
        try:
          return subclass(**{k: v for k, v in data.items() if k != "type"})
        except Exception as e:
          print(f"Failed to instantiate {subclass} with data {data}")
          raise
    
    def __init_subclass__(cls, type=None, **kwargs):
        """
        Called automatically by Python whenever a subclass is defined.
        Registers the subclass under the provided `key`.
        """
        super().__init_subclass__(**kwargs)
        cls._registry[type] = cls
        cls._type = type   # Store the key on the class (useful for debugging)
    
    @field_validator('emphasis')
    @classmethod
    def validate_emphasis(cls, v):
        if v is not None and v not in VALID_EMPHASIS_VALUES:
            raise ValueError(f"Invalid emphasis '{v}'. Valid values: {VALID_EMPHASIS_VALUES}")
        return v

class MusicalEvent(NotationEvent):
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
#  Musical Events
# ============================================================================

class Note(MusicalEvent, type="note"):
    """ note event with dynamics and articulation."""
    string: int = Field(..., ge=MIN_STRING, le=MAX_STRING)
    beat: float
    fret: Union[int, str]  # int for fret number, "x" for muted
    vibrato: bool = False
    # This is here so emphasis goes onto the proper layer
    layer: DisplayLayer = DisplayLayer.DYNAMICS
    
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
    
    def generate_notation(self):
        # Handle muted strings and vibrato
        if isinstance(self.fret, str) and self.fret.lower() == "x":
            fret_str = "x"
        else:
            fret_str = str(self.fret)
            if self.vibrato:
                fret_str += "~"

        return fret_str

class Chord(MusicalEvent, type="chord"):
    """ chord event with dynamics and emphasis."""
    beat: float
    chordName: Optional[str] = None
    frets: List[Dict[str, Union[int, str]]]  # [{"string": 1, "fret": 3}, ...]
    layer: DisplayLayer = DisplayLayer.CHORD_NAMES
    
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

class Slide(MusicalEvent, type="slide"):
    """ slide with emphasis support."""
    string: int = Field(..., ge=MIN_STRING, le=MAX_STRING)
    startBeat: float
    fromFret: int = Field(..., ge=0, le=MAX_FRET)
    toFret: int = Field(..., ge=0, le=MAX_FRET)
    direction: Literal["up", "down"]
    vibrato: bool = False
    layer: DisplayLayer = DisplayLayer.DYNAMICS

    def generate_notation(self):
        symbol = "/" if self.direction == "up" else "\\"

        # Compact format: "3/5" or "12\8"
        notation = self.format_technique(symbol, str(self.fromFret), str(self.toFret))

        # Add vibrato notation if specified (applies to the destination note)
        if self.vibrato:
            notation += "~"

        return notation

class Bend(MusicalEvent, type="bend"):
    """ bend with emphasis and vibrato."""
    string: int = Field(..., ge=MIN_STRING, le=MAX_STRING)
    beat: float
    fret: int = Field(..., ge=0, le=MAX_FRET)
    semitones: float = Field(..., ge=MIN_SEMITONES, le=MAX_SEMITONES)
    vibrato: bool = False
    layer: DisplayLayer = DisplayLayer.DYNAMICS

    def generate_notation(self) -> str:
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

        # Handle muted strings in bends (unusual but possible)
        if isinstance(self.fret, str) and self.fret.lower() == "x":
            fret_str = "x"
        else:
            fret_str = str(self.fret)

        semitone_str = str(self.semitones)

        # Handle common fraction cases with Unicode symbols
        match self.semitones:
            case 0.25:
                semitone_str = "¼"
            case 0.5:
                semitone_str = "½"
            case 0.75:
                semitone_str = "¾"
            case 1.25:
                semitone_str = "1¼"
            case 1.5:
                semitone_str = "1½"
            case 1.75:
                semitone_str = "1¾"
            case 2.25:
                semitone_str = "2¼"
            case 2.5:
                semitone_str = "2½"
            case 2.75:
                semitone_str = "2¾"
            case 3.0:
                semitone_str = "3"
        
        # Handle whole numbers (remove .0)
        if self.semitones == int(self.semitones):
            semitone_str = str(int(self.semitones))
        # Fallback for unusual decimal values

        technique_str = self.format_technique("b", fret_str, semitone_str)

        # Add vibrato notation if specified
        if self.vibrato:
            technique_str += "~"

        return technique_str


class HammerOn(MusicalEvent, type="hammerOn"):
    """ hammer-on with emphasis."""
    string: int = Field(..., ge=MIN_STRING, le=MAX_STRING)
    startBeat: float
    fromFret: int = Field(..., ge=0, le=MAX_FRET)
    toFret: int = Field(..., ge=0, le=MAX_FRET)
    vibrato: bool = False
    layer: DisplayLayer = DisplayLayer.DYNAMICS
    
    @field_validator('toFret')
    @classmethod
    def validate_hammer_direction(cls, v, info):
        if 'fromFret' in info.data and v <= info.data['fromFret']:
            raise ValueError("Hammer-on toFret must be higher than fromFret")
        return v
    
    def generate_notation(self) -> str:
        # Compact format: "3h5" or "10p12"
        notation = self.format_technique("h", str(self.fromFret), str(self.toFret))

        # Add vibrato notation if specified (applies to the destination note)
        if self.vibrato:
            notation += "~"

        return notation

class PullOff(MusicalEvent, type="pullOff"):
    """ pull-off with emphasis."""
    string: int = Field(..., ge=MIN_STRING, le=MAX_STRING)
    startBeat: float
    fromFret: int = Field(..., ge=0, le=MAX_FRET)
    toFret: int = Field(..., ge=0, le=MAX_FRET)
    vibrato: bool = False
    layer: DisplayLayer = DisplayLayer.DYNAMICS
    
    @field_validator('toFret')
    @classmethod
    def validate_pulloff_direction(cls, v, info):
        if 'fromFret' in info.data and v >= info.data['fromFret']:
            raise ValueError("Pull-off toFret must be lower than fromFret")
        return v
    
    def generate_notation(self) -> str:
        # Compact format: "3h5" or "10p12"
        notation = self.format_technique("p", str(self.fromFret), str(self.toFret))

        # Add vibrato notation if specified (applies to the destination note)
        if self.vibrato:
            notation += "~"

        return notation
    
# ============================================================================
# New Event Types
# ============================================================================

class StrumPattern(NotationEvent, type="strumPattern"):
    """Strum pattern that can span multiple measures."""
    startBeat: float = 1.0
    pattern: List[str]  # Array of strum directions: ["D", "U", "", "D", ...]
    measures: int = Field(default=1, ge=1, le=8)  # How many measures this pattern spans
    layer: DisplayLayer = DisplayLayer.STRUM_PATTERN
    
    @field_validator('pattern')
    @classmethod
    def validate_pattern(cls, v):
        valid_values = ["D", "U", ""]
        for direction in v:
            if direction not in valid_values:
                raise ValueError(f"Invalid strum direction '{direction}'. Use 'D', 'U', or ''")
        return v
    
    def process_strum_pattern(
        self,
        current_measure: int,
        time_signature: str,
        strum_chars: List[str],
        total_width: int
    ):
        """
        Process strum pattern and place it in the strum pattern layer.

        Args:
            current_measure: Current measure index (0-based)
            time_signature: Time signature string
            strum_chars: Character array for strum pattern layer
            total_width: Total width of the display
        """
        config = get_time_signature_config(time_signature)
        positions_per_measure = len(config["valid_beats"])

        logger.debug(f"Processing strum pattern: {len(self.pattern)} positions, {self.measures} measures")

        # For now, assume the pattern starts at the beginning of the measure group
        pattern_start_measure = 0  # Relative to current measure group

        # Check if current measure is covered by this pattern
        if current_measure < pattern_start_measure or current_measure >= pattern_start_measure + self.measures:
            logger.debug(f"Measure {current_measure} not covered by pattern (starts at {pattern_start_measure}, spans {self.measures})")
            return

        measure_offset_in_pattern = current_measure - pattern_start_measure
        pattern_start_idx = measure_offset_in_pattern * positions_per_measure
        pattern_end_idx = pattern_start_idx + positions_per_measure

        # Extract the pattern slice for this measure
        measure_pattern = self.pattern[pattern_start_idx:pattern_end_idx]

    # Validate pattern slice bounds
        if pattern_start_idx >= len(self.pattern):
            logger.warning(f"Pattern start index {pattern_start_idx} exceeds pattern length {len(self.pattern)}")
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
    @classmethod
    def validate_strum_patterns(cls, request: TabRequest) -> TabError:
        """
        Validate strum pattern events for proper time signature compatibility in parts-based schema.

        Checks:
        - Pattern length matches time signature requirements
        - Pattern spans complete measures only
        - No overlapping strum patterns
        - Valid strum direction values
        """
        time_sig = request.timeSignature
        expected_positions = get_strum_positions_for_time_signature(time_sig)

        logger.debug(f"Validating strum patterns for {time_sig} (expecting {expected_positions} positions per measure)")

        for part in request.parts:
            active_patterns = []  # Track overlapping patterns within this part

            logger.debug("Validating strum patterns in part '%s'", part.name)

            for measure_idx, measure in enumerate(part.measures):
                for event in measure.events:
                    if event.get("type") != "strumPattern":
                        continue

                    logger.debug(f"Found strum pattern in part '{part.name}' measure {measure_idx}")

                    pattern = event.get("pattern", [])
                    measures_spanned = event.get("measures", 1)
                    start_beat = event.get("startBeat", 1.0)

                    # Validate pattern length
                    expected_length = expected_positions * measures_spanned
                    if len(pattern) != expected_length:
                        logger.error(f"Strum pattern length mismatch in part '{part.name}': got {len(pattern)}, expected {expected_length}")
                        return TabFormatError(
                            part = part.name,
                            measure = measure_idx,
                            message = f"Strum pattern in part '{part.name}' has {len(pattern)} positions, expected {expected_length} for {measures_spanned} measures of {time_sig}",
                            suggestion = f"Pattern should have {expected_length} elements for {measures_spanned} measures of {time_sig}. Each measure needs {expected_positions} positions."
                        )

                    # Validate pattern values
                    for i, direction in enumerate(pattern):
                        if direction not in ["D", "U", ""]:
                            logger.error(f"Invalid strum direction '{direction}' at position {i} in part '{part.name}'")
                            return TabFormatError(
                                part = part.name,
                                measure = measure_idx,
                                message = f"Invalid strum direction '{direction}' at position {i} in part '{part.name}'",
                                suggestion = "Use 'D' for down, 'U' for up, or '' for no strum"
                            )

                    # Check for pattern overlaps within this part
                    pattern_info = {
                        "start_measure": measure_idx,
                        "end_measure": measure_idx + measures_spanned - 1,
                        "start_beat": start_beat
                    }

                    for existing_pattern in active_patterns:
                        if (pattern_info["start_measure"] <= existing_pattern["end_measure"] and
                            pattern_info["end_measure"] >= existing_pattern["start_measure"]):
                            logger.error(f"Overlapping strum patterns detected in part '{part.name}'")
                            return ConflictError(
                                part = part.name,
                                measure = measure_idx,
                                message = f"Overlapping strum patterns detected in part '{part.name}'",
                                suggestion = "Only one strum pattern can be active at a time within a part"
                            )

                    active_patterns.append(pattern_info)
                    logger.debug(f"Strum pattern validated in part '{part.name}': {measures_spanned} measures, {len(pattern)} positions")

        logger.debug("Strum pattern validation passed")
        return None

class GraceNote(MusicalEvent, type="graceNote"):
    """Grace note - small note played quickly before main note."""
    string: int = Field(..., ge=MIN_STRING, le=MAX_STRING)
    beat: float  # Beat where the grace note leads into
    fret: Union[int, str]
    graceFret: Union[int, str]  # The grace note fret
    graceType: Literal["acciaccatura", "appoggiatura"] = "acciaccatura"
    layer: DisplayLayer = DisplayLayer.DYNAMICS

    def convert_to_superscript(self, digit_string: str) -> str:
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

    def convert_to_subscript(self, digit_string: str) -> str:
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

    def generate_notation(self) -> str:
        # Convert grace fret to superscript
        if self.graceType == "acciaccatura":
            sscript_grace = self.convert_to_superscript(str(self.graceFret))
        else:
            # Appoggiatura: ₃5 (using subscript for distinction)
            sscript_grace = self.convert_to_subscript(str(self.graceFret))

        return f"{sscript_grace}{self.fret}"
    
    @classmethod
    def validate_grace_note_conflicts(cls, grace_notes: List[Dict], events_by_position: Dict, part_name: str, measure: int) -> TabError:
        """
        Check for conflicts between grace notes and main notes in parts-based schema.
        """
        for grace_note in grace_notes:
            # Each grace_note should be a GraceNote
            string_num = grace_note.string
            beat = grace_note.beat

            # Check if there's a main note at the same position
            position_key = f"{string_num}_{beat}"
            if position_key not in events_by_position:
                return TabFormatError(
                    part = part_name,
                    measure = measure,
                    beat = beat,
                    message = f"Grace note in part '{part_name}' on string {string_num} has no target note at beat {beat}",
                    suggestion = "Grace notes must lead into a main note at the same beat and string"
                )

        return None
    
    @classmethod
    def validate_grace_note_timing(cls, beat: float, time_sig: str, part_name: str, measure: int) -> TabError:
        """
        Validate grace note timing for parts-based schema.
        """
        config = get_time_signature_config(time_sig)
        max_beat = max(config["valid_beats"])

        # Grace notes should not be at the very end of a measure
        if beat >= max_beat:
            return TabFormatError(
                part = part_name,
                measure = measure,
                beat = beat,
                message = f"Grace note in part '{part_name}' has invalid timing at beat {beat}",
                suggestion = f"Grace notes should be placed before beat {max_beat}"
            )

        return None

class Dynamic(NotationEvent, type="dynamic"):
    """Standalone dynamic marking that affects following notes/chords."""
    beat: float
    dynamic: str = Field(..., description="Dynamic level (pp, p, mp, mf, f, ff)")
    duration: Optional[float] = None  # How long this dynamic lasts
    layer: DisplayLayer = DisplayLayer.DYNAMICS
    possible_dynamics: List = ["cresc.", "dim.", "<", ">"]
    
    @field_validator('dynamic')
    @classmethod
    def validate_dynamic(cls, v):
        valid_dynamics = [d.value for d in DynamicLevel] + cls.possible_dynamics
        if v not in valid_dynamics:
            raise ValueError(f"Invalid dynamic '{v}'. Valid: {valid_dynamics}")
        return v

    def generate_notation(self) -> str:
        """
        Generate dynamic notation with optional duration indicators.

        Args:
            dynamic: Dynamic marking (pp, p, mp, mf, f, ff, cresc., etc.)
            duration: Optional duration for extended markings

        Returns:
            String like "f", "cresc.---", "dim.--"
        """
        if self.dynamic in self.possible_dynamics:
            # Extended markings get duration dashes
            if self.duration:
                num_dashes = max(1, int(self.duration * 2))
                return self.dynamic + "-" * num_dashes
            else:
                return self.dynamic + "---"  # Default length

        # Standard dynamics are just the marking
        return self.dynamic
    
# ============================================================================
#  Annotation Events
# ============================================================================

class PalmMute(NotationEvent, type="palmMute"):
    """ palm mute with intensity levels."""
    beat: float
    duration: float = Field(default=1.0, gt=0, le=8.0)
    intensity: Optional[Literal["light", "medium", "heavy"]] = None
    intensity_map: Dict = {"light": "(L)", "medium": "(M)", "heavy": "(H)"}
    layer: DisplayLayer = DisplayLayer.ANNOTATIONS

    def generate_notation(self) -> str:
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
        if self.intensity:
            base += self.intensity_map.get(self.intensity, "")

        # Add duration dashes
        num_dashes = max(1, int(self.duration * 2))
        return base + "-" * num_dashes

class Chuck(NotationEvent, type="chuck"):
    """ chuck with emphasis levels."""
    beat: float
    intensity: Optional[Literal["light", "medium", "heavy"]] = None
    layer: DisplayLayer = DisplayLayer.ANNOTATIONS

    def generate_notation(self) -> str:
        return "X" + (self.intensity[0].upper() if self.intensity else "")  # X, XL, XM, XH