import keyring

from typing         import Optional
from threading      import Lock

# Local package
from .backend       import Backend
from .secret        import Secret

class Keyring(Backend):
    def __init__(self, secretsPath = "system"):
        super().__init__("KeyringBackend")

        self.lock = Lock()
        self.secretsPath = secretsPath

    def isSet(self, key: str) -> bool:
        with self.lock:
            value = keyring.get_password(self.secretsPath, key)
            return value is not None

    def get(self, key: str) -> Optional[Secret]:
        secret: Optional[Secret] = None

        with self.lock:
            value = keyring.get_password(self.secretsPath, key)
            if value is not None:
                secret = Secret(value, self.getID())

    def set(self, key: str, value: Secret) -> bool:
        with self.lock:
            keyring.set_password(self.secretsPath, key, value.expose())
            return True

    def remove(self, key:str) -> bool:
        with self.lock:
            keyring.delete_password(self.secretsPath, key)
            return True