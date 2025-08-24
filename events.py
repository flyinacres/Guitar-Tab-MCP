from typing import Dict, Type, Any
from pydantic import BaseModel, ValidationError


# ---------------------------
# 1. Generic SelfRegister mixin
# ---------------------------
class SelfRegister:
    """
    A generic mixin to automatically register subclasses.
    Each subclass family (like Event, Command, etc.) gets its own `_registry`.
    """
    _registry: Dict[str, Type] = {}

    def __init_subclass__(cls, key: str, **kwargs):
        """
        Called automatically by Python whenever a subclass is defined.
        Registers the subclass under the provided `key`.
        """
        super().__init_subclass__(**kwargs)
        cls._registry[key] = cls
        cls._key = key   # Store the key on the class (useful for debugging)


# ---------------------------
# 2. Base NotationEvent class (domain-specific)
# ---------------------------
class NotationEvent(SelfRegister, BaseModel):
    """
    Base class for all musical events.
    Inherits:
      - SelfRegister (so subclasses auto-register themselves)
      - Pydantic BaseModel (for validation and type safety)
    """

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """
        Factory method: build the right Event subclass from a dict.
        Looks up the 'type' field and delegates to the proper subclass.
        """
        event_type = data.get("type")
        subclass = cls._registry.get(event_type)
        if not subclass:
            raise ValueError(f"Unknown event type: {event_type}")

        # Use Pydantic validation when constructing
        return subclass(**{k: v for k, v in data.items() if k != "type"})

    def handle(self) -> None:
        """
        Default handler — subclasses should override this.
        """
        raise NotImplementedError("Each Event subclass must implement handle()")


# ---------------------------
# 3. Concrete Event subclasses
# ---------------------------
class ChordEvent(NotationEvent, key="chord"):
    chordName: str   # Pydantic field with type enforcement

    def handle(self) -> None:
        print(f"🎵 Handling chord: {self.chordName}")

class NoteEvent(NotationEvent, key="chord"):
    chordName: str   # Pydantic field with type enforcement

    def handle(self) -> None:
        print(f"🎵 Handling chord: {self.chordName}")

class PalmMuteEvent(NotationEvent, key="palmMute"):
    duration: float = 1.0  # Default duration if not specified

    def handle(self) -> None:
        print(f"🤘 Palm mute for {self.duration} beats")


class ChuckEvent(NotationEvent, key="chuck"):
    strength: int = 1   # Example field with default value

    def handle(self) -> None:
        print(f"🥁 Chuck with strength {self.strength}")
