# Local files
from .meta                      import RAGMetadata

class RAGInput:
    def __init__(self, metadata: RAGMetadata):
        self.metadata = metadata