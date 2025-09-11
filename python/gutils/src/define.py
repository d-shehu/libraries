from dataclasses    import dataclass
from typing         import List

@dataclass
class GAuthCredentials:
    token:          str
    refreshToken:   str
    desiredScope:   List[str]
    grantedScopes:  List[str]


class GAuthScopeTypes:
    GDRIVE_READ_ONLY = "gdrive_read_only"

GAUTH_SCOPES = {
    GAuthScopeTypes.GDRIVE_READ_ONLY: [
        "https://www.googleapis.com/auth/drive.readonly"
    ]
}
