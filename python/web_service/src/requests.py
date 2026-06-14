
from abc            import ABC, abstractmethod
from enum           import Enum, IntFlag
from typing         import ClassVar, Optional

import json
import time
import uuid

REQUEST_EXPIRY_INTERVAL = 3600 * 24 # Expire low priority requests after a day

class Priority(Enum):
    Undefined   = ""
    P1_Critical = "p1"
    P2_High     = "p2"
    P3_Medium   = "p3"
    P4_Low      = "p4"
    P5_Lowest   = "P5" 

class Status(IntFlag):
    Undefined   = 0
    Created     = 0x1
    Enqueued    = 0x2
    Processing  = 0x4
    Pending     = Created | Enqueued | Processing
    Succeeded   = 0x8
    Failed      = 0x10
    Canceled    = 0x20
    Expired     = 0x30
    Resolved    = Succeeded | Failed | Canceled | Expired
    Any         = Created | Enqueued | Processing | Succeeded | Failed | Canceled | Expired

class RequestPayload(ABC):
    @abstractmethod
    def encode(self) -> dict:
        pass

class Request:
    _registry: ClassVar[dict[str, type["Request"]]] = {}

    def __init__(self, 
                 userID: uuid.UUID, 
                 priority                   = Priority.P3_Medium, 
                 status                     = Status.Created, 
                 id: Optional[uuid.UUID]    = None, 
                 timestamp: Optional[float] = None):
        
        self.userID:    uuid.UUID   = userID
        self.priority:  Priority    = priority  # Priority, optional and assumed to be medium
        self.status:    Status      = status    # User can cancel requests
        # All requests must have a unique ID
        self.id:        uuid.UUID   = id if id is not None else uuid.uuid4()
        # Keep track of when request was made
        self.timestamp: float       = timestamp if timestamp is not None else time.time()

        self.payload: Optional[RequestPayload]  = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        Request._registry[cls.__name__] = cls

    def to_dict(self):
        return {
            "type":         type(self).__name__,
            "userID":       str(self.userID),
            "priority":     self.priority.name,
            "status":       self.status.name,
            "id":           str(self.id),
            "timestamp":    self.timestamp,
            "payload":      self.payload.encode() if self.payload is not None else None
        }
    
    @classmethod
    def from_dict(cls, data):
        targetCls = Request._registry[data["type"]]
        obj = targetCls(
            userID      = uuid.UUID(data["userID"]),
            priority    = Priority[data["priority"]],
            status      = Status[data["status"]],
            id          = uuid.UUID(data["id"]),
            timestamp   = float(data["timestamp"]),
        )

        if "payload" in data:
            obj.payload = targetCls._createPayload(data["payload"])

        return obj
    
    @classmethod
    def _createPayload(cls, data: dict) -> Optional[RequestPayload]:
        return None
    
    def isPending(self) -> bool:
        return ((self.status.value & Status.Pending.value) != 0)
    
    def checkExpired(self):
        # Only expire if status is pending ...
        if self.isPending():
            # ... and if low priority request and exceeded expiry interval.
            if (((time.time() - self.timestamp) >= REQUEST_EXPIRY_INTERVAL)
                and ((self.priority == Priority.P4_Low) or (self.priority == Priority.P5_Lowest))):
                self.status = Status.Expired

        return (self.status == Status.Expired)
    
    def __lt__(self, other):
        # Order based on absolute priority. Specific users not favored.
        return (self.priority < other.priority and
                self.timestamp < other.timestamp)    

class RequestEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Request):
            return o.to_dict()
        else:
            return super().default(o)