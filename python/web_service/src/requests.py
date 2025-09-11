
from abc            import ABC, abstractmethod
from enum           import Enum
from typing         import Generic, Optional, TypeVar

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

class Status(Enum):
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
    def __init__(self, data: dict):
        for key, value in data.items():
            setattr(self, key, value)

    @abstractmethod
    def decode(self, dict) -> bool:
        pass
    
    @abstractmethod
    def encode(self) -> str:
        pass

# User-defined subclass of 'RequestPayload'.
PayloadType = TypeVar("PayloadType", bound = RequestPayload)
    
class Request(Generic[PayloadType]):
    def __init__(self, userID: uuid.UUID, priority = Priority.P3_Medium, status: Status = Status.Created, 
                 id: uuid.UUID = uuid.uuid4(), timestamp = time.time()):
        self.userID:    uuid.UUID   = userID
        self.priority:  Priority    = priority # Priority, optional and assumed to be medium
        self.status:    Status      = status # User can cancel requests
        self.id:        uuid.UUID   = id
        self.timestamp: float       = timestamp # Keep track of when request was made

        self.payload: Optional[PayloadType]  = None
        
    @staticmethod
    def field_hook(dict):
        if "userID" in dict:
            dict["userID"] = uuid.UUID(dict["userID"])
        if "id" in dict:
            dict["id"] = uuid.UUID(dict["id"])
        if "priority" in dict:
            # Try as enum value or name
            try:
                dict["priority"] = Priority[dict["priority"]]
            except:
                dict["priority"] = Priority(dict["priority"])
        if "status" in dict:
            # Try as enum value or name
            try:
                dict["status"] = Status[dict["status"]]
            except:
                dict["status"] = Status(dict["status"])
        if "payload" in dict:
            payload: Optional[PayloadType] = None
            if payload is not None:
                payload = payload(**dict["payload"])
                payload.decode()
            dict["payload"] = payload
        return dict
    
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
            return {
                "userID":               str(o.userID),
                "priority":             o.priority.name,
                "status":               o.status.name,
                "id":                   str(o.id),
                "timestamp":            o.timestamp
            }
        elif isinstance(o, RequestPayload):
            return o.encode()
        else:
            return super().default(o)