from dataclasses                            import dataclass
from enum                                   import Enum
from langchain_chroma                       import Chroma
from langchain.schema.document              import Document
from langchain_community.vectorstores.utils import filter_complex_metadata

from pathlib                                import Path
from typing                                 import Dict, Generic, Iterator, List, Optional, TypeVar

import json
import shutil
import uuid

# User packages
from core                                   import cache

# Local files
from .embeddings                            import Embeddings
from .meta                                  import RAGMetadata, RAGMetadataEncoder
from .sources                               import RAGSource

# Defines
RAGSourceType       = TypeVar("RAGSourceType",  bound = RAGSource)

class RAGQueryMatchCondition(Enum):
    Match_Any   = 1,
    Match_All   = 2

ALL_RESULTS = -1

@dataclass
class RAGQueryParams:
    maxResults:         int
    minThreshold:       float
    tags:               List[str]
    matchingCondition:  RAGQueryMatchCondition

    def __init__(self,
                 minThreshold: float = 0.5, 
                 maxResults: int = 5, 
                 matchingTags: List[str] = [], 
                 matchCondition: RAGQueryMatchCondition = RAGQueryMatchCondition.Match_Any):
        
        self.maxResults         = maxResults
        self.minThreshold       = minThreshold
        self.matchingTags       = matchingTags
        self.matchingCondition  = matchCondition

class RAGCollection(Generic[RAGSourceType]):
    MetadataFile: str   = "meta.json"
    SourcesMeta: str    = "sources.json"
    DBFilename: str     = "chroma_langchain_db" # TODO: revisit naming convention

    def __init__(self, saveDir: Path, metadata: RAGMetadata, embeddings: Embeddings):
        self.collectionDir      = Path(saveDir, metadata.id)
        self.metadata           = metadata
        self.embeddings         = embeddings

        self.sourcesMetadata: Dict[str, RAGMetadata] = {}

        self.dbStore: Optional[Chroma] = None # TODO: consider making this generic as in VectorStore

    @staticmethod
    def readMetadata(saveDir: Path, id: str) -> RAGMetadata:
        with open(Path(saveDir, id, RAGCollection.MetadataFile)) as f:
            return RAGMetadata(**json.load(f, object_hook = RAGMetadata.field_hook))
        
    def delete(self):
        # TODO: how to actually safely close the vector store.
        if self.dbStore is not None:
            del self.dbStore
            self.dbStore = None

        # Delete metadata, dbstore and collections dir
        Path(self.collectionDir, RAGCollection.MetadataFile).unlink()
        shutil.rmtree(Path(self.collectionDir, RAGCollection.DBFilename))
        Path(self.collectionDir).rmdir()

    def exists(self) -> bool:
        # Only if both files were created is it considered a valid collection.
        return (Path(self.collectionDir, RAGCollection.MetadataFile).is_file()
                and Path(self.collectionDir, RAGCollection.DBFilename).is_file())
    
    # TODO: handle other vector store as a generic type of this class.
    def _getDBStoreMetadata(self) -> dict:
        # Resolve issue with Chroma cosine scoring inconsistency with langchain
        # Ref: https://github.com/langchain-ai/langchain/discussions/22422
        return {"hnsw:space": "cosine"}

    def initDB(self):
        # TODO: consider running Chrome server for performance reasons
        self.dbStore = Chroma(
            collection_name     = self.metadata.id,
            embedding_function  = self.embeddings,
            collection_metadata = self._getDBStoreMetadata(),
            persist_directory   = str(Path(self.collectionDir, RAGCollection.DBFilename))
        )
            
    def readSourceMetadata(self):
        with open(Path(self.collectionDir, RAGCollection.SourcesMeta)) as f:
            sourcesJSON = json.load(f, object_hook = RAGMetadata.field_hook)
            for item in sourcesJSON:
                sourceMeta = RAGMetadata(**item)
                self.sourcesMetadata[sourceMeta.id] = sourceMeta

    def writeSourceMetadata(self):
         with open(Path(self.collectionDir, RAGCollection.SourcesMeta), "w") as f:
            lsSourceMeta: List[RAGMetadata] = list(self.sourcesMetadata.values())
            json.dump(lsSourceMeta, f, cls = RAGMetadataEncoder)

    def doLoad(self):
        success = False
        try:
            if self.dbStore is None:
                self.initDB()
                self.readSourceMetadata()
            
            success = True
        finally:
            return success
        
    def reset(self):
        if self.doLoad() and self.dbStore is not None:
            self.dbStore.reset_collection()
            self.sourcesMetadata = {}
            self.writeSourceMetadata()
        else:
            raise ValueError("Please initialize dbStore.")
   
    def persist(self):
        # Create directory. It's ok if the directory exists.
        self.collectionDir.mkdir(mode = 0o700, parents = False, exist_ok = True)
        self.initDB()

        # Write collection metadata
        with open(Path(self.collectionDir, RAGCollection.MetadataFile), "w") as f:
            json.dump(self.metadata, f, cls = RAGMetadataEncoder)

        # Write the sources if there are any
        self.writeSourceMetadata()

    # TODO: not thread safe yet
    def addSource(self, source: RAGSourceType) -> bool:
        success = False

        if self.doLoad() and self.dbStore is not None:
            docList = list(source.getRawDocs())
            docListMetaFiltered = filter_complex_metadata(docList)    
            self.dbStore.add_documents(documents = docListMetaFiltered)

            # Update meta for this source
            self.sourcesMetadata[source.metadata.id] = source.metadata

            # TODO: optimize to avoid writing meta source over and over
            self.writeSourceMetadata()

            success = True
        else:
            raise LookupError(f"Unable to load vector store for collection {self.metadata.id}")

        return success # Assume OK if not exception generated

    def delSource(self, sourceID: str) -> bool:
        # Delete all fragments from documents in source ID
        if self.doLoad() and self.dbStore is not None:
            currSource = self.sourcesMetadata[sourceID]
            for entry in currSource.toc:
                self.dbStore.delete(entry.value)
            # Delete from hash
            del self.sourcesMetadata[sourceID]

            # TODO: optimize to avoid writing meta source over and over
            self.writeSourceMetadata()
        else:
            raise LookupError(f"Unable to load vector store for collection {self.metadata.id}") 
        
        return False
    
    def delDocument(self, sourceID: str, docID: str) -> bool:
        return False

    def updateSource(self, sourceID: str) -> bool:
        return False
    
    # Iterate over the source metadata.
    def __iter__(self) -> Iterator[RAGMetadata]:
        if self.doLoad():
            return iter(self.sourcesMetadata.values())
        else:
            raise LookupError(f"Unable to get sources for collection {self.metadata.id}")
    
    def query(self, queryStr: str, queryParams: RAGQueryParams = RAGQueryParams()) -> List[tuple[Document, float]]:
        result: List[tuple[Document, float]] = []

        # TODO: Add filtering of collection and source by tags
        if self.doLoad():
            if self.dbStore is not None:
                if queryParams.maxResults == ALL_RESULTS:
                    dbCollection = self.dbStore.get()
                    queryParams.maxResults = len(dbCollection["documents"])

                result = self.dbStore.similarity_search_with_relevance_scores(
                    queryStr, 
                    k = queryParams.maxResults,
                    filter = None
                )
            else:
                raise ValueError(f"Unable to load vector db for similarity search for collection {self.metadata.id}.")
        else:
            raise LookupError(f"Unable to get sources for collection {self.metadata.id}")    

        return result
    
