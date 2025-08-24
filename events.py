from typing import Dict, Type, Any, List
from pydantic import BaseModel, Field


class SelfRegister(BaseModel):
    """
      A generic mixin to automatically register subclasses.
      Each subclass must define a unique event_type string.
      A registry maps event_type → subclass automatically.
    """
    # A shared registry for subclasses
    _registry: Dict[str, Type] = {}

    type: str  # All events must carry their type

    # Called when a subclass is created
    def __init_subclass__(cls, key: str, **kwargs):
        """Automatically called when a subclass is defined."""
        super().__init_subclass__(**kwargs)
        cls._registry[key] = cls   # Register this subclass
        cls._key = key             # Optional: store the key on the class

# === Base Event class with registry ===
class Event(SelfRegister):
    """
    Base class for all events.
    """

    """Base class for all musical events."""
    _registry: Dict[str, Type["Event"]] = {}  # Keeps a separate registry for Event types

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """
        Factory method:
        Look up the correct subclass from registry,
        validate input data with Pydantic, and return the event object.
        """
        event_type = data.get("type")
        if event_type in cls._registry:
            # Use Pydantic validation here!
            return cls._registry[event_type](**data)
        raise ValueError(f"Unknown event type: {event_type}")
    

    def handle_annotation(self, *args, **kwargs):
        """
        Each subclass must implement this method
        to perform the actual handling logic.
        """
        raise NotImplementedError("Subclasses must implement handle()")


# === Subclasses (event types) ===

class ChordEvent(Event, event_type="chord"):
    chordName: str = Field(..., description="The name of the chord, e.g. Gmaj7")

    def handle_annotation(self, chord_chars, char_position, total_width):
        place_annotation_text(chord_chars, char_position, self.chordName, total_width)


class PalmMuteEvent(Event, event_type="palmMute"):
    duration: float = Field(1.0, description="Duration of the palm mute in beats")

    def handle_annotation(self, annotation_chars, char_position, total_width):
        pm_text = generate_palm_mute_notation(self.duration)
        place_annotation_text(annotation_chars, char_position, pm_text, total_width)


class ChuckEvent(Event, event_type="chuck"):
    def handle_annotation(self, annotation_chars, char_position, total_width):
        place_annotation_text(annotation_chars, char_position, "X", total_width)
