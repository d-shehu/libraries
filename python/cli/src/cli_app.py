import argparse
import os
from pathlib import Path

# User packages
from core import logs

# Local package
from .cli_context import *
from .cli_program import *

class ArgValidator:
    def parseDirPath(path):
        if path == "" or Path(path).is_dir():
            return path
        else:
            raise NotADirectoryError(path)
                

    def parseFilePath(path):
        if path == "" or Path(path).is_file():
            return path
        else:
            raise FileNotFoundError(path)
       
class CLIApp:
    def __init__(self, 
                 appName, 
                 description,
                 version,
                 additionalInfo = ""):
        
        self.appName        = appName
        self.description    = description
        self.version        = version
        self.additionalInfo = additionalInfo
        self.context        = CLIContext()

        # If logs director not specified fall back to logging to console
        self.logMgr = logs.ConfigureConsoleOnlyLogging(appName + "_Logger")
        self.logger = self.logMgr.getSysLogger()
        
        self.argParser = argparse.ArgumentParser(prog        = self.appName,
                                                 description = self.description,
                                                 epilog      = self.additionalInfo)

        self.configureArguments()

    # Override default usage from argparser
    def setUsage(self, appUsage):
        self.argParser.setUsage(appUsage) 

    def configureArguments(self):
        self.argParser.add_argument("-i", "--interactive",      type     = bool, 
                                                                action   = argparse.BooleanOptionalAction,
                                                                help     = "Run application in interactive mode with user input.",
                                                                default  = False)
        
        self.argParser.add_argument("-e", "--environment_file", type     = ArgValidator.parseFilePath,
                                                                help     = "Path to .env file.",
                                                                default  = "")
        
        self.argParser.add_argument(      "--disable_logging",  type     = str,
                                                                help     = """Disable logging for this level and below.
                                                                              Assumed to not be set enabling logging for
                                                                              all levels. Allow values: DEBUG, INFO,
                                                                              WARNING, ERROR, CRITICAL.""",
                                                                default  = "")
        
        self.argParser.add_argument(      "--log_dir",          type     = ArgValidator.parseDirPath,
                                                                help     = """Path to directory that holds logs. 
                                                                              If not specified then logging will be to console only.""",
                                                                default  = "")
        
        # TODO: debug should be used to toggle on/off debug logging.
        self.argParser.add_argument(      "--debug",            type     = bool, 
                                                                action   = argparse.BooleanOptionalAction,
                                                                help     = "Enable debug mode and logging. Defaults to false.",
                                                                default  = False)
        
        self.argParser.add_argument(      "--secrets_file",     type     = ArgValidator.parseFilePath,
                                                                help     = "Path to secrets file with API keys, passwords, etc.",
                                                                default  = "")

        # TODO: passthrough to underlying user logic
        self.argParser.add_argument(      "--verbose",          type      = bool, 
                                                                action    = argparse.BooleanOptionalAction,
                                                                help      = """Enable extra logging above and beyond. 
                                                                               Custom logic defined in app.""",
                                                                default   = False)
        
        self.argParser.add_argument("-v", "--version",          action    = "version",
                                                                version   = f"{self.appName} {self.version}",
                                                                help      = "Show app version and exit.")

    def parseArguments(self) -> bool:
        success = False
        
        try:
            args = self.argParser.parse_args()
            
            # Enable logging to file?
            logsDir = args.log_dir
            if logsDir != "":
                self.logMgr = logs.ConfigureDefaultLogging(self.appName + "_Logger", args.log_dir)
                self.logger = self.logMgr.getSysLogger()
            self.logger.debug(f"Logs dir: {logsDir}")

            # Debugging flag?
            self.isDebugMode = args.debug
            if not self.isDebugMode:
                self.logMgr.suppressLogger("DEBUG") # Disable logging
            self.logger.debug(f"Debug mode: {self.isDebugMode}")
            
            # Disable logging for this level and below.
            self.disableLoggingLevel = args.disable_logging
            if self.disableLoggingLevel != "":
                self.logMgr.suppressLogger(self.disableLoggingLevel)
                self.logger.debug(f"Disable log levels <=: {self.disableLoggingLevel}")

            # Interactive or batch mode
            self.isInteractive = args.interactive

            # Environment variables can come from either environment file or os.env
            self.envFilepath = args.environment_file
            if self.envFilepath != "":
                context.configureEnvVariables(os.path.expanduser(self.envFilepath))
                self.logger.debug(f"Disable log levels <=: {self.disableLoggingLevel}")

            # Secrets which also utilizes .env format
            self.secretsFilepath = args.secrets_file
            if self.secretsFilepath != "":
                context.configureSecrets(os.path.expanduser(self.secretsFilepath))

            # Verbose enable
            self.context.isVerboseMode = args.verbose
            
            success = True
        except Exception as e:
            self.logger.exception("Unable to parse one or more arguments.")

        return success
     
    def run(self, program) -> int:
        exitCode = os.EX_OK
        
        # Successfully parsed the arguments
        if program is None:
            self.logger.error("Must pass in a valid program to CLIApp's 'run'.")

        if self.parseArguments():
            program.configure(self.argParser, self.context, self.logger)
            try:
                if self.isInteractive:
                    self.logger.info(f"Running {self.appName} in interactive mode.")
                    exitCode = program.runInteractive()
                else:
                    self.logger.info(f"Running {self.appName} in batch mode.")
                    exitCode = program.runBatch()
            except Exception as e:
                self.logger.exception("Exception encountered while running program.")
                exitCode = os.EX_SOFTWARE
        else:
            exitCode = os.EX_USAGE

        return
        
def main():
    app = CLIApp("CLIApp", "CLIApp main function and simple demo.")
    app.run(CLICommand())

if __name__ == '__main__':
    main()