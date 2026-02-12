from abc            import ABC, abstractmethod
from datetime       import datetime, timedelta, UTC
from hvac           import Client, exceptions as HVACExceptions
from time           import time
from threading      import Event, Thread
from typing         import Callable, Optional

# User module and logging
from core           import logs

# Local packages
from .backend       import Backend
from .secret        import Secret


# Notes: 
# 1. Currently not necessarily thread safe (TODO)

class Vault(Backend):
    DEFAULT_CHECK_INTERVAL_SECS         = 3600          # How often to check if renewal or rotation is needed. Account for policy check.
    DEFAULT_ROTATION_INTERVAL_SECS      = 24 * 3600     # Assume tokens need to be rotated daily by default
    DISABLE_CHECKS                      = 0             # Pass in 0 to checkIntervalsSecs to disable
    DEFAULT_SAFETY_MARGING_SECS         = 5*60          # Rotate or renew at least 5 minute before it's needed
    VAULT_CONNECT_RETRY_INTERVAL_SECS   = 10            # In case connection to vault is reset, wait 10 secs

    def __init__(self, 
                 addr: str,
                 initialToken: str,
                 secretPath: str,
                 checkIntervalSecs: int = DEFAULT_CHECK_INTERVAL_SECS,
                 rotationListener: Optional[Callable[[str], None]] = None,
                 rotationIntervalSecs: int = DEFAULT_ROTATION_INTERVAL_SECS,
                ):
        super().__init__("VaultBackend")

        self.addr = addr
        self.token = initialToken
        self.secretPath = secretPath
        self.checkIntervalSecs = checkIntervalSecs
        self.rotationListener = rotationListener
        self.rotationIntervalSecs = rotationIntervalSecs
        self.client: Optional[Client] = None

        if self.checkIntervalSecs < 0:
            raise ValueError("Renewal interval must be a positive number or '0' indicating token doesn't renew.")
        if self.checkIntervalSecs >= self.rotationIntervalSecs:
            raise ValueError("Need to check more frequently than the rotation duration.")
        
    def isSet(self, key: str) -> bool:
        return self.getKV(self.secretPath, key) is not None

    def get(self, key: str) -> Optional[Secret]:
        secret = None

        secretValue = self.getKV(self.secretPath, key)
        if secretValue is not None:
            secret = Secret(secretValue, self.backendID)

        return secret

    def set(self, key: str, secret: Secret) -> bool:
        return self.putKV(self.secretPath, key, secret.expose())
    
    def remove(self, key:str) -> bool:
        return self.deleteKV(self.secretPath, key)

    def cleanup(self):
        self.disconnect()
        
    def getKV(self, path: str, key: str) -> Optional[str]:
        secretVal = None

        try:
            if self.client is not None and self.client.secrets is not None:
                response = self.client.secrets.kv.v2.read_secret_version(
                    path=path,
                    mount_point="kv"
                )
                secretData = response["data"]["data"]
                secretVal = secretData.get(key)
            else:
                raise Exception(f"Unable to read '{key}' from '{path}' because hvac client is not initialized.")
        except HVACExceptions.InvalidPath:
            raise Exception(f"Unable to read '{key}' from '{path}' due to bad path")
        except Exception:
            raise Exception(f"Unable to read '{key}' from '{path}' due to unexpected exception")

        return secretVal
    
    def putKV(self, path: str, key: str, secret: str) -> bool:
        success = False

        try:
            if self.client is not None and self.client.secrets is not None:
                response = self.client.secrets.kv.v2.create_or_update_secret(
                    path=path,
                    secret=secret,
                    mount_point="kv"
                )

                # Grab new version to confirm put succeeded
                newVersion = int(response["data"]["metadata"]["version"])
                success = newVersion >= 0
            else:
                raise Exception(f"Unable to write '{key}' from '{path}' because hvac client is not initialized.")
        except HVACExceptions.InvalidPath:
            raise Exception(f"Unable to write '{key}' from '{path}' due to bad path")
        except Exception:
            raise Exception(f"Unable to write '{key}' from '{path}' due to unexpected exception")

        return success
    
    def deleteKV(self, path: str, key: str) -> bool:
        success = False

        try:
            if self.client is not None and self.client.secrets is not None:
                response = self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                    path=path,
                    mount_point="kv"
                )
                success = True # If not exception assume deletion was successful
            else:
                raise Exception(f"Unable to delete '{key}' from '{path}' because hvac client is not initialized.")
        except HVACExceptions.InvalidPath:
            raise Exception(f"Unable to delete '{key}' from '{path}' due to bad path")
        except Exception:
            raise Exception(f"Unable to delete '{key}' from '{path}' due to unexpected exception")

        return success
        
    def isConnected(self) -> bool:
        return self.client is not None and self.client.is_authenticated()
    
    def __getClient(self, currToken: str) -> Client:
        client = Client(url=self.addr, token=currToken)

        # Avoid Vault's silly blocked access. This should be in the
        # documented examples.
        client.session.headers.update({
            "User-Agent": "vault/1.13.0" 
        })

        return client
    
    def __doConnect(self) -> bool:
        try:
            self.client = self.__getClient(self.token)
        finally:
            return self.isConnected()

    def connect(self) -> bool:

        if not self.isConnected():
            try:        
                # If TTL is short-lived
                if self.__doConnect() and self.checkIntervalSecs > 0:
                    # Handle token renewal via thread
                    self._isRunning = Event()
                    self._timerEvent = Event()
                    self._isRunning.set()

                    self._thread    = Thread(name = "Vault_Token_Renewal_Thread", target = self.__run)
                    self._thread.start()

            except Exception as e:
                raise Exception("Unable to connect to the client or otherwise manage tokens.")
        else:
            raise Exception("Vault already connected. Disconnect and create a new instance of this class.")

        return self.isConnected()
    
    def __reconnect(self) -> bool:
        success = False

        try:
            if self.client is not None and self.isConnected():
                self.client.logout(revoke_token=False)

            success = self.__doConnect()
        finally:
            return success 
    
    def getWaitTime(self, interval, ttl):
        waitTime = interval
        if (ttl + Vault.DEFAULT_SAFETY_MARGING_SECS) < interval:
            waitTime = max(0, ttl - Vault.DEFAULT_SAFETY_MARGING_SECS)
        else:
            waitTime = interval

        return waitTime


    def __run(self):

        while self._isRunning.is_set() and self.client is not None:
            try:
                if self.client is not None and self.client.auth is not None:
                    # Lookup the token
                    tokenLookup = self.client.auth.token.lookup_self()["data"]

                    # Get ttl for token
                    ttl = int(tokenLookup["ttl"])

                    # If it's clone enough to expiring renew just to be safe
                    if ttl < (self.checkIntervalSecs + Vault.DEFAULT_SAFETY_MARGING_SECS):
                        response = self.client.auth.token.renew_self(self.checkIntervalSecs + Vault.DEFAULT_SAFETY_MARGING_SECS)
                        ttl = response["auth"]["lease_duration"]

                    # Calculate elapsed time since last rotation
                    lastRotation = tokenLookup["creation_time"]
                    now = int(datetime.now(UTC).timestamp())
                    remainingTime = seconds=now - lastRotation

                    # Rotate if it's nearly time
                    if remainingTime < (self.rotationIntervalSecs + Vault.DEFAULT_SAFETY_MARGING_SECS):
                        newTokenResponse = self.client.auth.token.create_orphan(
                            policies=["job-search"],
                            ttl=self.rotationIntervalSecs + Vault.DEFAULT_SAFETY_MARGING_SECS,
                            renewable=True,
                        )

                        # Grab the new token
                        newToken = newTokenResponse["auth"]["client_token"]

                        testClient = self.__getClient(newToken)
                        if not testClient.is_authenticated():
                            raise Exception("Vault token rotation failed!")
                            testClient.logout(revoke_token=False)
                        else:
                            # Safe to revoke old
                            self.client.logout(True)

                            # Update the token in memory
                            self.token = newToken
                            self.client = testClient

                            # Notify that token has been updated
                            if self.rotationListener is not None:
                                self.rotationListener(newToken)


                    self._timerEvent.wait(self.checkIntervalSecs)
                else:
                    raise Exception("Vault client not initialized or authentication failed")

            except Exception as e:
                # Sleep a few secs
                self._timerEvent.wait(Vault.VAULT_CONNECT_RETRY_INTERVAL_SECS)
                self.__reconnect()


    def __wait(self):
        if self._thread is not None:
            self._thread.join()

    def disconnect(self):
        if self._thread is not None:
            self._isRunning.clear()
            self._timerEvent.set()
            self.__wait()

        if self.client is not None:
            self.client.logout(False)
            self.client = None