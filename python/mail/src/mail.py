from abc            import ABC, abstractmethod
from datetime       import datetime
from dataclasses    import dataclass
from typing         import List

# Local packages
from my_secrets     import secret
from utilities      import validators

@dataclass
class MailCredentials:
    username: secret.Secret
    password: secret.Secret

@dataclass
class Mail:
    id:         str
    sent:       datetime
    From:       str
    to:         str
    cc:         str
    bcc:        str
    replyTo:    str
    subject:    str
    bodyText:   str
    bodyHTML:   str

    def isEmpty(self) -> bool:
        return (self.id == "" 
                and self.sent == ""
                and self.From == ""
                and self.to == ""
                and self.cc == ""
                and self.bcc == ""
                and self.replyTo == ""
                and self.subject == ""
                and self.bodyText == ""
                and self.bodyHTML == "")

    def isValid(self) -> bool:
        # From, to must be valid and there must be a subject and body.
        return (validators.Validator.IsValidEmailList(self.From, False) 
                and validators.Validator.IsValidEmailList(self.to, False)
                and validators.Validator.IsValidEmailList(self.cc, True)
                and validators.Validator.IsValidEmailList(self.bcc, True)
                and validators.Validator.IsValidEmailList(self.replyTo, True)
                and self.subject != "" and (self.bodyText != "" or self.bodyHTML != ""))

# TODO: generalize in the future to abstract IMAP specific implementation
class MailFilter:
    def __init__(self, mailbox: str = "INBOX"):
        self.__mailbox = mailbox
        self.__expr = ""
        
    @property
    def mailbox(self) -> str:
        return self.__mailbox
    
    @mailbox.setter
    def inbox(self, value: str):
        self.__mailbox = value

    @property
    def expression(self) -> str:
        return self.__expr

    @expression.setter
    def expression(self, expression: str):
        self.__expr = expression

class MailProvider(ABC):
    def __init__(self, type: str, host: str, port: int):
        self.type = type
        self.host = host
        self.port = port

    @abstractmethod
    def connect(self, credentials: MailCredentials) -> bool:
        pass

    @abstractmethod
    def disconnect(self):
        pass

    @abstractmethod
    def search(self, filter: MailFilter) -> List[Mail]:
        pass
