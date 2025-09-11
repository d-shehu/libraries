from abc                        import ABC, abstractmethod
from dataclasses                import dataclass
from enum                       import Enum
from itertools                  import chain
from pathlib                    import Path
from typing                     import Dict, Iterator, Iterable, List, Optional

from langchain.schema.document  import Document

from langchain_community.document_loaders.parsers   import TesseractBlobParser

import os
import uuid

# Local files
from .meta                      import RAGMetadata
from .transformer               import RAGTransformer

from langchain_community.document_loaders import (
    CSVLoader,
    DirectoryLoader,
    Docx2txtLoader,
    JSONLoader,
    PyPDFLoader,
    PDFPlumberLoader,
    TextLoader,
    UnstructuredExcelLoader,
    UnstructuredHTMLLoader,
    UnstructuredPowerPointLoader,
    UnstructuredMarkdownLoader,
    UnstructuredPDFLoader
)

# Defines some customized readers
class SimplePDFLoader(PyPDFLoader):
    def __init__(self, file):
        super().__init__(file, 
                         mode = "single",
                         images_inner_format="html-img",
                         images_parser=TesseractBlobParser()
                         )
        
class ComplexPDFLoader(PDFPlumberLoader):
    def __init__(self, file):
        super().__init__(file,
                         extract_images = True
        )

# Doc: https://docs.unstructured.io/api-reference/partition/partitioning#partitioning-strategies
class SmartPDFLoader(UnstructuredPDFLoader):
    class Mode(Enum):
        Single      = "single"      # Return single langchain Doc
        Elements    = "elements"    # Return title, text

    class Strategy(Enum):
        Auto    = "auto"        # Determine automatically
        Fast    = "fast"        # NLP-based but not recommended for image-heavy pdf
        HiRes   = "hi_res"      # Model-based approach to gain insights on layouts and doc elements
        OCROnly = "ocr_only"    # Use optical character recognition to extract text from images
        VLM     = "vlm"         # Vision language models to extract text from image files

    def __init__(self, file):
        super().__init__(file, 
                         mode = SmartPDFLoader.Mode.Elements.value,
                         strategy = SmartPDFLoader.Strategy.HiRes.value)

ALL_RESULTS:int = -1

FILETYPE_LOADERS = {
    # '*.csv':    CSVLoader,
    # '*.docx':   Docx2txtLoader,
    # '*.html':   UnstructuredHTMLLoader,
    # '*.json':   JSONLoader,
    # '*.md':     UnstructuredMarkdownLoader,
    '*.pdf':    SmartPDFLoader,
    # '*.pptx':   UnstructuredPowerPointLoader,
    # '*.ppt':    UnstructuredPowerPointLoader,
    # '*.txt':    TextLoader,
    # '*.xlss':   UnstructuredExcelLoader,
    # '*.xlsx':   UnstructuredExcelLoader,
}

@dataclass
class RAGDoc:
    rawDoc:         Optional[Iterator[Document]] # Lazy load docs
    source:         str
    id:             str
    fragmentsID:    List[str]

    # Try to free up memory if data is no longer needed
    def purge(self):
        if self.rawDoc is not None:
            del self.rawDoc
            self.rawDoc = None

    def isDecomposed(self):
        return len(self.fragmentsID) > 0

    def getTOCRec(self):
        return {
            "source":       self.source,
            "id":           self.id,
            "fragmentsID":  self.fragmentsID
        }

