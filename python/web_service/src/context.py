from pathlib            import Path

import secrets
import uuid

# Local packages
from core               import threaded_dict

# Local sources
from .processor         import Processor
from .user_mgr          import UserMgrBase
from .user_auth         import UserAuth


class APIContext:
    def __init__(self, serviceID: uuid.UUID, processingDir: Path, processor: Processor, userMgr: UserMgrBase, asyncClient, logger):
        
        self.serviceID      = serviceID
        self.processingDir  = processingDir
        self.processor      = processor
        self.userMgr        = userMgr
        # TODO: consider switching to asymmetric encryption and key management. Params shouldn't be hard-coded.
        self.userAuth       = UserAuth(processingDir, 
                                       secrets.token_hex(32), 
                                       "HS256", 
                                       7,
                                       serviceID)
                                       
        self.asyncClient    = asyncClient
        self.logger         = logger
        
        self.apiPrefix      = "api"
        self.apiVersion     = 1

        # TODO: does custom user data needed to be persisted?
        self.userData = threaded_dict.ThreadedDict[uuid.UUID, threaded_dict.ThreadedDict[str, object]]()

    def load(self) -> bool:
        return self.userMgr.loadUsers() and self.userAuth.load()

    def store(self) -> bool:
        return self.userMgr.loadUsers() and self.userAuth.store()
            
    def clearAllUserData(self, id: uuid.UUID):
        if id in self.userData:
            del self.userData[id]
        else:
            raise LookupError(f"Unable to clear user data because data for user {id} not found.")
        
    def setUserData(self, id: uuid.UUID, key: str, value: object) -> bool:
        success = False

        try:
            if not id in self.userData:
                self.userData[id] = threaded_dict.ThreadedDict[str, object]()
            self.userData[id][key] = value
            success = True
        except:
            self.logger.error(f"Data with key {key} for user with id {id} already exists.")

        return success
    
    def unsetUserData(self, id: uuid.UUID, key: str) -> bool:
        success = False
    
        if id in self.userData and key in self.userData[id]:
            del self.userData[id][key]

        return success

    def getUserData(self, id: uuid.UUID, key: str) -> object:
        ret = None

        if id in self.userData and key in self.userData[id]:
            ret = self.userData[id][key]

        return ret

            
