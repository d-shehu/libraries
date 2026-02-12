from abc            import ABC, abstractmethod
from typing         import Optional

# Local package
from .secret        import Secret

class Backend(ABC):
    @abstractmethod
    def __init__(self, 
                 backendID: str):
        
        self.backendID  = backendID

    def getID(self) -> str:
        return self.backendID

    @abstractmethod
    def isSet(self, key: str) -> bool:
        pass

    @abstractmethod
    def get(self, key: str) -> Optional[Secret]:
        pass

    @abstractmethod
    def set(self, key: str, value: Secret) -> bool:
        pass

    @abstractmethod
    def remove(self, key:str) -> bool:
        pass

    # Override in child class if clean up is needed
    def cleanup(self):
        pass