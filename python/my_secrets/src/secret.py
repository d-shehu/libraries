# Secret wrapper to avoid exposing string accidentally through logging, etc.
# Inspired by SecretStr (pydantic)

from typing import Optional, Any

class Secret:

    __slots__ = ("_value","_backendID",)

    def __init__(self, secret: Optional[str], backendID: str):

        # Store the value in a *private* attribute; ``__slots__`` prevents accidental
        # creation of a __dict__ entry that could be inspected.
        self._value: str = secret if secret is not None else ""
        self._backendID = backendID

    # Never leak the actual string while debugging.
    def __repr__(self) -> str:
        return f"<SecretStr length={len(self._value)} hidden>"
    def __str__(self) -> str:  # pragma: no cover (identical to repr)
        return "<SECRET>"
    
    # User exposes the secret
    def expose(self) -> str:
        return self._value
    
    def update(self, newValue: str):
        self._value = newValue

    def getBackendID(self) -> str:
        return self._backendID
    
    # Replace default implementation
    def __eq__(self, other: Any) -> bool:
        # Only compare against other Secrets or string
        if isinstance(other, Secret):
            return self._value == other._value
        elif isinstance(other, str):
            return self._value == other
        
        return NotImplemented

    # Support use in dictionaries without directly exposing the value
    def __hash__(self) -> int:
        return hash(self._value)
    

    def __iter__(self):
        raise TypeError(
            "Object is not iterable. Use '.expose' to obtained the underlying string."
        )

    def __len__(self) -> int:
        return len(self._value)

    # ------------------------------------------------------------------
    # Dictionary conversion – defensive
    # ------------------------------------------------------------------
    def __dict__(self) -> dict:
        raise AttributeError(
            "Object does not expose a `__dict__`. Use '.expose' to obtained the underlying string."
        )