from ast import Str
from datetime                   import date, datetime, timezone
from typing                     import List

import json
import uuid

# Defines
INVALID_RAG_METADATA_DATE   = datetime(1900, 1, 1, tzinfo=timezone.utc)

class RAGMetadata:
    # Pick an arbitrary but invalid date in past
    
    DT_FORMAT_STR               = "%Y-%m-%d %H:%M:%S.%f%z"

    def __init__(self, name: str = "", description: str = "", lsTags: List[str] = [], id: str = "", toc = {},
                 created = INVALID_RAG_METADATA_DATE, 
                 updated = INVALID_RAG_METADATA_DATE,
                 indexed = INVALID_RAG_METADATA_DATE):
        self.name:          str         = name
        self.description:   str         = description
        self.lsTags:        List[str]   = lsTags
        self.id:            str         = id # ID is of type str for greater flexibility
        self.toc:           dict        = toc # Source, document or other TOC

        if created == INVALID_RAG_METADATA_DATE:
            self.created = datetime.now(timezone.utc) # Assume it's newly created and timestamp is "now"
        else:
            self.created = created

        if updated == INVALID_RAG_METADATA_DATE:
            self.updated = self.created
        else:
            self.updated = updated # Assume same as created if it's a new record

        #TODO: this needs to be updated during indexing
        self.indexed = indexed 

        # Auto assign an ID
        if self.id == "":
            self.id = str(uuid.uuid4())

    @staticmethod
    def field_hook(dict):
        if "toc" in dict:
            dict["toc"] = json.loads(dict["toc"])
        if "created" in dict:
            dict["created"] = datetime.strptime(dict["created"], RAGMetadata.DT_FORMAT_STR)
        if "updated" in dict:
            dict["updated"] = datetime.strptime(dict["updated"], RAGMetadata.DT_FORMAT_STR)
        if "indexed" in dict:
            dict["indexed"] = datetime.strptime(dict["indexed"], RAGMetadata.DT_FORMAT_STR)
        if "lsTags" in dict:
            lsTagsStr = dict["lsTags"]
            dict["lsTags"] = lsTagsStr.split(",") if lsTagsStr != ""  else []

        return dict
    

class RAGMetadataEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, RAGMetadata):
            return {
                "name":             o.name,
                "description":      o.description,
                "lsTags":           ", ".join(o.lsTags),
                "id":               o.id,
                "toc":              json.dumps(o.toc),    
                "created":          o.created.strftime(RAGMetadata.DT_FORMAT_STR),
                "updated":          o.updated.strftime(RAGMetadata.DT_FORMAT_STR),
                "indexed":          o.indexed.strftime(RAGMetadata.DT_FORMAT_STR)
            }
        else:
            return super().default(o)