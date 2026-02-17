import asyncio

from typing         import Awaitable, Callable, Dict, Optional

# User package
from core           import user_module, logs
from my_secrets     import secret

# This package
from .backend       import Backend, Notification
from .email         import EmailBackend
from .sms           import SMSBackend
from .templates     import SupportContact

class NotificationMgr(user_module.UserModule):
    def __init__(self,
                 supportContact: SupportContact,
                 logMgr = logs.ConfigureConsoleOnlyLogging("NotificationMgr")
                 ):
          super().__init__(logMgr)

          self.supportContact = supportContact
          self.backends : Dict[str, Backend] = {}
          
          self.__newLoopCreated = False
          try:
              self._loop = asyncio.get_event_loop()
          except RuntimeError:
              self._loop = asyncio.new_event_loop()
              asyncio.set_event_loop(self._loop)
              self.__newLoopCreated = True

    def __del__(self):
        self.removeAllNotifiers()

        try:
            if self.__newLoopCreated and self._loop is not None and not self._loop.is_closed():
                self._loop.close()
            if self.__newLoopCreated:
                asyncio.set_event_loop(None)
        except Exception:
            self.logger.exception("Unexpected exception while cleaning up asyncio loop.")


    def addGMailNotifier(self, username: secret.Secret, password: secret.Secret) -> bool:
        success = False

        try:
            gmailBackend = EmailBackend(
                username,
                password
                )
            
            if gmailBackend.clsID not in self.backends:
                self._loop.run_until_complete(gmailBackend.load())

                # Currently only support one email backend
                self.backends[gmailBackend.clsID] = gmailBackend
                success = True
            else:
                self.logger.error("Email backend already exists. Only one is allowed. Please remove other.")
        except Exception as e:
            self.logger.exception("Unable to add GMail notifier.")

        return success
    
    def addSMSNotifier(self, awsRegion: str, userAccessKey: secret.Secret, userSecretAccessKey: secret.Secret):
        success = False

        try:
            smsBackend = SMSBackend(
                awsRegion,
                userAccessKey,
                userSecretAccessKey
            )

            if smsBackend.clsID not in self.backends:
                self._loop.run_until_complete(smsBackend.load())

                # Currently only support one email backend
                self.backends[smsBackend.clsID] = smsBackend
                success = True
            else:
                self.logger.error("SMS backend already exists. Only one is allowed. Please remove other.")
        except Exception as e:
            self.logger.exception("Unable to add SMS notifier.")

        return success
    
    def removeNotifier(self, clsID: str) -> bool:
        success = False

        if clsID in self.backends:
            backend = self.backends[clsID]
            self._loop.run_until_complete(backend.unload())
            del self.backends[clsID]
        else:
            self.logger.error(f"Can't remove notifier {clsID} as it does not exist.")
        
        return success
    
    def removeAllNotifiers(self):

        for backend in self.backends.values():
            try:
                self._loop.run_until_complete(backend.unload())
            except Exception:
                self.logger.error(f"Unable to unload backend {backend.clsID}.")

        self.backends.clear()

    
    # Default handler called when notification is sent. User can override by setting onSend.
    async def __defaultOnSend(self, notification: Notification, success: bool):    
        if success:
            self.logger.debug(f"Notification with message {notification.message} sent.")
        else:
            self.logger.error(f"Unable to send notification with message {notification.message}.")

    async def __onSend(self, backend: Backend, 
                       notification: Notification, 
                       onSend: Callable[[Notification, bool], Awaitable[None]]
                       ):

        success = False

        try:
            await backend.send(notification, self.supportContact)
            success = True
        except:
            self.logger.exception("Exception while sending notification.")
        
        await onSend(notification, success)
              
    def scheduleNotification(self, 
                         notification: Notification, 
                         onSend: Optional[ Callable[[Notification, bool], Awaitable[None]] ] = None) -> bool:
        
        success = False

        # Find the backend (email, sms, etc.) for this notifier
        clsID = notification.backend
        if clsID in self.backends:
            backend = self.backends[clsID]

            # Inner async function that actually sends the notification
            callback = onSend if onSend is not None else self.__defaultOnSend

            #asyncio.run(self.__onSend(backend, notification, callback))
            self._loop.run_until_complete(self.__onSend(backend, notification, callback))
            success = True
        else:
            self.logger.error("Backend is not available for notification with backendID {clsID}.")

        return success
