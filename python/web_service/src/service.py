
from dataclasses        import dataclass
from fastapi            import FastAPI, File, UploadFile, HTTPException, status
from pathlib            import Path
from threading          import Thread
from typing             import Dict, Optional

import asyncio
import httpx
import os
import uvicorn
import uuid

# User module and logging
from core import user_module, logs

# Local files
from    .context    import APIContext
from    .processor  import Processor
from    .router     import ServiceRouter
from    .user_mgr   import UserMgrBase

@dataclass
class ServiceParams:
    processingDir:  Path
    usersDir:       Path
    customParams:   Dict

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

    # Can be overriden if APIContext is subclassed
    def initContext(self, processor: Processor, userMgr: UserMgrBase):
        self.context = APIContext(
            self.serviceID,
            self.params.processingDir,
            processor,
            userMgr,
            self.asyncClient,
            self.logger
        )
        #     serviceID,
        #     processingDir=self.processingDir,
        #     processor,
        #     userMgr,
        #     self.asyncClient,
        #     self.logger
        # )
        self.context.load()     

    def registerRouters(self, router: ServiceRouter) -> None:
        router.addRouter(self.app)

    def start(self):
        config = uvicorn.Config(self.app, host = "0.0.0.0", port = 8080, log_level = "info")
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
    def runAndWait(self, serviceName: str):
        try:
            self.logger.info(f"{serviceName} is running as a service ... ")
            self.start()
            self.wait()
            self.logger.info(f"{serviceName} service has exited!")
        except KeyboardInterrupt as e:
            self.logger.info(f"{serviceName} serverice has been interrupted by user!")
            self.stop()
            self.wait()

        return os.EX_OK


