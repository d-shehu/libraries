from abc            import ABC, abstractmethod

from enum           import Enum
from typing         import List

class NotificationType(Enum):
    Info        = "Info"
    Warning     = "Warning"
    Error       = "Error"
    Critical    = "Critical"

# Define in backend implementation
class NotificationContact(ABC):
    @abstractmethod
    def __str__(self) -> str:
        pass

class Notification:
    def __init__(self,
                 backend:   str,
                 type:      NotificationType,
                 sender:    NotificationContact,
                 receiver:  NotificationContact,
                 message:   str,
                 ):
        
        self._backend       = backend
        self._type          = type
        self._sender        = sender
        self._receiver      = receiver
        self._message       = message

        # Other who receives notification
        self._others: List[NotificationContact] = []

    @property
    def backend(self) -> str:
        return self._backend
    
    @property
    def type(self) -> NotificationType:
        return self._type
    
    @type.setter
    def type(self, value: NotificationType):
        self._type = value

    @property
    def sender(self) -> NotificationContact:
        return self._sender
    
    @sender.setter
    def sender(self, value: NotificationContact):
        self._sender = value

    @property
    def receiver(self) -> NotificationContact:
        return self._receiver
    
    @receiver.setter
    def receiver(self, value: NotificationContact):
        self._receiver = value
    
    @property
    def message(self) -> str:
        return self._message
    
    @message.setter
    def message(self, value: str):
        self._message = value


    @property
    def others(self) -> List[NotificationContact]:
        return self._others
    
    @others.setter
    def others(self, value: List[NotificationContact]):
        self._others = value