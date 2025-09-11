from openai         import OpenAI

import tiktoken

# User packages
from .llm_define    import LogLine, LLMMessage, LLMResponse, LLMResponseStatus
from .llm_model     import LLMModel

class OpenAIModel(LLMModel):
    def __init__(self, info, logger, tag = "", verboseOutput = False):
        super().__init__(info, logger, tag, verboseOutput)

        self.client: Optional[OpenAI] = None
        self.encoding = tiktoken.encoding_for_model(info["name"])

    def connectToClient(self, secrets) -> bool:
        success = False
        
        try:
            if self.client is not None:
                del self.client
                
            self.client = OpenAI(api_key=secrets["OPENAI_API_KEY"])
            
            success = True
        except Exception as e:
            self.logger.exception("Unable to connect to Open AI.")

        return success

    def _countTokens(self, contents) -> int:
        return len(self.encoding.encode(contents))

    def _parseResponse(self, response) -> LLMResponse:
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
            
        response = self.client.completions.create(
            model             = self._getModelHandle(),
            messages          = list(map(lambda obj: obj.__dict__, messages)), # Array of dict
            seed              = self.options.seed,  
            temperature       = self.options.temperature,
            top_p             = self.options.top_p,
            frequency_penalty = self.options.repeat_penalty
        )

        return response