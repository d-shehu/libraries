import time

# User packages
from abc            import ABC, abstractmethod
from core           import user_module, logs

# Local files
from .llm_define    import *

# A few key parameters for tweaking LLM performance.
class LLMOptions:
    def __init__(self):
        self.seed           = None
        self.temperature    = 1.0
        self.top_p          = 0.9
        self.top_k          = 40
        self.repeat_penalty = 1.1

    # Defaulting to more conservative and deterministic
    # values.
    def setConservative(self):
        self.seed           = None
        self.temperature    = 0.1
        self.top_p          = 0.9
        self.top_k          = 30
        self.repeat_penalty = 1.2

    def setDeterministic(self):
        self.seed           = 42 # Hard-code seed to make it more deterministic
        self.temperature    = float(0)
        self.top_p          = 0
        self.top_k          = 1
        self.repeat_penalty = 1.2

class LLMModel(ABC):
    def __init__(self, info: LLMInfo, logger, tag: str = "", verboseOutput: bool = False):
        self.info          = info
        self.logger        = logger
        self.tag           = tag
        self.verboseOutput = verboseOutput
        self.options       = LLMOptions()

    def connectToClient(self, secrets) -> bool:
        raise Exception("LLMModel's connectToClient must be overriden in child class.")

    def chat(self, messages: List[LLMMessage], outputFormat = None) -> str:
        answer = None
        
        try:
            start = time.time()

            outputFormatJSON = None
            if outputFormat is not None:
                outputFormatJSON = outputFormat.model_json_schema()

            if self.verboseOutput:
                self.logger.debug("Messages sent: ")
                for message in messages:
                    self.logger.debug(f"Role: message.role")
                    self.logger.debug(f"Content: message.content")
    
            response = self._doChat(messages, outputFormatJSON) # Actually send the request and get response
            if self.verboseOutput:
                self.logger.debug(LogLine("Response: ", response))
            parsedResponse = self._parseResponse(response)
            
            # TODO: revisit how to handle multiple responses. Not to be confused with streaming.
            firstMessage = parsedResponse.messages[0]

            if outputFormatJSON is not None:
                if self.verboseOutput:
                    self.logger.debug(LogLine("Response content: ", json.dumps(firstMessage.content, indent = 4)))
                answer = outputFormat.model_validate_json(firstMessage.content)
            else:
                answer = firstMessage.content

            elapsed = time.time() - start
            if self.verboseOutput:
                self.logger.debug(f"Query took: {elapsed}s")

        except Exception as e:
            self.logger.exception("Enable to send message to client.")

        return answer

    def _getModelHandle(self) -> str:
        modelHandle: str = self.info["name"]
        if self.tag != "":
            modelHandle = modelHandle + ":" + self.tag
            
        return modelHandle

    @abstractmethod
    def _parseResponse(self, response) -> LLMResponse:
        pass
        
    @abstractmethod
    def _doChat(self, messages: List[LLMMessage], responseFormatJson = None):
        pass

    @abstractmethod
    def _countTokens(self, content) -> int:
        pass

    def getTokenCountFromMessages(self, messages) -> int:
        totalTokenCount = 0

        if self.verboseOutput:
            self.logger.debug(LogLine("Count tokens for num messages: ", len(messages)))
        for message in messages:
            totalTokenCount += self._countTokens(message.content)

        return totalTokenCount