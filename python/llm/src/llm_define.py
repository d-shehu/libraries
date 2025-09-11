from enum           import Enum
from typing         import List, Optional

# User packages
from core           import logs

# Aliases
LogLine = logs.LogLine

class LLMClientType(Enum):
    OLLAMA = "OLLAMA"
    OPENAI = "OPENAI"

class LLMInfo(Enum):
    GPT4O       = {"id": 1, "name": "gpt-4o",    "tokenizer": "gpt-4o"}
    COMMAND_R   = {"id": 2, "name": "command-r", "tokenizer": "CohereForAI/c4ai-command-r-v01"}
    GEMMA2      = {"id": 4, "name": "gemma2",    "tokenizer": "google/gemma-2-2b-it"}
    GEMMA3      = {"id": 3, "name": "gemma3",    "tokenizer": "google/gemma-3-1b-it"}
    LLAMA31     = {"id": 5, "name": "llama3.1",  "tokenizer": "meta-llama/Llama-3.1-8B"}

    def __str__(self):
        return self.value["name"]

    def __getitem__(self, key):
        return self.value[key]
    
def GetLLMInfofromName(name: str) -> LLMInfo:
    for member in LLMInfo:
        if member.value["name"] == name:
            return member
        
    raise IndexError(f"Invalid LLMInfo name {name}")

class LLMMessage:
    def __init__(self, role: str, content: str):
        self.role    = role
        self.content = content

        
class LLMResponseStatus(Enum):
    UNKNOWN     = 0
    FAILED      = 1
    SUCCEEDED   = 2
    
class LLMResponse:
    def __init__(self):
        self.model: str                     = ""
        self.messages: List[LLMMessage]     = []
        self.status                         = LLMResponseStatus.UNKNOWN