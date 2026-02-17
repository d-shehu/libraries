from abc                import ABC, abstractmethod

# This package
from .notification      import Notification
from .utilities         import SupportContact

class Backend(ABC):

    def __init__(self, clsID: str):
        self._clsID = clsID

    @property
    def clsID(self) -> str:
        return self._clsID
    
    @abstractmethod
    async def load(self):
        pass

    @abstractmethod
    async def unload(self):
        pass

    @abstractmethod
    async def send(self, notification: Notification, supportContact: SupportContact):
        pass
