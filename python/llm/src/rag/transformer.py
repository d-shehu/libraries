from abc                        import ABC, abstractmethod
from dataclasses                import dataclass
from langchain.schema.document  import Document
from langchain_text_splitters   import RecursiveCharacterTextSplitter
from typing                     import Dict, Iterable, Iterator, List, Tuple

import uuid

class RAGTransformer(ABC):
    @abstractmethod
    def transform(self, doc: Iterable[Document]) -> Iterable[Document]:
        pass
    
# CharacterTextSplitter is a basic approach to splitting text 
class RAGSimpleTransformer(RAGTransformer):
    def __init__(self, chunkSize: int, chunkOverlap: int):
        self.chunkSize      = chunkSize
        self.chunkOverlap   = chunkOverlap

        self.textSplitter: RecursiveCharacterTextSplitter = RecursiveCharacterTextSplitter(
            chunk_size = chunkSize, 
            chunk_overlap = chunkOverlap
        )
        
    @staticmethod
    def createOptimized():
        # TODO: empirically derive parameters from testing or from base document
        return RAGSimpleTransformer(4096, 0)
    
    def transform(self, doc: Iterable[Document]) -> Iterable[Document]:
        return self.textSplitter.split_documents(doc)