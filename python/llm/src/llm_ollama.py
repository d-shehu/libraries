import json
import io
import os
import numpy as np

from dataclasses    import dataclass
from requests       import Request, Response, Session
from transformers   import AutoTokenizer
from typing         import List, Optional

# Local packages
from my_secrets     import secrets_mgr

# This package
from .llm_define    import LogLine, LLMInfo, LLMMessage, LLMResponse, LLMResponseStatus
from .llm_model     import LLMModel, LLMParams

@dataclass
class OllamaParams:
    # Some confusion in docs on the default value. 
    # To avoid issues with truncated responses set this to -1 (unlimited) explicitly.
    num_predict = -1
    # Maximum context allowed via API. 0 indicates no limit.
    num_ctx = 0

# While using Ollama python package, I ran into inconsistent results
# when compared to calling APIs directly using Postman or curl. 
# Sometimes output is significantly different, unusable or there is a
# significant increase in memory usage. 
class OllamaClient:
    def __init__(self, host: str, port: int, logger, api_key: secrets_mgr.Secret, verboseOutput: bool = False):
        self.host           = host
        self.port           = port
        self.logger         = logger
        self.api_key        = api_key
        self.session        = Session()
        self.verboseOutput  = verboseOutput

    def __del__(self):
        self.session.close()

    def __sendRequest(self, model: str, messages: List[dict], options: dict) -> Response:
        headers = {}
        if not self.api_key.isEmpty():
            headers["Authorization"] = f"Bearer {self.api_key.expose()}"
        headers["Content-Type"] = "application/json"

        # TODO: remove this
        options["context"] = 32768

        # Zero-shot, client is responsible for managing chat history.
        url = f"{self.host}:{self.port}/api/chat"
        ollamaRequest = Request("POST", url, headers, json = {
            "model":        model,
            "messages":     messages,
            "stream":       True,
            #"format":       "json",
            "keep_alive":   "5m",
            "options":      options
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

        response = self.session.send(preparedRequest, stream=True)

        return response

    def sendMessages(self, model: str, messages: List[dict], options: dict) -> dict:
        
        response = self.__sendRequest(model, messages, options)

        responseJSON = None
        role = None
        contentBuffer = io.StringIO()

        for rawLine in response.iter_lines(decode_unicode=True):
            if not rawLine:
                continue

            chunk = json.loads(rawLine)

            if "message" in chunk:
                chunkedMessage = chunk["message"]

                if role is None:
                    role = chunkedMessage["role"]
                    contentBuffer.write(chunkedMessage["content"])
                elif chunkedMessage["role"] == role:
                    contentBuffer.write(chunkedMessage["content"])
                else:
                    raise Exception("Unexpected change in 'role' while streaming messages from ollama.")
                
                # Is chunking complete?
                if "done" in chunk:
                    if chunk.get("done"):
                        responseJSON = chunk # Last response should be complete
                        responseJSON["message"]["content"] = contentBuffer.getvalue() # Copy the full msg contents
                        break
                else:
                    raise Exception("Chunked message from Ollama missing 'done' field.")
            else:
                raise Exception("Chunked response from Ollama missing 'message'.")

        contentBuffer.close()
        
        if responseJSON is None:
            raise Exception("Incomplete JSON response received from Ollama API.")

        if isinstance(responseJSON, dict):
            if self.verboseOutput:
                self.logger.debug("Response from Ollama: ")
                self.logger.debug(LogLine("Type of Ollama: ", type(responseJSON)))
                self.logger.debug(LogLine(responseJSON))
        else:
            raise Exception("Expected the Ollama response type to be dictionary.")
            
        return responseJSON
        
class OllamaModel(LLMModel):
    DEFAULT_OLLAMA_CONTEXT_LEN: int = 2048
    
    def __init__(self, info: LLMInfo, logger, variant: str, verboseOutput: bool = False):
        super().__init__(info, logger, variant, verboseOutput)

        self.ollamaParams = OllamaParams()
        self.client: Optional[OllamaClient] = None

        # TODO: configure this via param
        self.maxContextLength = self.info 
        
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
            
    def __init_tokenizer(self, hfToken: secrets_mgr.Secret):
        modelName = self.info["name"]
        saveDir = os.path.expanduser(f"~/models/{modelName}-tokenizer")
        if not os.path.isdir(saveDir):
            if self.verboseOutput:
                self.logger.debug(LogLine("Downloading tokenizer model: ", self.info["tokenizer"]))
            self.tokenizer = AutoTokenizer.from_pretrained(self.info["tokenizer"], token=hfToken.expose())
            self.tokenizer.save_pretrained(os.path.expanduser(saveDir))
        else:
            if self.verboseOutput:
                self.logger.debug(LogLine("Tokenizer model on disk: ", self.info["tokenizer"]))
            self.tokenizer = AutoTokenizer.from_pretrained(saveDir)
        
    def connectToClient(self, secretsMgr: secrets_mgr.SecretsMgr) -> bool:
        success = False
        
        try:
            if self.client is not None:
                del self.client

            if self.verboseOutput:
                self.logger.info("Connecting to Ollama client...")

            ollamaHost  = secretsMgr.getSecret("OLLAMA_API_HOST")
            ollamaPort  = secretsMgr.getSecret("OLLAMA_API_PORT")
            ollamaKey   = secretsMgr.getSecret("OLLAMA_API_KEY")
            hfToken     = secretsMgr.getSecret("HUGGING_FACE_TOKEN")

            if (ollamaHost is not None 
                and ollamaPort is not None 
                and ollamaKey is not None 
                and hfToken is not None):

                self.client = OllamaClient(
                    ollamaHost.expose(), 
                    int(ollamaPort.expose()),
                    self.logger, 
                    ollamaKey, 
                    self.verboseOutput)
                
                self.__init_tokenizer(hfToken)

                success = True # If not exception assume it worked
            else:
                self.logger.error("Unable to connect to Ollama. Check OLLAMA_API_HOST, OLLAMA_API_PORT, OLLAMA_API_KEY and HUGGING_FACE_TOKEN")
            
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
        

    def _parseResponse(self, response: dict) -> LLMResponse:
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
        
    def _doChat(self, messages: List[LLMMessage], responseFormatJson = None) -> dict:
        response = {}

        if self.verboseOutput:
            self.logger.debug(LogLine("Chatting with Ollama model " + self._getModelHandle()))

        # Ollama specific option not supported with OpenAI API.
        self.options.num_ctx = self.__calculateContextLen(messages)                
        if self.verboseOutput:
            self.logger.debug(f"Context length set to {self.options.num_ctx}")
            self.logger.debug(f"Options: {self.options.__dict__}")

        if self.client is not None:
            response = self.client.sendMessages(
                model = self._getModelHandle(), 
                messages = list(map(lambda obj: obj.__dict__, messages)), # Array of dict, 
                options = self.options.__dict__ # Convert to dict
            )
        else:
            self.logger.error("LLM client is not defined or initialized.")

        return response