from abc                import abstractmethod
from fastapi            import FastAPI
from threading          import Thread
from typing             import Optional

import asyncio
import httpx
import os
import uvicorn
import uuid

# User module and logging
from core import logs, user_module

# Local files
from    .context    import APIContext
from    .params     import ServiceParams
from    .processor  import Processor
from    .router     import ServiceRouter
from    .user_mgr   import UserMgrBase

class FastAPIService(user_module.UserModule):
    def __init__(self, 
                 params: ServiceParams, 
                 serviceID: uuid.UUID, 
                 logMgr = logs.ConfigureConsoleOnlyLogging("FastAPIService")
                 ):
        
        super().__init__(logMgr)

        self._thread: Optional[Thread]          = None
        self._server: Optional[uvicorn.Server]  = None
        
        self.asyncClient    = httpx.AsyncClient()
        self.app            = FastAPI()
        self.params         = params

        self.serviceID      = serviceID

    @abstractmethod
    def createProcessor(self) -> Processor:
        pass # Must define in subclass with desired processor subclass

    @abstractmethod
    def createUserMgr(self) -> UserMgrBase:
        pass # Must define in subclass with desired UsrMgr implementation

    @abstractmethod
    def createRouter(self) -> ServiceRouter:
        pass # Define custom routes and APIs

    # Can be overriden if APIContext needs to be subclassed for custom service.
    def createAPIContext(self) -> APIContext:
        return APIContext(
            self.serviceID,
            self.params.processingDir,
            self.createProcessor(),
            self.createUserMgr(),
            self.asyncClient,
            self.logger
        )

    def initContext(self) -> bool:
        success = False

        try:
            if self.params.isValid:
                self.context = self.createAPIContext()
                self.registerRouters(self.createRouter())
            
            success = (self.params.isValid 
                    and self.context is not None 
                    and self.context.load())
        except:
            self.logger.exception("Unable to initialize service context due to exception.")
    
        return success

    def registerRouters(self, router: ServiceRouter):
        router.addRouter(self.app)

    def start(self):
        config = uvicorn.Config(self.app, 
                                host = self.params.serverAddr, 
                                port = self.params.serverPort, 
                                log_level = "info")
        
        self._server = uvicorn.Server(config)
        if self._server is not None:
            self._thread = Thread(name = "Service_Thread", target = self._run, daemon = True)
            self._thread.start()
        else:
            self.logger.error("Unable to start uvicorn server")

        if self.context.processor is not None:
            self.context.processor.start()

    def wait(self):
        if self._thread is not None:
            # Wait for server to exit gracefully
            self._thread.join()

    def stop(self):
        # Stop the processor first and then shut down own threads
        if self.context.processor is not None:
            self.context.processor.stop()

        if self._server is not None: 
            # Signal to uvicorn to stop listening for requests
            self._server.should_exit = True
            self.wait()
            self.context.store()
            del self.asyncClient
            self.asyncClient = None
            del self._server
            self._server = None
            
    def _run(self):
        if self._server is not None:
            asyncio.run(self._server.serve())
        else:
            self.logger.error("Server not initialized.")
        
    def __del__(self):
        self.stop()
        del self.app

    # Convenience function for running service in CLI app cleanly
    def runAndWait(self) -> int:
        retVal = os.EX_SOFTWARE

        try:
            if self.initContext():
                self.logger.info(f"{self.params.serviceName} is running as a service ... ")
                self.start()
                self.wait()
                self.logger.info(f"{self.params.serviceName} has exited!")

                retVal = os.EX_OK
            else:
                self.logger.error("{self.params.serviceName} unable to run because context can't be initialized.")
                retVal = os.EX_CONFIG

        except KeyboardInterrupt as e:
            self.logger.info(f"{self.params.serviceName} has been interrupted by user!")
            self.stop()
            self.wait()

        return retVal


