import json
import time

# Local packages
from abc            import ABC, abstractmethod
from core           import user_module, logs
from my_secrets     import secrets_mgr

# This package
from .llm_define    import *

class LLMModel(ABC):
    def __init__(self, info: LLMInfo, logger, variant: str = "", verboseOutput: bool = False):
        self.info          = info
        self.logger        = logger
        self.variant       = variant
        self.verboseOutput = verboseOutput

    def connectToClient(self, secretsMgr: secrets_mgr.SecretsMgr) -> bool:
        raise Exception("LLMModel's connectToClient must be overriden in child class.")

    def chat(self, messages: List[LLMMessage], outputFormat = None) -> str:
        answer = ""
        
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
                answer = outputFormatJSON.model_validate_json(firstMessage.content)
            else:
                answer = firstMessage.content

            elapsed = time.time() - start
            if self.verboseOutput:
                self.logger.debug(f"Query took: {elapsed}s")

        except Exception as e:
            self.logger.exception("Enable to send message to client.")

        return answer

    def _getModelHandle(self) -> str:
        modelHandle: str = self.info.name
        if self.variant != "":
            modelHandle = modelHandle + ":" + self.variant
            
        return modelHandle

    @abstractmethod
    def _parseResponse(self, response: dict) -> LLMResponse:
        pass
        
    @abstractmethod
    def _doChat(self, messages: List[LLMMessage], responseFormatJson = None) -> dict:
        pass

    @abstractmethod
    def _countTokens(self, content) -> int:
        pass

    def getTokenCountFromMessages(self, messages: List[LLMMessage]) -> int:
        totalTokenCount = 0

        if self.verboseOutput:
            self.logger.debug(LogLine("Count tokens for num messages: ", len(messages)))

        for message in messages:
            totalTokenCount += self._countTokens(message.content)

        return totalTokenCount