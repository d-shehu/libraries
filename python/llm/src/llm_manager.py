from enum import Enum
from datetime import date
import json
from ollama import chat, Client
from openai import OpenAI
import numpy as np
import os
from pydantic import BaseModel
import requests
import sys
import tiktoken
from transformers import AutoTokenizer
import time

# User module and logging
from core import user_module, logs

# Aliases
LogLine = logs.LogLine

class LLMClientType(Enum):
    OLLAMA = 1
    OPENAI = 2

class LLMInfo(Enum):
    GPT4O       = {"id": 1, "name": "gpt-4o",    "tokenizer": "gpt-4o"}
    COMMAND_R   = {"id": 2, "name": "command-r", "tokenizer": "CohereForAI/c4ai-command-r-v01"}
    GEMMA2      = {"id": 4, "name": "gemma2", "tokenizer": "google/gemma-2-2b-it"}
    GEMMA3      = {"id": 3, "name": "gemma3", "tokenizer": "google/gemma-3-1b-it"}
    LLAMA31     = {"id": 5, "name": "llama3.1", "tokenizer": "meta-llama/Llama-3.1-8B"}

    def __getitem__(self, key):
        return self.value[key]

class LLMMessage:
    def __init__(self, role, content):
        self.role    = role
        self.content = content

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

        
class LLMResponseStatus(Enum):
    UNKNOWN     = 0
    FAILED      = 1
    SUCCEEDED   = 2
    
class LLMResponse:
    def __init__(self):
        self.model        = ""
        self.messages     = []
        self.status       = LLMResponseStatus.UNKNOWN

class LLMModel:
    def __init__(self, info, logger, tag = "", verboseOutput = False):
        self.client        = None
        self.info          = info
        self.logger        = logger
        self.tag           = tag
        self.verboseOutput = verboseOutput
        self.options       = LLMOptions()

    def connectToClient(self, secrets) -> bool:
        raise Exception("LLMModel's connectToClient must be overriden in child class.")

    def chat(self, messages, outputFormat = None):
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

    def _getModelHandle(self):
        modelHandle = self.info["name"]
        if self.tag != "":
            modelHandle = modelHandle + ":" + self.tag
            
        return modelHandle

    def _parseResponse(self, response):
        raise Exception("LLMModel's parseResponse must be overriden in child class.")
        
    def _doChat(self, messages, responseFormatJson = None):
        raise Exception("LLMModel's doChat must be overriden in child class.")

    def _countTokens(self, content):
        raise Exception("LLMModel's getTokenizer must be overriden in child class.")

    def getTokenCountFromMessages(self, messages):
        totalTokenCount = 0

        if self.verboseOutput:
            self.logger.debug(LogLine("Count tokens for num messages: ", len(messages)))
        for message in messages:
            totalTokenCount += self._countTokens(message.content)

        return totalTokenCount
        
class OpenAIModel(LLMModel):
    def __init__(self, info, logger, tag = "", verboseOutput = False):
        super().__init__(info, logger, tag, verboseOutput)
        self.encoding = tiktoken.encoding_for_model(info["name"])

    def connectToClient(self, secrets):
        success = False
        
        try:
            if self.client is not None:
                del self.client
                
            self.client = OpenAI(api_key=secrets["OPENAI_API_KEY"])
            
            success = True
        except Exception as e:
            self.logger.exception("Unable to connect to Open AI.")

        return success

    def _countTokens(self, contents):
        return len(self.encoding.encode(contents))

    def _parseResponse(self, response):
        parsedResponse = LLMResponse()

        try:
            parsedResponse.model = response.model    
            # TODO: revisit this. OpenAI may return multiple messages
            firstChoice = response.choices[0]
            # Simplifying status since this is non-streaming and synchronous.
            if firstChoice.finish_reason == "stop":
                parsedResponse.status = LLMResponseStatus.SUCCEEDED
            else:
                parsedResponse.status = LLMResponseStatus.FAILED
                
            message = firstChoice.message
            parsedResponse.messages = [ LLMMessage(message.role, message.content) ]
            
        except Exception as e:
            parsedResponse.status = LLMResponseStatus.FAILED
            self.logger.exception("While trying to parse response.")

        return parsedResponse

    def _doChat(self, messages, responseFormatJson = None):
        if responseFormatJson is not None:
            raise Exception("JSON response not currently supported with Open AI LLM")

        if self.verboseOutput:
            self.logger.debug(LogLine("Chatting with OpenAI model " + self._getModelHandle()))
            
        response = self.client.chat.completions.create(
            model             = self._getModelHandle(),
            messages          = list(map(lambda obj: obj.__dict__, messages)), # Array of dict
            seed              = self.options.seed,  
            temperature       = self.options.temperature,
            top_p             = self.options.top_p,
            frequency_penalty = self.options.repeat_penalty
        )

        return response
    
# While using Ollama python package, I ran into inconsistent results
# when compared to calling APIs directly using Postman or curl. 
# Sometimes output is significantly different, unusable or there is a
# significant increase in memory usage. 
class OllamaClient(LLMModel):
    def __init__(self, url, logger, api_key = "", verboseOutput = False):
        self.url           = url
        self.logger        = logger
        self.api_key       = api_key
        self.session       = requests.Session()
        self.verboseOutput = verboseOutput

    def __del__(self):
        self.session.close()

    def sendMessages(self, model, messages, options):
        headers = {}
        if self.api_key != "":
            headers["Authorization"] = f"Bearer {self.api_key}"
        headers["Content-Type"] = "application/json"

        ollamaRequest = requests.Request("POST", self.url, headers, json = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": options
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
    DEFAULT_OLLAMA_CONTEXT_LEN = 2048
    
    def __init__(self, info, logger, tag, verboseOutput = False):
        super().__init__(info, logger, tag, verboseOutput)

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
            self.maxModelContextLength = DEFAULT_OLLAMA_CONTEXT_LEN # Ollama's default
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
        
    def connectToClient(self, secrets):
        success = False
        
        try:
            if self.client is not None:
                del self.client

            if self.verboseOutput:
                self.logger.info("Connecting to Ollama client...")

            self.client = OllamaClient(secrets["OLLAMA_API_HOST"], self.logger, secrets["OLLAMA_API_KEY"], self.verboseOutput)
            
            self.__init_tokenizer(secrets)
            
            success = True
        except Exception as e:
            self.logger.exception("Unable to connect to Ollama")

        return success

    def _countTokens(self, contents):
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
        

    def _parseResponse(self, response):
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
        
class LLMManager(user_module.UserModule):
    def __init__(self, clientType, info, tag = "", verboseOutput = False):
        super().__init__(sys.modules[__name__])
        
        self.clientType    = clientType
        self.verboseOutput = verboseOutput
        
        if clientType == LLMClientType.OLLAMA:
            self.llmModel = OllamaModel(info, self.logger, tag, verboseOutput)
        elif clientType == LLMClientType.OPENAI:
            self.llmModel = OpenAIModel(info, self.logger, tag, verboseOutput)
        else:
            self.logger.error(LogLine("Unknown client type: ", clientType))
            self.llmModel = None

    def __del__(self):
        del self.llmModel
    
    def connectToClient(self, secrets):
        success = False
        
        try:
            success = self.llmModel.connectToClient(secrets)  
        except Exception as e:
            self.logger.exception("Could not load job search secrets")
    
        return success

    def chat(self, prompt, context = None, role = "user", responseFormat = None):
        # Capture earlier conversations
        messagesToSend = []
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