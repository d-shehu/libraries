from abc                import ABC, abstractmethod
from fastapi            import APIRouter, FastAPI, HTTPException, status
from fastapi.security   import OAuth2PasswordBearer

# Local source
from .context       import *
from .user          import User, UserPublic
from .user_auth     import AuthStatus

class ServiceRouter(ABC):

    def __init__(self, context: APIContext):
        self.context        = context
        self.api            = APIRouter()
        self.oath2Scheme    = OAuth2PasswordBearer(tokenUrl = "token")
        
    @abstractmethod
    def registerRoutes(self):
        pass

    def addRouter(self, app: FastAPI) -> None:
        self.registerRoutes()
        app.include_router(self.api)
    
    def getAPIPath(self, path: str) -> str:
        return f"/{self.context.apiPrefix}/v{self.context.apiVersion}/{path}"
    
    def getFullUserDataFromToken(self, token: str) -> User:
        authStatus, userID = self.context.userAuth.getUserIDFromToken(token)
        user = self.context.userMgr.getUserByID(userID) if userID is not None else None
        if authStatus == AuthStatus.OK and user is not None:
            return user
        elif authStatus == AuthStatus.Invalid_Credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User credentials are invalid."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unexpected status or user data while decoding JWT token."
            )

    def getUserFromToken(self, token: str) -> UserPublic:
        return self.getFullUserDataFromToken(token)
