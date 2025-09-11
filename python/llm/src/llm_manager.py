
from typing         import Dict, Optional

# User module and logging
from core           import user_module, logs

# Local files
from .llm_define    import *
from .llm_model     import LLMModel
from .llm_openai    import OpenAIModel
from .llm_ollama    import OllamaModel
        
class LLMManager(user_module.UserModule):
    def __init__(self, clientType: LLMClientType, info: LLMInfo, tag: str = "", verboseOutput: bool = False, 
                 logMgr = logs.ConfigureConsoleOnlyLogging("LLMManagerLogger")
                ):
        super().__init__(logMgr)
        
        self.clientType     = clientType
        self.verboseOutput  = verboseOutput
        
        self.llmModel: Optional[LLMModel] = None
        if clientType == LLMClientType.OLLAMA:
            self.llmModel = OllamaModel(info, self.logger, tag, verboseOutput)
        elif clientType == LLMClientType.OPENAI:
            self.llmModel = OpenAIModel(info, self.logger, tag, verboseOutput)
        else:
            self.logger.error(LogLine("Unknown client type: ", clientType))

    def __del__(self):
        del self.llmModel
    
    # TODO: replace secrets with apiKey to restrict access
    def connectToClient(self, secrets: dict) -> bool:
        success = False
        
        try:
            if self.llmModel is not None:
                success = self.llmModel.connectToClient(secrets)
            else:
                self.logger.error("llm model was not initialized.")
        except Exception as e:
            self.logger.exception("Could not load job search secrets")
    
        return success

    def chat(self, prompt, context: Optional[List[LLMMessage]] = None, role = "user", responseFormat = None) -> str:
        # Capture earlier conversations
        messagesToSend: List[LLMMessage] = []
        if context is not None:
            messagesToSend = context
    
        # Append new prompt
        messagesToSend.append(LLMMessage(role, prompt))

        if self.verboseOutput:
            self.logger.debug(LogLine("Estimated input token count: ", 
                                      self.llmModel.getTokenCountFromMessages(messagesToSend)))

        answer = self.llmModel.chat(messagesToSend, responseFormat)

        # TODO: clean this up
        if self.verboseOutput and answer is not None:
            self.logger.debug(LogLine("Estimated output token count: ", 
                              self.llmModel.getTokenCountFromMessages([LLMMessage("assistant", answer)])))

        return answer