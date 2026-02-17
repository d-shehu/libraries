import boto3
import re

# Local packages
from my_secrets         import secret

# Import from this packages
from .backend           import Backend
from .notification      import Notification, NotificationContact, NotificationType
from .templates         import NotificationRenderer
from .utilities         import SupportContact

SMS_BACKEND = "SMSBackend"

class PhoneNumber(NotificationContact):
    ValidPhoneRegex = r"\+[1-9]\d{1,14}"

    def __init__(self, phoneNumber: str):
        self.phoneNumber = ""
        # Quick check that this is a valid phone number
        if not re.fullmatch(PhoneNumber.ValidPhoneRegex, phoneNumber):
            raise ValueError(f"Invalid phone number {phoneNumber}")
        else:
            self.phoneNumber = phoneNumber

    def __str__(self) -> str:
        return self.phoneNumber

class SMSNotification(Notification):
    def __init__(self, 
                 type: NotificationType, 
                 sender: PhoneNumber, 
                 receiver: PhoneNumber, 
                 message: str):
        super().__init__(SMS_BACKEND, type, sender, receiver, message)


class SMSBackend(Backend):

    def __init__(self,
                 awsRegion: str,
                 smsUserAccessKey: secret.Secret, 
                 smsUserSecretAccessKey: secret.Secret,
                 maxMessageSizeInCharacters: int = 160 # Maximum message length
                 ):
        
        super().__init__(SMS_BACKEND)

        self.smsUserAccessKey           = smsUserAccessKey
        self.smsUserSecretAccessKey     = smsUserSecretAccessKey
        self.awsRegion                  = awsRegion
        self.maxMessageSizeInCharacters = maxMessageSizeInCharacters

        self.snsClient                  = None

    async def load(self):

        self.snsClient = boto3.client("sns", 
                                      region_name = self.awsRegion,
                                      aws_access_key_id = self.smsUserAccessKey.expose(),
                                      aws_secret_access_key = self.smsUserSecretAccessKey.expose())
    
    async def unload(self):

        # Disconnect if client is initialized and hasn't timed out yet
        if self.snsClient is not None:
            try:
                self.snsClient.close()
            except Exception as e:
                raise Exception("Unable to clean up SNS client.")
            
        self.client = None
    
    # Enqueue notifications
    async def send(self, notification: Notification, supportContact: SupportContact):

        # Sanity check. Notification Mgr should be dispatching notifications to the appropriate handler.
        if type(notification) is SMSNotification and self.snsClient is not None:
            snsNotification: SMSNotification = notification

            # Render content using template
            renderer = NotificationRenderer(supportContact)
            template = renderer.render(notification.type,
                            str(notification.receiver),
                            "",
                            snsNotification.message)
            
            shortMessage = template.short
            
            if len(shortMessage) > self.maxMessageSizeInCharacters:
                raise Exception(f"SMS message of len {len(shortMessage)} is too long. Max allowed is {self.maxMessageSizeInCharacters}.")

            # TODO: process SMS response
            response = self.snsClient.publish(
                PhoneNumber=str(snsNotification.receiver),
                Message=shortMessage
            )
            
        elif self.snsClient is None:
            raise ValueError("SNS client is not initialized.")
        else:
            raise ValueError("The notification given is not an SMS notification.")
