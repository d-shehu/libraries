from fastapi.responses          import RedirectResponse
from google_auth_oauthlib.flow  import Flow
from pathlib                    import Path
from typing                     import Dict, List

import secrets
import uuid

# Local packages
from web_service    import context, router, user

# Local files
from .define        import GAuthCredentials

# TODO: replace with a better mechanism
STATE_STORE: Dict[str, uuid.UUID] = {}

class GAuthRouter(router.ServiceRouter):
    
    def __init__(self, context: context.APIContext, gauthClientSecretsPath: Path, gauthCallbackURI: str, 
                 identifier: str, desiredScope: List[str]):
        super().__init__(context)
        self.gauthClientSecretsPath = gauthClientSecretsPath
        self.gauthCallbackURI       = gauthCallbackURI
        self.identifier             = identifier
        self.desiredScope           = desiredScope

    def registerRoutes(self):
        @self.api.post(self.getAPIPath("gauth/login"))
        async def login(userID: uuid.UUID, userGMail: str):
            user = self.context.getUser(userID)
            if user is not None:
                flow = Flow.from_client_secrets_file(
                    self.gauthClientSecretsPath,
                    scopes  = self.desiredScope,
                    redirect_uri = self.gauthCallbackURI
                )

                state = secrets.token_urlsafe(32)
                STATE_STORE[state] = userID

                authURL, _ = flow.authorization_url(
                    access_type             = "offline",
                    include_granted_scopes  = "true",
                    login_hint              = userGMail,
                    prompt                  = "consent",
                    state = state
                )

                return RedirectResponse(authURL)
        
        @self.api.get(self.getAPIPath("gauth/callback"))
        async def callback(state: str, code: str):
            userID = STATE_STORE[state]
            user = self.context.getUser(userID)
            if user is not None:
                state = str(self.context.getUserData(userID, "gauth_state"))
                flow = Flow.from_client_secrets_file(
                    self.gauthClientSecretsPath,
                    scopes  = self.desiredScope,
                    redirect_uri = self.gauthCallbackURI,
                    state   = state
                )

                flow.fetch_token(code=code)
                credentials = flow.credentials

                # TODO: add some robust checking
                self.context.setUserData(userID, self.identifier, GAuthCredentials(
                    str(credentials.token),
                    str(credentials.refresh_token),
                    self.desiredScope,
                    list(credentials.granted_scopes)
                ))

