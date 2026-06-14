from enum import Enum

class ProgramMode(Enum):
    Interactive = "interactive"
    Command     = "command"
    Service     = "service"
    Undefined   = ""