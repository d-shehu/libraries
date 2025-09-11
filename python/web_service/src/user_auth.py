from dataclasses    import dataclass
from datetime       import datetime, timedelta, timezone
from enum           import Enum
from jwt.exceptions import InvalidTokenError
from pathlib        import Path
from typing         import List, Optional, Tuple

import base64
import hashlib
import hmac
import json
import jwt
import os
import uuid

# Local files
from .user          import User
from .user_access   import Effect, Permission, Policy

@dataclass
class Token:
    access_token:   str
    token_type:     str

@dataclass
class JWTPayload:
    email:          str
    id:             str
    expires:        str
    permissions:    List[str]

    @staticmethod
    def FromToken(token):
        return JWTPayload(
            token["email"],
            token["id"],
            token["expires"],
            token["permissions"]
        )

class AuthStatus(Enum):
    OK                  = "OK"
    Invalid_User        = "Invalid_User"
    Invalid_Credentials = "Invalid_Credentials"

POLICY_FILE = "policy.json"

class UserAuth:
    DT_FORMAT_STR               = "%Y-%m-%d %H:%M:%S.%f%z"

    def __init__(self, processingDir: Path, secret: str, algorithm: str, tokenExpiryInDays: int, serviceID: uuid.UUID):
        self.secret             = secret
        self.algorithm          = algorithm
        self.tokenExpiryInDays  = tokenExpiryInDays
        self.serviceID          = serviceID

        # Policies (single file / 1 policy supported)
        self.processingDir              = processingDir
        self.policyFile                 = Path(processingDir, POLICY_FILE)
        self.policy: Optional[Policy]   = None

    def _createToken(self, email: str, id: str, permissions: List[str]) -> str:
        payload = JWTPayload(
            email,
            id,
             (datetime.now(timezone.utc) + timedelta(minutes=1)).strftime(UserAuth.DT_FORMAT_STR),
             permissions
        )

        token = jwt.encode(payload.__dict__, self.secret, self.algorithm)

        return token
    
    def load(self) -> bool:
        return self.loadPolicies()

    def store(self) -> bool:
        return self.storePolicies()
    
    def createUser(self, email: str, username: str, password: str) -> User:
        hashedPassword, passwordSalt = UserAuth.CreateCredentials(password)
        user = User(
            email,
            username,
            uuid.uuid4(),
            True,
            hashedPassword,
            passwordSalt,
        )
        return user

    def getTokenFromCredentials(self, user: Optional[User], givenPassword: str) -> Tuple[AuthStatus, Optional[Token]]:
        if user is None:
            return (AuthStatus.Invalid_User, None)
        elif not UserAuth.DoesPasswordMatch(user, givenPassword):
            return (AuthStatus.Invalid_Credentials, None)
        else:
            permissions = self.getUserPermissions(user.id)
            return (
                AuthStatus.OK, 
                Token(self._createToken(user.email, str(user.id), permissions=permissions), "bearer")
            )
        
    def getUserIDFromToken(self, token: str) -> Tuple[AuthStatus, Optional[uuid.UUID]]:
        try:
            decoded = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            payload = JWTPayload.FromToken(decoded)
            if payload.id is None:
                return (AuthStatus.Invalid_Credentials, None)
            
            return (AuthStatus.OK, uuid.UUID(payload.id))
        except InvalidTokenError:
            return (AuthStatus.Invalid_Credentials, None)
        
    def getUserPermissions(self, userID: uuid.UUID) -> List[str]:
        lsPermissions: List[str] = []

        if self.policy is not None:
            for statement in self.policy.statements:
                # All policies which are explicitly allowed for this user for this service.
                # TODO: this doesn't handle conditions, or multiple overlapping/conflicting conditions
                if (statement.actor == userID 
                    and statement.resource == self.serviceID
                    and statement.effect == Effect.Allow
                ):
                    for permission in statement.permissions:
                        # Encode the permission function:action
                        lsPermissions.append(permission.getFunction() + ":" + permission.getAction())


        return lsPermissions
        
    def loadPolicies(self) -> bool:
        success = False

        # No need to lock access since this happens at startup before accepting requests
        if self.policyFile.is_file():
            try:
                with open(self.policyFile, "r") as f:
                    self.policy = Policy(**json.loads(f.read(), object_hook = Policy.field_hook))

                # TODO: add more robust checks
                if self.policy is not None:
                    success = len(self.policy.statements) > 0
            except Exception as e:
                raise LookupError(f"Exception while trying to read from policy file: {POLICY_FILE}.")
        else:
            success = True # Policies is optional

        return success

    def storePolicies(self) -> bool:
        return True # TODO: Policy is ready-only and must be edited manually in-file
        
    def isAllowed(self, userID: uuid.UUID, resourceID: uuid.UUID, permission: Permission) -> bool:
        ret = False

        if self.policy is not None:
            ret = self.policy.isPermitted(
                userID,
                resourceID,
                permission
            )

        return ret
    

    @staticmethod
    def CreateCredentials(password: str) -> Tuple[str, str]:
        passwordSalt = os.urandom(16)
        hashedPassword = UserAuth.HashPassword(password, passwordSalt)
        return (base64.b64encode(hashedPassword).decode("utf-8"), 
                base64.b64encode(passwordSalt).decode("utf-8")
        )

    @staticmethod
    def DoesPasswordMatch(user: User, givenPassword: str) -> bool:
        givenPasswordHashed = UserAuth.HashPassword(
            givenPassword,
            base64.b64decode(user.passwordSalt.encode("utf-8"))
        )

        return hmac.compare_digest(
            base64.b64decode(user.hashedPassword.encode("utf-8")), 
            givenPasswordHashed
        )

    @staticmethod
    def HashPassword(password: str, passwordSalt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac(
            'sha256', 
            password.encode("utf-8"), 
            passwordSalt, 
            100000
        )