# A simple placeholder for users API to avoid every service implementing it's own

from fastapi            import Depends, Form, HTTPException, status
from typing             import Annotated, List

import uuid

# Local source
from ..context          import APIContext
from ..router           import ServiceRouter
from ..user             import User, UserPublic
from ..user_auth        import AuthStatus, UserAuth, Token
from ..user_access      import SimplePermissions
from ..user_mgr         import UserUpdateStatus

class UsersRouter(ServiceRouter):
    def __init__(self, context: APIContext):
        super().__init__(context)

    def registerRoutes(self):

        @self.api.post(self.getAPIPath("login"))
        async def loginUser(email:str = Form(...), password: str = Form(...),
                             status_code = status.HTTP_200_OK) -> Token:
            user = self.context.userMgr.getUserByEmail(email)
            loginStatus, token = self.context.userAuth.getTokenFromCredentials(user, password)
            if loginStatus == AuthStatus.Invalid_User:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User with this email {email} does not exist."
                )
            elif loginStatus == AuthStatus.Invalid_Credentials:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User credentials are invalid."
                )
            elif token is None:
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Authentication token is unexpectedly null."
                ) 
            else:
                return token   

        @self.api.post(self.getAPIPath("users"), status_code = status.HTTP_201_CREATED)
        async def createUser(email:str = Form(...), userName: str = Form(...), password: str = Form(...)):
            hashedPassword, passwordSalt = UserAuth.CreateCredentials(password)
            user = User(
                email,
                userName,
                uuid.uuid4(),
                True,
                hashedPassword,
                passwordSalt
            )
            createdStatus = self.context.userMgr.add(user)
            if createdStatus == UserUpdateStatus.Email_Conflict:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User with this email exists."
                )
            elif createdStatus == UserUpdateStatus.ID_Conflict:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User with this id already exists."
                )
            elif createdStatus != UserUpdateStatus.Success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Service encountered unexpected error while trying to add user."
                ) 
            
        @self.api.get(self.getAPIPath("users"))
        async def getUsers(token: Annotated[str, Depends(self.oath2Scheme)]) -> List[UserPublic]:
            currUser = self.getUserFromToken(token)
            if (self.context.userAuth.isAllowed(
                currUser.id, 
                self.context.serviceID,
                SimplePermissions(
                    "users",
                    "list"
                ))
            ):
                return list(self.context.userMgr.getUsers())
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="This user doesn't have permission to access other user data."
                )
        
        @self.api.put(self.getAPIPath("user"), status_code = status.HTTP_204_NO_CONTENT)
        async def updateUser(token: Annotated[str, Depends(self.oath2Scheme)], 
                             email: str = Form(...), 
                             username: str = Form(...)
                             ):
            
            currUser = self.getFullUserDataFromToken(token)
            if email != "" and username != "":
                updatedUser = currUser.clone()
                updatedUser.email = email
                updatedUser.username = username

                updatedStatus = self.context.userMgr.updateUser(currUser.id, updatedUser)
                if updatedStatus == UserUpdateStatus.Success:
                    return updatedUser.id
                elif updatedStatus == UserUpdateStatus.Email_Conflict:
                    # New email must not be in-use
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="New email already assigned to a user."
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Service encountered unexpected error while trying to updated user."
                    )
            else: 
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Please specify a valid email and username."
                )
                
        @self.api.get(self.getAPIPath("users"), status_code = status.HTTP_200_OK)
        async def getUser(token: Annotated[str, Depends(self.oath2Scheme)]) -> UserPublic:
             return self.getUserFromToken(token)

        # TODO: when deleting users we should purge user data also.
        @self.api.put(self.getAPIPath("users/{{userID}}/deactivate"), status_code = status.HTTP_204_NO_CONTENT)
        async def deactivateUsers(token: Annotated[str, Depends(self.oath2Scheme)], userID: uuid.UUID):
            currUser = self.getUserFromToken(token)
            if (self.context.userAuth.isAllowed(
                currUser.id, 
                self.context.serviceID,
                SimplePermissions(
                    "users",
                    "deactivate"
                ))
            ):
                if not self.context.userMgr.deactivate(userID):
                    raise HTTPException(
                        status.HTTP_404_NOT_FOUND,
                        detail="User doesn't exist or can't be deactivated."
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="This user doesn't have permission to access other user data."
                )

        # TODO: when deleting users we should purge user data also.
        @self.api.delete(self.getAPIPath("users/{{userID}}"), status_code = status.HTTP_204_NO_CONTENT)
        async def deleteUser(token: Annotated[str, Depends(self.oath2Scheme)], userID: uuid.UUID):
            currUser = self.getUserFromToken(token)
            if (self.context.userAuth.isAllowed(
                currUser.id, 
                self.context.serviceID,
                SimplePermissions(
                    "users",
                    "delete"
                ))
            ):
                if not self.context.userMgr.remove(userID):
                    raise HTTPException(
                        status.HTTP_404_NOT_FOUND,
                        detail="User doesn't exist and can't be deleted."
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="This user doesn't have permission to access other user data."
                )
            
            