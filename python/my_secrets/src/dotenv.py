from dotenv         import dotenv_values, set_key, unset_key
from pathlib        import Path
from threading      import Lock
from typing         import Dict, Optional

# Local package
from .secret        import Secret
from .backend       import Backend

class DotEnv(Backend):
    def __init__(self, 
                 envFilepath: Path):
        super().__init__("DotEnvBackend")
        
        self.envFilepath = envFilepath
        dotenvSecrets = dotenv_values(envFilepath)
        self.secrets:Dict[str, Secret] = {
            key: Secret(value, self.getID()) for key, value in dotenvSecrets.items()
        }  

        self.lock = Lock()

    def isSet(self, key: str) -> bool:
        with self.lock:
            return key in self.secrets

    def get(self, key: str) -> Optional[Secret]:
        secret: Optional[Secret] = None

        with self.lock:
            if key in self.secrets:
                secret = self.secrets[key]

        return secret
    
    def remove(self, key:str) -> bool:
        with self.lock:
            unset_key(self.envFilepath, key)
            return True

    def set(self, key: str, value: Secret) -> bool:
        with self.lock:
            self.secrets[key] = value
            set_key(self.envFilepath, key, value.expose())
            return True
        
