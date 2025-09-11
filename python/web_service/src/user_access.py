# Note this is an experimental feature and WIP and will evolve as we build more services.

from abc            import ABC, abstractmethod
from enum           import Enum
from dataclasses    import dataclass
from typing         import Any, List, Union

import json
import uuid

class Effect(Enum):
    Allow   = "Allow"
    Deny    = "Deny"

class Match(Enum):
    Allow   = "Allow"
    Deny    = "Deny"
    NA      = "N/A"

@dataclass
class Permission(ABC):
    @abstractmethod
    def isPermitted(self, desiredPerm) -> Match:
        pass

    @abstractmethod
    def toJSON(self) -> str:
        pass

    @abstractmethod
    def fromJSON(self, data: str) -> bool:
        pass

    @abstractmethod
    def getCLSName(self) -> str:
        pass

    @abstractmethod
    def getFunction(self) -> str:
        pass

    @abstractmethod
    def getAction(self) -> str:
        pass

@dataclass
class SimplePermissions(Permission):
    function:   str
    action:     str
    clsName:    str = "SimplePermissions"

    def isPermitted(self, desiredPerm) -> Match:
        ret = Match.NA
        if isinstance(desiredPerm, SimplePermissions) and (self.function == desiredPerm.function):
            ret = Match.Allow if (self.action == desiredPerm.action) else Match.Deny

        return ret
    
    def toJSON(self) -> str:
        return json.dumps(self)
    
    def fromJSON(self, data: str) -> bool:
        try:
            obj = json.loads(data)
            self.function       = obj["function"]
            self.action         = obj["action"]

            return True
        except:
            return False
        
    def getCLSName(self):
        return self.clsName
    
    def getFunction(self) -> str:
        return self.function

    def getAction(self) -> str:
        return self.action

class PermissionCreator:
    @staticmethod
    def create(dict: dict):
        clsName = dict["clsName"]
        match clsName:
            case "SimplePermissions":
                return SimplePermissions(**dict)
            case _:
                raise LookupError(f"{clsName} is not a known child class of Permissions.")


class UnaryOperand(Enum):
    Undefined   = ""
    Not         = "Not"

class BinaryOperand(Enum):
    And = "And"
    Or  = "Or"
    EQ  = "="

class Condition(ABC):
    @abstractmethod
    def eval(self, operand: UnaryOperand = UnaryOperand.Undefined) -> bool:
        pass

    @abstractmethod
    def __call__(self, operand: BinaryOperand, rValue: Union['Condition', str]) -> bool:
        pass

class KVCondition(Condition):
    key:        str
    value:      str
    
    def __init__(self, key: str, value: str):
        self.key    = key
        self.value  = value

    @staticmethod
    def _Bool(value: str) -> bool:
        ret = False

        # TODO: clean up. Some common ways to encode bool
        if value in ('y', 'yes', 't', 'true', 'enabled', 'on', '1'):
            ret = True
        elif value in ('n', 'no', 'f', 'false', 'disabled', 'off', '0'):
            ret = False
        else:
            raise ValueError("{value} does not appear to be a boolean.")
        
        return ret

    def eval(self, operand: UnaryOperand = UnaryOperand.Undefined) -> bool:

        ret = KVCondition._Bool(self.value.lower())
        if operand == UnaryOperand.Not:
            ret = not ret
        
        return ret
        
    def __call__(self, operand: BinaryOperand, other: Union[Condition, str]) -> bool:
        ret = False

        if isinstance(other, Condition):
            match operand:
                case BinaryOperand.And:
                    ret = (self.eval() and other.eval())
                #case BinaryOperand.Or:
                    ret = (self.eval() or other.eval())
                case BinaryOperand.EQ:
                    ret = (self.eval() == other.eval())
                case _:
                    raise NotImplementedError("{operand} not supported.")
        else:
            match operand:
                case BinaryOperand.And:
                    ret = (self.eval() and KVCondition._Bool(other))
                case BinaryOperand.Or:
                    ret = (self.eval() or KVCondition._Bool(other))
                case BinaryOperand.EQ:
                    ret = (self.value == other)
                case _:
                    raise NotImplementedError("{operand} not supported.")

        return ret
                

# TODO: conditional logic is TBD. Need to evaluate if action should be a str or inheritable class.
@dataclass
class Statement:
    actor:          uuid.UUID           # User or service account
    effect:         Effect              # Allow or deny action. Always default to deny.
    permissions:    List[Permission]    # What specific functionality to allow or deny on resource
    resource:       uuid.UUID           # Service or some system resource to which this policy applies
    #conditions: List[Condition]
    statementID:    uuid.UUID           # ID of this policy statement
    description:    str                 # Short human-readable summary of what this policy does.

    @staticmethod
    def field_hook(dict):
        if "actor" in dict:
            dict["actor"] = uuid.UUID(dict["actor"])

        if "effect" in dict:
            # Try as enum value or name
            try:
                dict["effect"] = Effect[dict["effect"]]
            except:
                dict["effect"] = Effect(dict["effect"])

        if "permissions" in dict:
            dict["permissions"] = [PermissionCreator.create(permissionData) for permissionData in dict["permissions"]]

        if "resource" in dict:
            dict["resource"] = uuid.UUID(dict["resource"])

        if "statementID" in dict:
            dict["statementID"] = uuid.UUID(dict["statementID"])
        return dict
    
    def isPermitted(self, actor: uuid.UUID, resource: uuid.UUID, requestedPermission: Permission) -> Match:
        ret = Match.NA
    
        if self.actor == actor and self.resource == resource:
             # TODO: simplest approach for evaluating policies. Ignores conditions and is not efficient 
            # if there are many permissions, etc. See below.
            for permission in self.permissions:
                currMatch = permission.isPermitted(requestedPermission)
                if currMatch != Match.NA:
                    ret = currMatch

        return ret

    
class StatementEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Statement):
            return {
                "actor":            str(o.actor),
                "effect":           str(o.effect),
                "permission":       str(o.permissions),
                "resource":         str(o.resource),
                "statementID":      str(o.statementID),
                "description":      o.description
            }
        else:
            return super().default(o)

@dataclass
class Policy:
    statements: List[Statement] # Must have at least one statement
    policyID:   uuid.UUID
    version:    str

    @staticmethod
    def field_hook(dict):
        if "statements" in dict:
            for statement in dict["statements"]:
                Statement.field_hook(statement)
            dict["statements"] = [Statement(**statementData) for statementData in dict["statements"]]

        if "policyID" in dict:
            dict["policyID"] = uuid.UUID(dict["policyID"])
        
        return dict
    
    # TODO: simplest approach for evaluating policies. Ignores conditions and is not efficient 
    # if there are many statements, etc.
    def isPermitted(self, actor: uuid.UUID, resource: uuid.UUID, requestedPermission: Permission) -> bool:
        ret = False # Assume not allowed unless explicitly specified

        for statement in self.statements:
            # TODO: not there may be conflicting statements or specific conditions.
            currMatch = statement.isPermitted(actor, resource, requestedPermission)
            if currMatch != Match.NA:
                ret = True if Match.Allow else False


        return ret


class PolicyEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Policy):
            return {
                "statements":       str([StatementEncoder().default(s) for s in o.statements]),
                "policyID":         str(o.policyID),
                "version":          o.version,
            }
        else:
            return super().default(o)
