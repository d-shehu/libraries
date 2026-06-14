from pathlib        import Path
from typing         import Optional

import os
import shutil
import tempfile

# User packages
from core           import cache

# This package
from .requests      import *

# TODO: set lower initially for testing. Set higher after it's confirmed to work.
MAX_CACHED_REQUEST: int = 10

class RequestCache(cache.Cache[uuid.UUID, Request]):

    class RequestFetchHandler(cache.CacheFetchItemHandler[uuid.UUID,Request]):
        def __init__(self, processingDir: Path, logger):
            super().__init__()

            self.processingDir = processingDir
            self.logger = logger

        def __call__(self, key: uuid.UUID) -> Optional[Request]:
            ret: Optional[Request] = None

            try:
                requestFilepath = Path(self.processingDir, str(key))
                requestFilepath = requestFilepath.with_suffix(".json")
                with open(requestFilepath) as f:
                    data = json.load(f)
                    ret = Request.from_dict(data)
            except Exception as e:
                self.logger.exception(f"Unable to load request with id {key} from file.")

            return ret
        
    class RequestEvictHandler(cache.CacheEvictItemHandler[uuid.UUID,Request]):
        def __init__(self, processingDir: Path, logger):
            super().__init__()

            self.processingDir = processingDir
            self.logger = logger

        def __call__(self, key: uuid.UUID, value: Request):
            ret: Optional[Request] = None

            if (value.status & Status.Resolved) == 0:
                try:
                    tempPath = ""
                    with tempfile.NamedTemporaryFile("w", dir = self.processingDir, delete = False) as tmpFile:
                        tmpFile.write(json.dumps(value, cls = RequestEncoder))
                        tmpFile.flush()
                        os.fsync(tmpFile.fileno())
                        tempPath = tmpFile.name

                    # If successfully then copy to processing
                    processingPath = Path(self.processingDir, str(key))
                    processingPath = processingPath.with_suffix(".json")
                    if Path(tempPath).is_file():
                        shutil.move(tempPath, processingPath)
                    else:
                        raise Exception(f"Unable to move file to {processingPath}.")
                except Exception as e:
                    self.logger.exception(f"Unable to persist request with id {key} to file.")
                

    def __init__(self, processingDir: Path, logger):
        super().__init__(MAX_CACHED_REQUEST, cache.CacheReplacementPolicy.LFU)

        self.processingDir = processingDir
        self.setFetchHandler(RequestCache.RequestFetchHandler(processingDir, logger))
        self.setEvictHandler(RequestCache.RequestEvictHandler(processingDir, logger))