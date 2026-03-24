from enum           import Enum
from threading      import Lock
from typing         import Dict, Optional

# Local packages
from core           import user_module, logs

# This package
from .mail          import MailCredentials, MailProvider
from .gmail         import GMail

class ProviderType(Enum):
    GMail = "GMail"

class MailMgr(user_module.UserModule):
    def __init__(self,
                 logMgr = logs.ConfigureConsoleOnlyLogging("MailMgr")
                 ):
        super().__init__(logMgr)
        self.providers: Dict[str, MailProvider] = {}
        self.lock = Lock()


    def __del__(self):
        with self.lock:
            for provider in self.providers.values():
                provider.disconnect()

    def __createProvider(self, type: ProviderType) -> Optional[MailProvider]:
        provider = None

        if type == ProviderType.GMail:
            provider = GMail()
        else:
            self.logger.error(f"Provider {type.value} not supported.")

        return provider

    # Create or obtain
    def getProvider(self, type: ProviderType, credentials: Optional[MailCredentials] = None) -> Optional[MailProvider]:
        provider: Optional[MailProvider] = None

        providerType = type.value
        with self.lock:
            if providerType in self.providers:
                provider = self.providers[providerType]
            elif credentials is None:
                self.logger.error(f"Provider {providerType} not initialized and credentials not available.")
            else:
                newProvider = self.__createProvider(type)
                if newProvider and newProvider.connect(credentials):
                    self.providers[type.value] = newProvider
                    provider =  newProvider
                else:
                    self.logger.error("Unable to connect to mail provider with the given credentials.")
        
        return provider

