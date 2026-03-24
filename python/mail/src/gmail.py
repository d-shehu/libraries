import imaplib
import email

from email.policy   import default
from email.utils    import parsedate_to_datetime
from typing         import cast, List, Optional, Tuple

# This package
from .mail          import Mail, MailFilter, MailProvider, MailCredentials

class MailMsg:
    def __init__(self, rawMail):
        self.msg        = email.message_from_bytes(rawMail, policy=default)
        self.bodyText   = ""
        self.bodyHTML   = ""

        self.__getBody()

    def __getitem__(self, key: str) -> str:
        val = self.msg.get(key)
        return val if val is not None else ""
    
    def __getBody(self):
        # Extract body
        if self.msg.is_multipart():
            for part in self.msg.walk():
                content_type = part.get_content_type()
                disposition = part.get_content_disposition()

                if disposition == "attachment":
                    continue

                if content_type == "text/plain":
                    self.bodyText = part.get_content()

                elif content_type == "text/html":
                    self.bodyHTML = part.get_content()

        else:
            self.bodyText = self.msg.get_content()
    
    def to_Mail(self) -> Mail:
        return Mail(
            self["Message-ID"],
            parsedate_to_datetime(self["Date"]),
            self["From"],
            self["To"],
            self["Cc"],
            self["Bcc"],
            self["Reply-To"],
            self["Subject"],
            self.bodyText,
            self.bodyHTML
        )

class GMail(MailProvider):
    HOST = "imap.gmail.com"
    TLS_PORT = 993

    def __init__(self):
        super().__init__("GMail", GMail.HOST, GMail.TLS_PORT)
        self.connection: Optional[imaplib.IMAP4_SSL] = None
        self.credentials: Optional[MailCredentials] = None
    

    def connect(self, credentials: MailCredentials) -> bool:
        success = False

        self.credentials = credentials
        self.connection = imaplib.IMAP4_SSL(self.host, self.port)
        if self.connection is not None:
            ret, data = self.connection.login(self.credentials.username.expose(), 
                                    self.credentials.password.expose())
            
            success = ret == "OK"
            
        return success

    def disconnect(self) -> bool:
        success = False

        if self.connection:
            # Try to close connection safely
            try:
                if getattr(self.connect, "state", "") == "SELECTED":
                    self.connection.close()
            except imaplib.IMAP4.error as e:
                raise Exception(f"Unable to close IMAP: {e}")
                
            # Attempt to logout
            try:
                self.connection.logout()
                success = True
            except Exception as e:
                raise Exception(f"Unable to log out from IMAP: {e}")
            
        return success
    
    @staticmethod
    def __getMsgField(msg, field: str) -> str:
        val = msg.get(field)
        return val if val is not None else ""

    def __fetchMessage(self, id) -> Mail:
        if self.connection is not None:
            typ, msgData = self.connection.fetch(id, "(RFC822)")
            if typ != "OK" or msgData is None:
                raise Exception(f"Unable to fetch mail with id {id}")
            
            if msgData is not None:
                dataList = cast(List[Tuple[bytes, bytes]], msgData)
                rawEmail = MailMsg(dataList[0][1])

                return rawEmail.to_Mail()
            else:
                raise Exception("Unable to extract email from raw message data")
        else:
            raise Exception("Can't get email as connection is not initialized.")


    def search(self, filter: MailFilter) -> List[Mail]:
        lsMatches: List[Mail] = []

        if self.connection is None:
            raise Exception("Connection to gmail not initialized.")
        elif filter.expression == "":
            raise Exception("Filter must be non empty.")
        else:
            res,data = self.connection.select(filter.mailbox)
            if res != "OK":
                raise Exception(f"Unable to select mailbox {filter.mailbox} due to {data}")

            res,data = self.connection.search(None, filter.expression)
            if res == "OK" and data[0]:
                ids = data[0].split()

                for id in ids:
                    message = self.__fetchMessage(id)
                    lsMatches.append(message)
        
        return lsMatches
            