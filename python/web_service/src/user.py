from dataclasses    import dataclass

import json
import uuid

@dataclass
class UserPublic:
    email:          str
    username:       str
    id:             uuid.UUID
    isActive:       bool

    def clone(self):
        return UserPublic(
            self.email,
            self.username,
            self.id,
            self.isActive
        )
    
    def assign(self, other):
        self.email          = other.email
        self.username       = other.username
        self.id             = other.id
        self.isActive       = other.isActive

    @staticmethod
    def id_hook(dict):
        if "id" in dict:
            dict["id"] = uuid.UUID(dict["id"])
        return dict

@dataclass
class User(UserPublic):
    hashedPassword: str
    passwordSalt:   str

    # Override if User is subclassed
    def clone(self) -> "User":
        return User(
            # From parent
            self.email,
            self.username,
            self.id,
            self.isActive,
            # This class' members
            self.hashedPassword,
            self.passwordSalt
        )

    def assign(self, other):
        super().assign(other)
        self.hashedPassword = other.hashedPassword
        self.passwordSalt   = other.passwordSalt

    @staticmethod
    def id_hook(dict):
        UserPublic.id_hook(dict)
        return dict

class UserEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, User):
            return {
                "email":            o.email,
                "username":         o.username,
                "id":               str(o.id),
                "isActive":         o.isActive,
                "hashedPassword":   o.hashedPassword,
                "passwordSalt":     o.passwordSalt,
            }
        else:
            return super().default(o)