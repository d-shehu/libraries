from enum                           import Enum
from langchain_huggingface          import HuggingFaceEmbeddings
from langchain_core.embeddings      import Embeddings
from langchain_openai               import OpenAIEmbeddings
from langchain_ollama               import OllamaEmbeddings
from pathlib                        import Path
from pydantic                       import SecretStr
from threading                      import Lock
from typing                         import Dict

class EmbeddingsProvider(Enum):
    Ollama = "Ollama",
    OpenAI = "OpenAI"
    Local  = "Local" # Download from hugging face
    Legacy = "Legacy" # Based on testing

class RAGEmbeddings:
    DefaultModel = {
        EmbeddingsProvider.Ollama:  "llama3",
        EmbeddingsProvider.OpenAI:  "text-embedding-3-large",
        EmbeddingsProvider.Local:   "sentence-transformers/all-mpnet-base-v2",
        EmbeddingsProvider.Legacy:  "all-MiniLM-L6-v2"
    }
    # Cache list of embeddings
    Lookup: Dict[EmbeddingsProvider, Embeddings] = {}
    lock: Lock = Lock()

    @staticmethod
    def get(provider: EmbeddingsProvider, apiKey: str = "", url: str = "", model: str = "", cacheDir: Path = Path()) -> Embeddings:
        with RAGEmbeddings.lock:
            # If no model is passed try one of the defaults
            if model == "":
                if provider in RAGEmbeddings.DefaultModel:
                    model = RAGEmbeddings.DefaultModel[provider]
                else:
                    raise Exception(f"Unable to get model for provider {provider} and none specified.")

            # Initialize embedding for given provider as needed
            if not provider in RAGEmbeddings.Lookup:
                if provider == EmbeddingsProvider.Ollama:
                    RAGEmbeddings.Lookup[provider] = OllamaEmbeddings(
                        base_url    = url,
                        model       = model
                    )
                elif provider == EmbeddingsProvider.OpenAI:
                    # TODO: evaluate making secrets all SecretStr
                    RAGEmbeddings.Lookup[provider] = OpenAIEmbeddings(
                        openai_api_key  = SecretStr(apiKey), 
                        model           = model,
                    )
                # Generic embeddings provided by Huggingface
                elif provider == EmbeddingsProvider.Local:
                    RAGEmbeddings.Lookup[provider] = HuggingFaceEmbeddings(
                        model_name      = model,
                        cache_folder    = cacheDir,
                        model_kwargs={
                            "token": apiKey
                        }
                    )
                elif provider == EmbeddingsProvider.Legacy:
                    RAGEmbeddings.Lookup[provider] = HuggingFaceEmbeddings(
                        model_name      = model,
                        cache_folder    = str(cacheDir),
                        model_kwargs={
                            "token": apiKey
                        }
                    )
                else:
                    raise Exception(f"Unknown provider {provider}")
                
            return RAGEmbeddings.Lookup[provider] 