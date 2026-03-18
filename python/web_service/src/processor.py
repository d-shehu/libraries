from pathlib        import Path
from queue          import PriorityQueue
from threading      import Event, Lock, Thread
from typing         import List, Optional, Tuple, TypeAlias

import json
import os
import shutil
import tempfile

# Local packages
from core           import cache
from utilities      import background_task

# Local files
from .requests      import *

# Defines
REQUESTS_FILE       = "requests"
AUTO_SAVE_INTERVAL  = 15 * 60
# TODO: set higher after testing
MAX_CACHED_REQUEST: int = 10

HaltRequest = (Priority.P1_Critical, uuid.UUID(""))
RequestPriorityQueue: TypeAlias = PriorityQueue[Tuple[Priority, uuid.UUID]]

class RequestCache(cache.Cache[uuid.UUID, Request]):

    class RequestFetchHandler(cache.CacheFetchItemHandler[uuid.UUID,Request]):
        def __init__(self, processingDir: Path, logger):
            super().__init__()

            self.processingDir = processingDir
            self.logger = logger

        def __call__(self, key: uuid.UUID) -> Optional[Request]:
            ret: Optional[Request] = None

            try:
                requestFilepath = Path(self.processingDir, str(key), ".json")
                with open(requestFilepath) as f:
                    data = json.load(f, object_hook = Request.field_hook)
                    ret = Request(**data)
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

            try:
                tempPath = ""
                with tempfile.NamedTemporaryFile("w", dir = self.processingDir, delete = False) as tmpFile:
                    tmpFile.write(json.dumps(value, cls = RequestEncoder))
                    tmpFile.flush()
                    os.fsync(tmpFile.fileno())
                    tempPath = tmpFile.name

                # If successfully then copy to processing
                processingPath = Path(self.processingDir, str(key), ".json")
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
    
class Processor(background_task.BackgroundTask):
    DEFAULT_MAINTENANCE_INTERVAL_SECS = 60

    def __init__(self, processingDir: Path, logger):
        self._thread: Optional[Thread]          = None

        self.processingDir  = processingDir
        self.requestsFile   = Path(processingDir, REQUESTS_FILE)
        self.logger         = logger

        # Tracking requests
        self.cache  = RequestCache(self.processingDir, self.logger)
        self.priorityQueue: RequestPriorityQueue = PriorityQueue()

        # Access and flow control for background thread processing requests
        self._requestLock   = Lock()
        self._isRunning     = Event()
        self._isRunning.set()

        self._maintRunner   = background_task.BackgroundRunner(self, 
                                                               Processor.DEFAULT_MAINTENANCE_INTERVAL_SECS)
    
    # Throws exception if unable to load request
    def _load(self) -> bool:
        success = False
        
        # Load unprocessed/pending records from file
        try:
            lsRequests: List[Request] = self.getPendingRequests()

            # Order based on priority and timestamp before resuming processing
            lsRequests.sort()
            for request in lsRequests:
                # Store requests in cache for quick lookup
                self.cache.put(request.id, request)
                # enqueue request so it's actually process
                self.priorityQueue.put((request.priority, request.id))

                success = True
            else:
                self.logger.warning("Requests file not found. Perhaps this is the 1st time the service was run.")
        except Exception as e:
            self.logger.exception("Unable to load requests from file.")
                
        return success

    def doTask(self):
        # Allow periodic writing of requests to file to minimize risk of losing data records
        
        # Persist any changes to local cache
        lsRequestsPersist = []
        dict = self.cache.acquireDict()
        if dict is not None:
            for key in dict:
                request: Optional[Request] = dict.get(key)
                # Persist any unfullfilled and unexpired requests not yet processed.
                if request is not None and request.isPending() and not request.checkExpired():
                    lsRequestsPersist.append(request)
        self.cache.releaseDict()
        
        # Store records not yet processed here
        tempPath = ""
        with tempfile.NamedTemporaryFile("w", dir = self.processingDir, delete = False) as tmpFile:
            tmpFile.write(json.dumps(lsRequestsPersist, cls = RequestEncoder))
            tmpFile.flush()
            os.fsync(tmpFile.fileno())
            tempPath = tmpFile.name

        # If succeeded then copy to processing
        if Path(tempPath).is_file():
            shutil.move(tempPath, Path(self.processingDir, REQUESTS_FILE))

    def onTaskException(self, exception: Exception):
        self.logger.exception("Unable to persist outstanding requests.")

    def getPendingRequests(self) -> List[Request]:
        lsRequests:List[Request] = []

        # Pending requests stay in processing until the request has been processed
        # either successfully or not. Then it goes to the user's directory.
        requestsDir = Path(self.processingDir, REQUESTS_FILE)
        for entry in requestsDir.iterdir():
            # Verify file is of form <request uuid>.json
            if entry.is_file() and Processor._isValidRequestFilename(entry):
                recordsFilepath = Path(requestsDir, entry.stem + ".json")
                with open(recordsFilepath) as f:
                    data = json.load(f, object_hook = Request.field_hook)
                    request = Request(**data)
                    # Is it still pending?
                    if request.isPending():
                        lsRequests.append(request)

        return lsRequests

    def start(self):
        # Daemon thread to prevent app exit from killing thread before it's done processing current work.
        self._thread = Thread(name = "Processor_Thread", target = self._run, daemon = True) 
        self._thread.start()

        # Autosave and other maint. periodically in case service dies
        if self._maintRunner is not None:
            self._maintRunner.start()

    def stop(self):
        self._isRunning.clear()
        self.priorityQueue.put(HaltRequest)

        # Wait for threads to terminate
        if self._thread is not None:
            self._thread.join()  # Wait for server to exit

        # Stop auto-save
        if self._maintRunner is not None:
            self._maintRunner.stop()
    
    def _processRequest(self, request: Request) -> Status:
        raise NotImplementedError("Must define _processRequest for your 'Processor' subclass.")

    def _run(self):
        while self._isRunning.is_set():
            reqPair: Tuple[Priority, uuid.UUID] = self.priorityQueue.get()

            if reqPair != HaltRequest:
                # Get from cache
                request = self.cache.get(reqPair[1])
                if request:
                    with self._requestLock:
                        if request.status == Status.Enqueued:
                            request.status = Status.Processing

                    try:
                        self._processRequest(request)
                    except Exception as e:
                        self.logger.exception(f"Unable to process request: {request}")
                        request.status = Status.Failed
                else:
                    self.logger.exceptionf(f"Unable to read request with id {reqPair[1]} from priority queue")

            else:
                self.logger.warning("Received halt request. Assuming user requested program to exit.")
            
    def enqueue(self, request: Request) -> bool:
        success = False

        if self._isRunning.is_set():
            with self._requestLock:
                try:
                    if request.status == Status.Created:
                        request.status = Status.Enqueued
                    self.cache.put(request.id, request)
                    self.priorityQueue.put((request.priority, request.id))
                    success = True
                except Exception as e:
                    self.logger.exception("Unable to accept request")

        return success
                    
    def cancel(self, requestID: uuid.UUID) -> bool:
        success = False

        request = self.cache.get(requestID)
        if request is not None:
            # We can only cancel request if it's not being processed
            with self._requestLock:
                if request.isPending():
                    request.status = Status.Canceled
                    success = True
                else:
                    self.logger.error(f"Unable to cancel request with id {requestID}")

        return success
    
    @staticmethod
    def _isValidRequestFilename(filepath: Path):
        isValid = False
        try:
            uuid.UUID(filepath.stem)
            isValid = True
        finally:
            return isValid





    
        
    
