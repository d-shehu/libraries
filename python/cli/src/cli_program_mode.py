from enum import Enum

class CLIProgramMode(Enum):
    Interactive = "interactive"
    Command     = "command"
    Service     = "service"
    Undefined   = ""