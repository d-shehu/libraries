from abc            import ABC, abstractmethod
from enum           import Enum
from pathlib        import Path
from threading      import Lock
from typing         import Dict, Iterable, List, Optional

import json
import os
import shutil
import tempfile
import uuid

# Local files
from .user          import User, UserEncoder

# Defines
USERS_FILE      = "users.json"

class UserUpdateStatus(Enum):
    Success         = 0
    Does_Not_Exist  = 1
    ID_Conflict     = 2
    Email_Conflict  = 3
    Other_Error     = 4

class UserMgrBase(ABC):
    
    @abstractmethod
    def loadUsers(self) -> bool:
        pass

    @abstractmethod
    def storeUsers(self) -> bool:
        pass

    @abstractmethod
    def getUserByID(self, id: uuid.UUID) -> Optional[User]:
        pass

    @abstractmethod
    def getUserByEmail(self, email: str) -> Optional[User]:
        pass

    @abstractmethod
    def getUsers(self) -> Iterable[User]:
        pass

    @abstractmethod
    def add(self, user: User) -> UserUpdateStatus:
        pass

    @abstractmethod
    def remove(self, id: uuid.UUID) -> bool:
        pass

    @abstractmethod
    def deactivate(self, id: uuid.UUID) -> bool:
        pass

    @abstractmethod
    def updateUser(self, id: uuid.UUID, updatedUser: User) -> UserUpdateStatus:
        pass

# Default implementation is file based. 
# TODO: introduce Cognito and other Auth support.
class UserMgrFiles(UserMgrBase):
    def __init__(self, processingDir: Path, usersDir: Path):
        # A simple implementation in memory assuming relatively few users.
        self.processingDir  = processingDir
        self.usersFile      = Path(processingDir, USERS_FILE)
        self.usersDir       = usersDir

        # TODO: implement as a user cache if number of users, user data is large
        # Simplified lookup as set of uuid and emails are mutually exclusive. 
        self.usersByID:     Dict[uuid.UUID, User]   = {}
        self.usersByEmail:  Dict[str, User]         = {}
        self._userLock                              = Lock()

    def getUserPath(self, user: User):
        return Path(self.usersDir, str(user.id))

    def initUser(self, user: User):
        # Don't throw exception if user directory already exists
        self.getUserPath(user).mkdir(0o700, False, True)

    def loadUsers(self) -> bool:
        success = False

        # No need to lock access since this happens at startup before accepting requests
        if self.usersFile.is_file():
            lsUsers: List[User] = []
            try:
                with open(self.usersFile, "r") as f:
                    rawList = json.loads(f.read(), object_hook = User.id_hook)
                    lsUsers = [User(**l) for l in rawList]

                errorAdding = False
                for user in lsUsers:
                    errorAdding = self.add(user) != UserUpdateStatus.Success

                success = not errorAdding
            except Exception as e:
                raise LookupError(f"Exception while trying to read from users file: {USERS_FILE}.")

        return success

    # Allow periodic writing of requests to file to minimize risk of losing data records
    def storeUsers(self) -> bool:
        success = False

        lsUsers = []

        with self._userLock:
            for user in self.usersByID.values():
                lsUsers.append(user)

        try:
            # Store records not yet processed here
            tempPath = ""
            with tempfile.NamedTemporaryFile("w", dir = self.processingDir, delete = False) as tmpFile:
                tmpFile.write(json.dumps(lsUsers, cls = UserEncoder))
                tmpFile.flush()
                os.fsync(tmpFile.fileno())
                tempPath = tmpFile.name

            # If succeeded then copy to processing
            if Path(tempPath).is_file():
                shutil.move(tempPath, Path(self.processingDir, USERS_FILE))

            success = True
        except Exception as e:
            raise SystemError("Unable to persist users to file.")

        return success
    
    def getUserByID(self, id: uuid.UUID) -> Optional[User]:
        user: Optional[User] = None

        with self._userLock:
            user = self.usersByID[id]

        return user
    
    def getUserByEmail(self, email: str) -> Optional[User]:
        user: Optional[User] = None

        with self._userLock:
            if email in self.usersByEmail:
                user = self.usersByEmail[email]

        return user
    
    def getUsers(self) -> Iterable[User]:
        # Make a copy of users to avoid concurrency issue
        with self._userLock:
            return list(self.usersByID.values())
    
    def add(self, user: User) -> UserUpdateStatus:
        with self._userLock:
            if user.id in self.usersByID:
                return UserUpdateStatus.ID_Conflict
            elif user.email in self.usersByEmail:
                return UserUpdateStatus.Email_Conflict
            else:
                self.usersByID[user.id] = user
                self.usersByEmail[user.email] = user
                self.initUser(user)

            return UserUpdateStatus.Success
        
    def remove(self, id: uuid.UUID) -> bool:
        success = False

        with self._userLock:
            if id is self.usersByID:
                user = self.usersByID[id]
                del self.usersByID[user.id]
                del self.usersByEmail[user.email]
                success = True
            
        return success
    
    def deactivate(self, id: uuid.UUID) -> bool:
        success = False

        with self._userLock:
            if id is self.usersByID:
                user = self.usersByID[id]
                if user.isActive:
                    user.isActive = False
                    success = True
            
        return success

    def updateUser(self, id: uuid.UUID, updatedUser: User) -> UserUpdateStatus:
        status: UserUpdateStatus = UserUpdateStatus.Other_Error

        with self._userLock:
            user = self.usersByID[id]
            if user is None:
                status = UserUpdateStatus.Does_Not_Exist
            elif user.email != updatedUser.email:
                if updatedUser.email in self.usersByEmail:
                    status = UserUpdateStatus.Email_Conflict
                else:
                    del self.usersByEmail[user.email]
                    user.assign(updatedUser)
                    self.usersByEmail[updatedUser.email] = user
                    status = UserUpdateStatus.Success
            else:
                user.assign(updatedUser)
                status = UserUpdateStatus.Success

        return status

    