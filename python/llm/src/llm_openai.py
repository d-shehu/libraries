from openai             import OpenAI
from openai.types.chat  import ChatCompletionUserMessageParam
from typing             import cast, List, Optional

import tiktoken

# Local packages
from my_secrets         import secrets_mgr

# This package
from .llm_define        import LogLine, LLMMessage, LLMResponse, LLMResponseStatus
from .llm_model         import LLMModel

class OpenAIModel(LLMModel):
    def __init__(self, info, logger, variant = "", verboseOutput = False):
        super().__init__(info, logger, variant, verboseOutput)

        self.client: Optional[OpenAI] = None
        self.encoding = tiktoken.encoding_for_model(info.name)

    def connectToClient(self, secretsMgr: secrets_mgr.SecretsMgr) -> bool:
        success = False
        
        try:
            if self.client is not None:
                del self.client
                
            openAIAPIKey=secretsMgr.getSecret("OPENAI_API_KEY")
            if openAIAPIKey is not None:
                self.client = OpenAI(api_key=openAIAPIKey.expose())
                success = True
            else:
                self.logger.error("Unable to connect to OpenAI API due to missing 'OPENAI_API_KEY'.")

        except Exception as e:
            self.logger.exception("Unable to connect to Open AI.")

        return success

    def _countTokens(self, contents) -> int:
        return len(self.encoding.encode(contents))

    def _parseResponse(self, response:dict) -> LLMResponse:
        parsedResponse = LLMResponse()

        try:
            parsedResponse.model = response["model"]    
            # TODO: revisit this. OpenAI may return multiple messages
            choices = response["choices"]
            firstChoice = choices[0]
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

    def _doChat(self, messages: List[LLMMessage], responseFormatJson = None) -> str:
        if responseFormatJson is not None:
            raise Exception("JSON response not currently supported with Open AI LLM")

        if self.verboseOutput:
            self.logger.debug(LogLine("Chatting with OpenAI model " + self._getModelHandle()))

        if self.client is not None: 
            response = self.client.chat.completions.create(
                model             = self._getModelHandle(),
                messages          = [ cast(ChatCompletionUserMessageParam, message.to_dict()) for message in messages],
                seed              = self.info.params.seed,  
                temperature       = self.info.params.temperature,
                top_p             = self.info.params.top_p,
                frequency_penalty = self.info.params.repeat_penalty
            )
        else:
            self.logger.error("LLM client is not defined or initialized.")

        return response