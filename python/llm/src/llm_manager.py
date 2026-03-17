import json

from pathlib        import Path
from typing         import Optional

# Local packages
from core           import user_module, logs
from my_secrets     import secrets_mgr

# This package
from .llm_define    import *
from .llm_model     import LLMModel
from .llm_openai    import OpenAIModel
from .llm_ollama    import OllamaModel
        
class LLMManager(user_module.UserModule):
    def __init__(self, 
                 clientType: LLMClientType, 
                 model: str, 
                 variant: str,
                 customLLMParamsFilepath: Path = Path(), 
                 verboseOutput: bool = False, 
                 logMgr = logs.ConfigureConsoleOnlyLogging("LLMManagerLogger")
                ):
        
        super().__init__(logMgr)
        
        self.llmInfoLookup: dict[str, LLMInfo] = {}

        self.clientType     = clientType
        self.verboseOutput  = verboseOutput
        
        self.llmModel: Optional[LLMModel] = None
        if clientType == LLMClientType.OLLAMA:
            self.llmModel = OllamaModel(info, self.logger, tag, verboseOutput)
        elif clientType == LLMClientType.OPENAI:
            self.llmModel = OpenAIModel(info, self.logger, tag, verboseOutput)
        else:
            self.logger.error(LogLine("Unknown client type: ", clientType))

    # Override settings if user passes in a configuration file
    # User only needs to specify what to override. All fields optional.
    # {
    #    "models": {
    #        "gemma3": {
    #            "context": 131072
    #            "params": {
    #               "temperature": 1.0
    #               ...
    #           }
    #        }
    #    }
    # }

    def __loadLLMInfo(self, info: LLMInfo, customLLMParamsFilepath: Path):

        # Load defaults first
        for llmInfo in LLMInfo.GetDefaultsLLMInfo():
            self.

        # The format should match LLMInfo
        if customLLMParamsFilepath.exists():
            with open(customLLMParamsFilepath) as paramsFile:
                params = json.load(paramsFile)

                if "models" in params:
                    # If user specified overrides for this info
                    if info.name in params["models"]:
                        modelOverride = params["models"][info.name]
                        # Context set?
                        if "context" in modelOverride:
                            info.value.context = modelOverride["context"]
                        # Params set?
                        if "param" in modelOverride:
                            info.value.params.from_dict(modelOverride["param"])
                else:
                    raise Exception(f"LLM model param file {customLLMParamsFilepath} not properly formatted.")
                
        elif customLLMParamsFilepath != Path():
            raise Exception("User specified filepath for custom LLM parameters is not valid.")

    def __del__(self):
        del self.llmModel
    
    # TODO: replace secrets with apiKey to restrict access
    def connectToClient(self, secretsMgr: secrets_mgr.SecretsMgr) -> bool:
        success = False
        
        try:
            if self.llmModel is not None:
                success = self.llmModel.connectToClient(secretsMgr)
            else:
                self.logger.error("llm model was not initialized.")
        except Exception as e:
            self.logger.exception("Could not load job search secrets")
    
        return success

    def chat(self, prompt, context: Optional[List[LLMMessage]] = None, role = "user", responseFormat = None) -> str:
        answer = ""
        
        # Capture earlier conversations
        messagesToSend: List[LLMMessage] = []
        if context is not None:
            messagesToSend = context
    
        # Append new prompt
        messagesToSend.append(LLMMessage(role, prompt))

        if self.llmModel is not None:
            if self.verboseOutput:
                self.logger.debug(LogLine("Estimated input token count: ", 
                                        self.llmModel.getTokenCountFromMessages(messagesToSend)))

            answer = self.llmModel.chat(messagesToSend, responseFormat)

            # TODO: clean this up
            if self.verboseOutput and answer is not None:
                self.logger.debug(LogLine("Estimated output token count: ", 
                                self.llmModel.getTokenCountFromMessages([LLMMessage("assistant", answer)])))
        else:
            self.logger.error("LLM model is not defined or initialized.")

        return answer