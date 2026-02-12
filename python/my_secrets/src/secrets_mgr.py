from pathlib        import Path
from typing         import cast, List, Optional, TypeVar

import os
import sys

# User module and logging
from core           import user_module, logs

# Local package
from .backend       import Backend
from .dotenv        import DotEnv
from .keyring       import Keyring
from .secret        import Secret
from .vault         import Vault

# Generic type
T = TypeVar("T")

# Backends are supported
# 1. dotenv file - simplest and needed to boostrap other backends
# 2. keyring - for local applications (TODO)
# 3. vault - for services

class SecretsMgr(user_module.UserModule):

    # Vault specific configs
    VAULT_ADDR_ENV_VAR:             str = "VAULT_ADDRESS"
    VAULT_TOKEN_ENV_VAR:            str = "VAULT_TOKEN"
    # Optional
    VAULT_CHECK_INTERVAL_ENV_VAR:   str = "VAULT_CHECK_INTERVAL_SECS"
    VAULT_ROTATE_INTERVAL_ENV_VAR:  str = "VAULT_ROTATE_INTERVAL_SECS"

    def __init__(self,
                 secretsPath: str,
                 logMgr = logs.ConfigureConsoleOnlyLogging("SecretsMgr")
                 ):
        super().__init__(logMgr)

        self.secretsPath = secretsPath
        self.backends: List[Backend] = []

    # Use .env for services or deployments where keyring is not available.
    # Assume this .env is appropriately restricted via permissions.
    def loadFromEnv(self, envPath: Path) -> bool:

        success = False

        try:
            self.backends.append(DotEnv(envPath))

            # Load other backends
            success = self.__initBackends()
        except Exception:
            self.logger.exception("Unexpected exception while loading dotenv configs & secrets.")
        
        return success
    
    # Use keyring for app deployments
    def loadFromKeyring(self) -> bool:

        success = False

        try:
            self.backends.append(Keyring(self.secretsPath))

            # Load other backends
            success = self.__initBackends()
        except Exception:
            self.logger.exception("Unexpected exception while loading dotenv configs & secrets.")
        
        return success
    
    def unload(self):
        for backend in self.backends:
            backend.cleanup()

    def __initBackends(self) -> bool:

        success = True # Other backends are optional

        # Vault requires token, vault address which should be 
        # secured as well. Use the existing backend either
        # dotenv or keyring to get the vault settings assume
        # user wants to enable vault. 
        if self.hasSecret(SecretsMgr.VAULT_ADDR_ENV_VAR):
            success = self.__initVault()

        return success
    
    def __initVault(self) -> bool:

        success = False

        # If Vault is defined then the token must as well
        if self.hasSecret(SecretsMgr.VAULT_TOKEN_ENV_VAR):

            try:
                # Interval is defined?
                checkInterval = self.__getConfig(SecretsMgr.VAULT_CHECK_INTERVAL_ENV_VAR, 
                                                     Vault.DEFAULT_CHECK_INTERVAL_SECS)
                rotateInterval = self.__getConfig(SecretsMgr.VAULT_ROTATE_INTERVAL_ENV_VAR,
                                                      Vault.DEFAULT_ROTATION_INTERVAL_SECS)

                vault = Vault(
                    self.__getConfig(SecretsMgr.VAULT_ADDR_ENV_VAR, ""),
                    self.__getConfig(SecretsMgr.VAULT_TOKEN_ENV_VAR, ""),
                    self.secretsPath,
                    checkInterval,
                    self.__onVaultTokenRotate,
                    rotationIntervalSecs=rotateInterval
                )

                success = vault.connect()
                if success:
                    self.backends.insert(0, vault) # Insert as 1st backend as the preferred store for secrets
                else:
                    self.logger.error("Vault config detected but unable to connect to it.")
            except Exception:
                self.logger.exception("Exception while trying to initialize Vault")
        else:
            self.logger.error("Current token for vault is not defined. Unable to connect.")

        return success
    
    def __onVaultTokenRotate(self, newToken: str):
        # Use the original backend (DotEnv or keyring) for the token as it's
        # needed to bootstrap Vault.
        backend = self.backends[-1]
        backend.set(SecretsMgr.VAULT_TOKEN_ENV_VAR, 
                    Secret(newToken, backend.getID()))
    
    
    # A convenience function for restricted configs but not necessarily secrets. 
    # Risky since it exposes the value as a plain old string. Use with caution!
    def __getConfig(self, key: str, default: T) -> T:
        config: T = default

        secret = self.getSecret(key)
        if secret is not None:
            config = type(default)(secret.expose())
        
        return config
    
    def hasSecret(self, key: str) -> bool:
        found = False

        # Backends are in priority order. Return 1st match.
        for backend in self.backends:
            try:
                found = backend.isSet(key)
                if found:
                    break
            except Exception:
                self.logger.exception(f"Exception while trying to get secret {key}")

        return found
         
    def getSecret(self, key: str) -> Optional[Secret]:
        secret: Optional[Secret] =  None

        # Backends are in priority order. Return 1st match.
        for backend in self.backends:
            try:
                if backend.isSet(key):
                    secret = backend.get(key)
                    if secret is not None:
                        break
                    else:
                        self.logger.error(f"Secret {key} found but not undefined")
            except Exception:
                self.logger.exception(f"Exception while trying to get the secret {key}")

        return secret

    def updateSecret(self, key: str, secret: Secret) -> bool:
        success = False

        for backend in self.backends:
            try:
                if backend.getID() == backend.isSet(key):
                    success = backend.set(key, secret)
            except Exception:
                self.logger.exception(f"Unexpected exception while updating secret {key} with backend {secret.getBackendID()}")

        if not success:
            self.logger.error(f"Unable to match or otherwise update secret {key} for backend {secret.getBackendID()}")
        
        return success

    def putSecret(self, key: str, secret: str) -> bool:
        success = False

        try:
            preferredBackend = self.backends[0] # 1st is preferred
            success = preferredBackend.set(key, Secret(secret, preferredBackend.getID()))

            if not success:
                self.logger.error(f"Unable to set secret {key} in backend {preferredBackend.getID()}")
        except Exception:
            self.logger.exception("Unexpected exception while setting secret {key} in backend {preferredBackend.getID()}")

        return success