class CollectionMgr:
    Max_Collections_in_Memory = 5 # TODO: raise after testing is done

    # Helper classes
    class FetchCollectionHandler(cache.CacheFetchItemHandler[str, RAGCollection]):
        def __init__(self, saveDir: Path, embeddings: Embeddings):
            super().__init__()
            self.saveDir    = saveDir
            self.embeddings = embeddings

        def __call__(self, key: str) -> Optional[RAGCollection]:
            metadata = RAGCollection.readMetadata(self.saveDir, key)
            return RAGCollection(self.saveDir, metadata, self.embeddings)

    class EvictCollectionHandler(cache.CacheEvictItemHandler[str, RAGCollection]):
        def __call__(self, key: str, value: RAGCollection) -> Optional[RAGCollection]:
            value.persist()

    # Class Members
    def __init__(self, saveDir: Path, embeddings: Embeddings):
        self.saveDir    = saveDir
        self.embeddings = embeddings
        self.cache      = cache.Cache(CollectionMgr.Max_Collections_in_Memory,
                                      cache.CacheReplacementPolicy.LRU)
        
        self.cache.setFetchHandler(CollectionMgr.FetchCollectionHandler(saveDir, embeddings))
        self.cache.setEvictHandler(CollectionMgr.EvictCollectionHandler())

    def create(self, metadata: RAGMetadata) -> RAGCollection:
        newCollection = RAGCollection(self.saveDir, metadata, self.embeddings)
        if newCollection.exists():
            raise FileExistsError("Collection already exists")
        else:
            newCollection.persist()
            self.cache.put(metadata.id, newCollection)
            return newCollection

    def get(self, id: str) -> Optional[RAGCollection]:
        return self.cache.get(id)

    # Iterate over the metadata to avoid loading the collection.
    def __iter__(self) -> Iterator[RAGMetadata]:

        for entry in self.saveDir.iterdir():
            if entry.is_dir():
                yield RAGCollection.readMetadata(self.saveDir, entry.name)
    
    def deleteCollection(self, id: str):

        collection = self.cache.get(id)
        if collection is not None:
            collection.delete()




    