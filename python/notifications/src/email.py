import aiosmtplib
import mimetypes
import re
import ssl

from datetime           import datetime, timezone
from email.message      import EmailMessage
from pathlib            import Path
from typing             import List, Optional

# Local packages
from my_secrets         import secret

# Import from this packages
from .notification      import Notification, NotificationContact, NotificationType
from .backend           import Backend
from .templates         import NotificationRenderer
from .utilities         import SupportContact

# Defines
EMAIL_BACKEND = "EmailBackend"

class EmailAttachment:
    def __init__(self,
                 filename: str,
                 maintype: str,
                 subtype: str,
                 fileData: bytes):
        
        self._filename  = filename
        self._mainType  = maintype
        self._subtype   = subtype
        self._fileData  = fileData

    @property
    def filename(self) -> str:
        return self._filename
    
    @filename.setter
    def filename(self, value: str):
        self._filename = value

    @property
    def mainType(self) -> str:
        return self._mainType
    
    @mainType.setter
    def mainType(self, value: str):
        self._mainType = value

    @property
    def subtype(self) -> str:
        return self._subtype
    
    @subtype.setter
    def subtype(self, value: str):
        self._subtype = value

    @property
    def fileData(self) -> bytes:
        return self._fileData
    
    @fileData.setter
    def fileData(self, value: bytes):
        self._fileData = value

class EmailAddress(NotificationContact):
    ValidEmailRegex = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,7}"
    def __init__(self, emailAddress: str):
        self.emailAddress = ""
        # Quick check that this is a valid email
        if not re.fullmatch(EmailAddress.ValidEmailRegex, emailAddress):
            raise ValueError(f"Invalid email {emailAddress}")
        else:
            self.emailAddress = emailAddress

    def __str__(self) -> str:
        return self.emailAddress

class EmailNotification(Notification):
    def __init__(self, 
                 type: NotificationType, 
                 sender: EmailAddress, 
                 receiver: EmailAddress, 
                 message: str,
                 subject: str = ""):
        super().__init__(EMAIL_BACKEND, type, sender, receiver, message)

        self._subject = subject
        self.attachedFiles: List[Path] = []
        self._attachments: List[EmailAttachment] = []

    @property
    def subject(self) -> str:
        return self._subject
    
    @subject.setter
    def subject(self, value: str):
        self._subject = value

    def attachFile(self, filepath: Path):
        self.attachedFiles.append(filepath)

    def totalAttachmentsSize(self) -> int:
        totalSize = 0

        for attachment in self._attachments:
            totalSize += len(attachment.fileData)

        return totalSize
    
    def processFileAttachments(self):

        self._attachments.clear()
        for filepath in self.attachedFiles:
            filename = filepath.name
            ctype, encoding = mimetypes.guess_type(filename)

            # If mime is unknown fall back
            mainType, subtype = ("application", "octet-stream") if ctype is None else tuple(ctype.split("/"))

            with open(filepath, "rb") as fp:
                fileData = fp.read()

                self._attachments.append(EmailAttachment(
                    filename,
                    mainType,
                    subtype,
                    fileData
                ))


class EmailBackend(Backend):
    GMAIL_SMTP      = "smtp.gmail.com"
    PORT_SMTP       = 587 # Use SSL by default 
    DISABLE_TIMEOUT = None

    def __init__(self,
                 username: secret.Secret, 
                 password: secret.Secret,
                 smtpAddr: str = GMAIL_SMTP, 
                 smtpPort: int = PORT_SMTP,
                 timeout: Optional[float] = DISABLE_TIMEOUT,
                 maxAttachSize: int = 25 * 1025 * 1024 # 25 MB limit on send
                 ):
        
        super().__init__(EMAIL_BACKEND)

        self.username       = username
        self.password       = password
        self.smtpAddr       = smtpAddr
        self.smtpPort       = smtpPort
        self.timeout        = timeout
        self.maxAttachSize  = maxAttachSize

        self.lazyLoad = True
        self.client : Optional[aiosmtplib.SMTP] = None
        

    async def __connect(self):
        if not self.username.isEmpty() and not self.password.isEmpty():
            try:
                context = ssl.create_default_context()
                self.client = aiosmtplib.SMTP(
                    hostname=self.smtpAddr,
                    port=self.smtpPort,
                    timeout=self.timeout,
                    tls_context=context,
                    start_tls=True
                )

                await self.client.connect()
                await self.client.login(self.username.expose(), self.password.expose())

            except Exception as e:
                self.client = None
                raise Exception(f"Unable to connect to mail provider at {self.smtpAddr} on {self.smtpPort}.")
        else:
            raise Exception(f"GMail username or password are undefined.")


    async def load(self):

        # Don't initiate connection unless it's needed if lazy load is set
        # SMTP server will disconnect if idle for too long.
        if not self.lazyLoad:
            await self.__connect()
    
    async def unload(self):

        # Disconnect if client is initialized and hasn't timed out yet
        if self.client is not None and self.client.is_connected:
            try:
                await self.client.quit()
            except Exception as e:
                raise Exception("Unable to clean up SMTP client at {self.smtpAddr} on {self.smtpPort}.")
            
        self.client = None
    
    def __genTemplate(self, notification: EmailNotification, supportContact: SupportContact, message: EmailMessage):
        # Render content using template
        renderer = NotificationRenderer(supportContact)
        template = renderer.render(notification.type,
                        str(notification.receiver),
                        notification.subject,
                        notification.message)
        
        # Attach both text and html. Clients can use whichever is preferred.
        message.set_content(template.body)
        message.add_alternative(template.html, subtype="html")

    
    # Enqueue notifications
    async def send(self, notification: Notification, supportContact: SupportContact):

        # Reconnect if connection was lost or not initialized
        if self.client is None or not self.client.is_connected:
            await self.__connect() 

        # Sanity check. Notification Mgr should be dispatching notifications to the appropriate handler.
        if type(notification) is EmailNotification and self.client is not None:
            emailNotification: EmailNotification = notification

            # Handle attachments up front in case we exceeded max size
            emailNotification.processFileAttachments()
            totalAttachmentSize = emailNotification.totalAttachmentsSize()
            if totalAttachmentSize > self.maxAttachSize:
                raise Exception(f"Attachment(s) total size {totalAttachmentSize} exceeded maximum allowed of {self.maxAttachSize}.")
            
            # Format the message
            message = EmailMessage()
            message["From"]     = str(emailNotification.sender)
            message["To"]       = str(emailNotification.receiver)
            message["Subject"]  = emailNotification.subject

            # Notify other listeners without revealing all recipients
            if len(emailNotification.others) > 0:
                message["Bcc"]  = ", ".join(map(str, emailNotification.others))
            
            # Standard headers
            message["Date"]     = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")

            self.__genTemplate(notification, supportContact, message)

            try:
                await self.client.send_message(message)
            except aiosmtplib.SMTPSenderRefused:
                # 'is_connected' doesn't guarantee we're still connected to the server.
                # If it's a timeout reconnect and error try again.
                await self.__connect()
                await self.client.send_message(message)

        elif self.client is None:
            raise ValueError("SMTP client is not initialized.")
        else:
            raise ValueError("The notification given is not an email notification.")

            


