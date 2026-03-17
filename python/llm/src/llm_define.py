from dataclasses    import dataclass
from enum           import Enum
from typing         import cast, List

# Local packages
from core           import logs

# Aliases
LogLine = logs.LogLine

# Defines
LLMParams_Option_Disabled              = -1

class LLMClientType(Enum):
    OLLAMA = "OLLAMA"
    OPENAI = "OPENAI"

# A few key parameters for tweaking LLM performance.
@dataclass
class LLMParams:
    temperature: float      = 1.0
    top_p:float             = 0.9
    top_k:int               = 40
    repeat_penalty:float    = 1.1
    min_p:float             = LLMParams_Option_Disabled
    repeat_penalty:float    = LLMParams_Option_Disabled
    presence_penalty:float  = LLMParams_Option_Disabled
    seed: int               = LLMParams_Option_Disabled
    
    # Setting all options through they may not be relavent for a specific model
    # and especially for the deterministic mode.
    def setConservative(self):
        self = LLMParams()
        self.temperature    = 0.1
        self.top_p          = 0.9
        self.top_k          = 20
        self.repeat_penalty = 1.2

    def setDeterministic(self):
        self = LLMParams()
        self.temperature    = 0.0
        self.top_p          = 1
        self.top_k          = 1
        self.repeat_penalty = 1.2
        self.seed           = 3457 # Hard-coded seed used to stabilize output for testing or if user prefer consistent results.

@dataclass
class LLMInfo:
    name: str
    tokenizer: str
    context: int
    params: LLMParams

    @staticmethod
    def GetDefaultsLLMInfo() -> List["LLMInfo"]:
        return [
            LLMInfo("gemma3",
                    "google/gemma-3-1b-it",
                    131072,
                    LLMParams(
                        temperature=1.0, 
                        top_p=0.95, 
                        top_k=64, 
                        repeat_penalty=1.0, 
                        min_p=0.01
                    )),
            LLMInfo("gpt-oss",
                    "openai/gpt-oss-120b",
                    131072,
                    LLMParams(
                        temperature=1.0,
                        top_p=1.0,
                        top_k=0
                    )),
            LLMInfo("llama3.2",
                     "meta-llama/Llama-3.2-3B",
                     131072,
                     LLMParams(
                        temperature=1.0, 
                        top_p=0.9, 
                        top_k=40, 
                        repeat_penalty=1.1, 
                        min_p=0.01
                    ))
        ]

class LLMMessage:
    def __init__(self, role: str, content: str):
        self.role    = role
        self.content = content

    def to_dict(self) -> dict[str, str]:
        return {
            "role":     self.role,
            "content":  self.content
        }

        
class LLMResponseStatus(Enum):
    UNKNOWN     = 0
    FAILED      = 1
    SUCCEEDED   = 2
    
class LLMResponse:
    def __init__(self):
        self.model: str                     = ""
        self.messages: List[LLMMessage]     = []
        self.status                         = LLMResponseStatus.UNKNOWN