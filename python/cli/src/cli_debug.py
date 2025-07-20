import debugpy
import pydevd

from .cli_context      import * 

class CLIDebugger:
    def __init__(self, logger, cliContext):
        self.logger = logger
        self.debugAddress   = cliContext.getEnvVariable("DEBUG_ADDRESS", "0.0.0.0")
        self.debugPort      = cliContext.getEnvVariable("DEBUG_PORT", 3000)
        self.isListening    = False
        self.isDone         = False

    def __del__(self):
        if not self.isDone:
            self.isDone = True
            self.stop()

    def start(self):
        if not self.isDone and not self.isListening:
            self.logger.info(f"Listening for debugger on '{self.debugAddress}:{self.debugPort}'.")
            debugpy.listen((self.debugAddress, self.debugPort))
            self.isListening = True
        elif not self.isDone:
            self.logger.error("Already listening for debugger.")
        else:
            self.logger.error("Unable to listen for debugger.")


    def wait(self):
        if not self.isListening:
            self.start()

        self.logger.info("Waiting for client to attach...")
        debugpy.wait_for_client()
        debugpy.breakpoint()

    def stop(self):
        if self.isListening:
            pydevd.stoptrace()
            self.isListening = False