class RAGSource(ABC):
    def __init__(self, metadata: RAGMetadata):
        self.metadata                   = metadata
        self.docs: Dict[str, RAGDoc]    = {}
        
    # Load from disk or remote location
    @abstractmethod
    def load(self) -> bool:
        pass

    # Extract text from tables or other complex structure
    def transform(self, transformer: RAGTransformer):
        success = False

        if self.docs is not None:
            newDocs: List[RAGDoc] = []

            for doc in self.docs.values():
                if not doc.isDecomposed():
                    if doc.rawDoc is not None:
                        docFragments = transformer.transform(doc.rawDoc)
                        doc.purge() # Free up memory from original doc
                        # Add each fragment as its own document
                        for fragment in docFragments:
                            fragmentID = str(uuid.uuid4())
                            # Collect new docs in temp list ...
                            newDocs.append(RAGDoc(
                                rawDoc      = iter([fragment]),
                                source      = doc.source,
                                id          = str(fragmentID),
                                fragmentsID = []
                            ))
                            doc.fragmentsID.append(fragmentID)
                        # Update TOC with new fragments
                        self.metadata.toc[doc.id] = doc.getTOCRec()
                    else:
                        raise ValueError(f"Document associated with source {doc.source} already purged from memory.")
            
            # Add all new docs to source
            for newDoc in newDocs:
                self._add(newDoc)

            success = True
        else:
            raise ValueError("Documents not loaded or otherwise not available.")

        return success

    def getRawDocs(self) -> Iterator[Document]:
        ret = None

        if self.docs is not None:
            for ragDoc in self.docs.values():
                # The "documents" to use are the ones that haven't been decomposed
                # into fragments.
                if not ragDoc.isDecomposed():
                    if ret is None:
                        ret = ragDoc.rawDoc
                    elif ragDoc.rawDoc is not None:
                        ret = chain(ret, ragDoc.rawDoc)
                    else:
                        raise ValueError(f"Document associated with source {ragDoc.source} already purged from memory.")
        else:
            raise LookupError(f"Unable to get source with id {self.metadata.id}")
        
        if ret is None:
            ret = iter([])
        
        return ret
        
    def _add(self, doc: RAGDoc):
        self.docs[doc.id]           = doc
        self.metadata.toc[doc.id]   = doc.getTOCRec()

    def _remove(self, id: str):
        try:
            if id in self.docs and self.metadata.toc:
                children: List[str] = self.metadata.toc[id]["childrenID"]
                del self.docs[id]
                del self.metadata.toc[id]

                for childID in children:
                    self._remove(childID)

        except Exception as e:
            raise LookupError("Unable to remove doc from toc or associated fragments")


class LocalFilesSource(RAGSource):
    def __init__(self, sourcePath: Path, metadata: RAGMetadata, recursiveLoad: bool = True):
        super().__init__(metadata)

        self.sourcePath     = sourcePath
        self.recursiveLoad  = recursiveLoad

        # If the unique ID is not set create one from the filepath
        if metadata.id == "":
            newID = LocalFilesSource.GetIDFromPath(sourcePath)
            self.metadata.id = newID
            
    @staticmethod
    def GetIDFromPath(path: Path) -> str:
        newID = str(path).replace(os.sep, ".")
        if newID.startswith("."):
            newID = newID[1:]
        
        return newID

    def _loadDir(self, dirPath) -> bool:
        for entry in dirPath.iterdir():
            if entry.is_dir() and self.recursiveLoad:
                self._loadDir(entry)
            elif entry.is_file():
                # Is this format supported
                pattern = "*" + entry.suffix
                if pattern in FILETYPE_LOADERS:
                    self._loadFile(entry)
        
        return not self.docs is not None

    def _loadFile(self, filepath: Path) -> bool:
        filepath = filepath.resolve() # Make sure it's an absolute path
        
        pattern = "*" + filepath.suffix # Look for a loader like *.pdf or *.txt
        if pattern in FILETYPE_LOADERS:
            loaderCls = FILETYPE_LOADERS[pattern]
            loader = loaderCls(filepath)
            self._add(RAGDoc(
                rawDoc      = loader.lazy_load(),
                source      = str(filepath),
                id          = LocalFilesSource.GetIDFromPath(filepath), # Assume path is absolute and unique
                fragmentsID = [] # No children as yet
            ))
        else:
            raise NotImplementedError(f"Unable to find loader for type '{filepath.suffix}'.")

        return self.docs is not None

    def load(self):
        success = False

        if self.sourcePath.is_dir():
            success = self._loadDir(self.sourcePath)
        elif self.sourcePath.is_file():
            success = self._loadFile(self.sourcePath)
        else:
            raise NotImplementedError(f"'{self.sourcePath}' is neither a directory or file")
        
        return success
    