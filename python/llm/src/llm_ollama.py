from transformers   import AutoTokenizer

import os
import numpy as np
import requests

# Local files
from .llm_define    import LogLine, LLMInfo, LLMMessage, LLMResponse, LLMResponseStatus
from .llm_model     import LLMModel

# While using Ollama python package, I ran into inconsistent results
# when compared to calling APIs directly using Postman or curl. 
# Sometimes output is significantly different, unusable or there is a
# significant increase in memory usage. 
class OllamaClient:
    def __init__(self, host: str, port: int, logger, api_key: str = "", verboseOutput: bool = False):
        self.host           = host
        self.port           = port
        self.logger         = logger
        self.api_key        = api_key
        self.session        = requests.Session()
        self.verboseOutput  = verboseOutput

    def __del__(self):
        self.session.close()

    def sendMessages(self, model, messages, options) -> str:
        headers = {}
        if self.api_key != "":
            headers["Authorization"] = f"Bearer {self.api_key}"
        headers["Content-Type"] = "application/json"

        # Zero-shot, client is responsible for managing chat history.
        url = f"{self.host}:{self.port}/api/chat"
        ollamaRequest = requests.Request("POST", url, headers, json = {
            "model":    model,
            "messages": messages,
            "stream":   False,
            "format":   "json",
            "options":  options
        })

        preparedRequest = ollamaRequest.prepare()

        if self.verboseOutput:
            self.logger.debug("Sending request to Ollama:")
            self.logger.debug(f"URL: {preparedRequest.url}")
            self.logger.debug(f"Method: {preparedRequest.method}")
            self.logger.debug("Headers:")
            for header, value in preparedRequest.headers.items():
                self.logger.debug(f"  {header}: {value}")
            self.logger.debug(f"Body: {preparedRequest.body}")
            self.logger.debug("")

        response = self.session.send(preparedRequest)

        responseJSON = response.json()
        if self.verboseOutput:
            self.logger.debug("Response from Ollama: ")
            self.logger.debug(LogLine("Type of Ollama: ", type(responseJSON)))
            self.logger.debug(LogLine(responseJSON))
            
        return responseJSON
        
class OllamaModel(LLMModel):
    DEFAULT_OLLAMA_CONTEXT_LEN: int = 2048
    
    def __init__(self, info, logger, tag, verboseOutput = False):
        super().__init__(info, logger, tag, verboseOutput)

        self.client: Optional[OllamaClient] = None

        # TODO: configure this via param
        self.maxRecommendedContextLength = 8192
        # Some confusion in docs on the default value. 
        # To avoid issues with truncated responses set this to -1 explicitly.
        self.options.num_predict = -1 
        
        # Ollama API defaults to 4K context length default 
        # but many models support much larger context.
        # For all supported models set the highest supported
        # context. But the actual context will be determined
        # dynamically based on content.
        if self.info == LLMInfo.COMMAND_R:
            self.maxModelContextLength = 131072 # 128K model
        elif self.info == LLMInfo.GEMMA2:
            self.maxModelContextLength = 8192
        elif self.info == LLMInfo.GEMMA3:
            self.maxModelContextLength = 8192
        elif self.info == LLMInfo.LLAMA31:
            self.maxModelContextLength = 131072
        else:
            self.maxModelContextLength = OllamaModel.DEFAULT_OLLAMA_CONTEXT_LEN # Ollama's default
            raise Exception(f"Error: unknown model: {self.info}. Context window may be incorrect")
            
    def __init_tokenizer(self, secrets):
        modelName = self.info["name"]
        saveDir = os.path.expanduser(f"~/models/{modelName}-tokenizer")
        if not os.path.isdir(saveDir):
            if self.verboseOutput:
                self.logger.debug(LogLine("Downloading tokenizer model: ", self.info["tokenizer"]))
            self.tokenizer = AutoTokenizer.from_pretrained(self.info["tokenizer"], token=secrets["HUGGING_FACE_TOKEN"])
            self.tokenizer.save_pretrained(os.path.expanduser(saveDir))
        else:
            if self.verboseOutput:
                self.logger.debug(LogLine("Tokenizer model on disk: ", self.info["tokenizer"]))
            self.tokenizer = AutoTokenizer.from_pretrained(saveDir)
        
    def connectToClient(self, secrets) -> bool:
        success = False
        
        try:
            if self.client is not None:
                del self.client

            if self.verboseOutput:
                self.logger.info("Connecting to Ollama client...")

            self.client = OllamaClient(
                secrets["OLLAMA_API_HOST"], 
                secrets["OLLAMA_API_PORT"],
                self.logger, 
                secrets["OLLAMA_API_KEY"], 
                self.verboseOutput)
            
            self.__init_tokenizer(secrets)
            
            success = True
        except Exception as e:
            self.logger.exception("Unable to connect to Ollama")

        return success

    def _countTokens(self, contents) -> int:
        return len(self.tokenizer.tokenize(contents))

    def __calculateContextLen(self, messages):
        numTokens = self.getTokenCountFromMessages(messages)
        if numTokens > self.maxModelContextLength:
            self.logger.warning("Content length is greater than model context.")
        if numTokens > self.maxRecommendedContextLength:
            self.logger.warning("Content lenght is greater than recommended context.")

        # Nearest power of 2 that is greater than actual number of tokens.
        # However no greater than max recommended or model context length and no less
        # than Ollama default to avoid unpredictable behavior or running out of memory.
        contextLen = 2 ** (int(np.emath.logn(2, numTokens)) + 1)
        if contextLen >= self.maxRecommendedContextLength or contextLen >= self.maxModelContextLength:
            contextLen = min(self.maxRecommendedContextLength, self.maxModelContextLength)
        elif contextLen < self.DEFAULT_OLLAMA_CONTEXT_LEN:
            contextLen = self.DEFAULT_OLLAMA_CONTEXT_LEN

        return contextLen
        

    def _parseResponse(self, response) -> LLMResponse:
        parsedResponse = LLMResponse()

        try:            
            parsedResponse.model = response["model"]
            # Simplifying status since this is non-streaming and synchronous.
            if response["done"] == True and response["done_reason"] == "stop":
                parsedResponse.status = LLMResponseStatus.SUCCEEDED
            else:
                parsedResponse.status = LLMResponseStatus.FAILED
                
            # TODO: revisit this. Ollama returns a single response
            message = response["message"]
            parsedResponse.messages = [ LLMMessage(message["role"], message["content"]) ]
        except Exception as e:
            parsedResponse.status = LLMResponseStatus.FAILED
            self.logger.exception("Exception encountered while trying to parse response.")

        return parsedResponse
        
    def _doChat(self, messages, responseFormatJson = None):

        if self.verboseOutput:
            self.logger.debug(LogLine("Chatting with Ollama model " + self._getModelHandle()))

        # Ollama specific option not supported with OpenAI API.
        self.options.num_ctx = self.__calculateContextLen(messages)                
        if self.verboseOutput:
            self.logger.debug(f"Context length set to {self.options.num_ctx}")
            self.logger.debug(f"Options: {self.options.__dict__}")

        response = self.client.sendMessages(
            model = self._getModelHandle(), 
            messages = list(map(lambda obj: obj.__dict__, messages)), # Array of dict, 
            options = self.options.__dict__ # Convert to dict
        )

        return response