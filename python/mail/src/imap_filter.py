from datetime           import datetime,timezone
from enum               import Enum
from typing             import Optional, Tuple

# Defines
INVALID_DATETIME = datetime.min.replace(tzinfo=timezone.utc)   # 0001-01-01T00:00:00+00:00

class IMAPStatusType(Enum):
    UNDEFINED   = ""
    ALL         = "ALL"
    ANSWERED    = "ANSWERED"
    DELETED     = "DELETED"
    DRAFT       = "DRAFT"
    FLAGGED     = "FLAGGED"
    NEW         = "NEW"
    OLD         = "OLD"
    RECENT      = "RECENT"
    SEEN        = "SEEN"
    UNANSWERED  = "UNANSWERED"
    UNDELETED   = "UNDELETED"
    UNDRAFT     = "UNDRAFT"
    UNFLAGGED   = "UNFLAGGED"
    UNSEEN      = "UNSEEN"

class IMAPTargetType(Enum):
    UNDEFINED   = ""
    FROM        = "FROM"
    TO          = "TO"
    CC          = "CC"
    BCC         = "BCC"

class IMAPContentType(Enum):
    UNDEFINED   = ""
    SUBJECT     = "SUBJECT"
    BODY        = "BODY"
    TEXT        = "TEXT" # Header or body
    KEYWORD     = "KEYWORD"

class IMAPDateType(Enum):
    UNDEFINED   = ""
    BEFORE      = "BEFORE"
    ON          = "ON"
    SINCE       = "SINCE"


class IMAPFilterCriteria:
    def __init__(self):
        self.__status           = IMAPStatusType.UNDEFINED
        self.__target           = (IMAPTargetType.UNDEFINED, "")
        self.__contains         = (IMAPContentType.UNDEFINED, "")
        self.__messageDate      = (IMAPDateType.UNDEFINED, INVALID_DATETIME)
        self.__sentDate         = (IMAPDateType.UNDEFINED, INVALID_DATETIME)

    @property
    def status(self) -> IMAPStatusType:
        return self.__status
    
    @status.setter
    def status(self, value: IMAPStatusType):
        self.__status = value

    @property
    def target(self) -> Tuple[IMAPTargetType, str]:
        return self.__target
    
    @target.setter
    def target(self, value: Tuple[IMAPTargetType, str]):
        self.__target = value 

    @property
    def contains(self) -> Tuple[IMAPContentType, str]:
        return self.__contains
    
    @contains.setter
    def contains(self, value: Tuple[IMAPContentType, str]):
        self.__contains = value

    @property
    def messageDate(self) -> Tuple[IMAPDateType, datetime]:
        return self.__messageDate
    
    @messageDate.setter
    def messageDate(self, value: Tuple[IMAPDateType, datetime]):
        self.__messageDate = value

    @property
    def sentDate(self) -> Tuple[IMAPDateType, datetime]:
        return self.__sentDate
    
    @sentDate.setter
    def sentDate(self, value: Tuple[IMAPDateType, datetime]):
        self.__sentDate = value

    # Get string representation
    def __str__(self) -> str:
        expr = "" if self.__status == IMAPStatusType.UNDEFINED else self.__status.value

        # If multiple properties set they are treated as AND
        if self.__target[0] != IMAPTargetType.UNDEFINED:
            expr += " " + self.__target[0].value + " \"" + self.__target[1] + "\""

        if self.__contains[0] != IMAPContentType.UNDEFINED:
            expr += " " + self.__contains[0].value + " \"" + self.__contains[1] + "\""

        if self.__messageDate[0] != IMAPDateType.UNDEFINED:
            expr += " " + self.__messageDate[0].value + " " + self.__messageDate[1].strftime('%d-%b-%Y')

        if self.__sentDate[0] != IMAPDateType.UNDEFINED:
            expr += " SENT" + self.__sentDate[0].value + " " + self.__sentDate[1].strftime('%d-%b-%Y')

        return expr.strip()
    
    def canORCriteria(self) -> bool:
        return True

    def canANDCriteria(self) -> bool:
        return True

class IMAPFilterOperator(Enum):
    AND = "and"
    OR  = "or"
    NOT = "not"

class IMapFilterExpression(IMAPFilterCriteria):
    def __init__(self, 
                 operator: IMAPFilterOperator, 
                 left: IMAPFilterCriteria, 
                 right: Optional[IMAPFilterCriteria] = None):
        
        
        if operator != IMAPFilterOperator.NOT:
            # Right can't be undefined unless unary
            if right is None:
                raise Exception("Invalid binary expression. Right operand undefined.")
            # ORing an AND isn't directly supported by synatx
            elif operator == IMAPFilterOperator.OR and (left.canORCriteria() or right.canORCriteria()):
                raise Exception("Can't 'OR' expressions possibly because they have an AND.")
    
        self.operator   = operator
        self.left       = left
        self.right      = right
        
        
    def canORCriteria(self) -> bool:
        return (self.operator != IMAPFilterOperator.AND)
    
    # Get string representation
    def __str__(self) -> str:
        expr = ""

        if self.operator == IMAPFilterOperator.NOT:
            expr = "NOT " + self.left.__str__()
        elif self.operator == IMAPFilterOperator.OR:
            expr = "OR " + self.left.__str__() + " " + self.right.__str__()
        elif self.operator == IMAPFilterOperator.AND:
            expr = self.left.__str__() + " " + self.right.__str__()
        else:
            raise Exception(f"IMAP operator {self.operator.value} not supported.")
        
        return expr


    