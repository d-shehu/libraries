import os
from pathlib import Path

# User packages
from core import user_module, logs, install

# Local package
from .cli_context      import *
from .cli_program      import *
from .cli_program_mode import *
from .cli_argparser    import *
from .cli_utilities    import *

class CLIApp(user_module.UserModule):
    def __init__(self, 
                 appName, 
                 description,
                 version,
                 additionalInfo = ""):
        super().__init__(logs.ConfigureConsoleOnlyLogging(appName + "_Logger"))
        
        self.appName        = appName
        self.description    = description
        self.version        = version
        self.additionalInfo = additionalInfo
        self.context        = CLIContext(self.logger)

        self.argParser = argparse.ArgumentParser(prog          = self.appName,
                                                 description   = self.description,
                                                 epilog        = self.additionalInfo)

        self.configureArguments()

    # Override default usage from argparser
    def setUsage(self, appUsage):
        self.argParser.setUsage(appUsage) 

    def configureArguments(self):
        self.argParser.add_argument("-m", "--mode",             type     = str, 
                                                                help     = "Run application in interactive mode with user input.",
                                                                choices  = ["interactive", "command", "service"],
                                                                default  = "command")
        
        self.argParser.add_argument("-e", "--environment-file", type     = ArgValidator.parseFilePath,
                                                                help     = "Path to .env file.",
                                                                default  = "")
        
        self.argParser.add_argument(      "--disable-logging",  type     = str,
                                                                help     = """Disable logging for this level and below.
                                                                              Assumed to not be set enabling logging for
                                                                              all levels. Allow values: DEBUG, INFO,
                                                                              WARNING, ERROR, CRITICAL.""",
                                                                default  = "")
        
        self.argParser.add_argument(      "--log-dir",          type     = ArgValidator.parseDirPath,
                                                                help     = """Path to directory that holds logs. 
                                                                              If not specified then logging will be to console only.""",
                                                                default  = "")
        
        # TODO: debug should be used to toggle on/off debug logging.
        self.argParser.add_argument(      "--debug",            type     = bool, 
                                                                action   = argparse.BooleanOptionalAction,
                                                                help     = "Enable debug mode and logging. Defaults to false.",
                                                                default  = False)
        
        self.argParser.add_argument(      "--secrets-file",     type     = ArgValidator.parseFilePath,
                                                                help     = "Path to secrets file with API keys, passwords, etc.",
                                                                default  = "")

        self.argParser.add_argument(      "--set",              nargs    = 3,
                                                                metavar  = ("TYPE", "KEY", "VALUE"),
                                                                action   = "append",
                                                                help     = """Set env variable or secret as a key-value pair. 
                                                                            Example: --set param param1 10
                                                                                     --set secret username myusername
                                                                            """)
                

        # For debugging, enable automatic install of all packages
        self.argParser.add_argument(install.InstallFlag,        type     = bool, 
                                                                action   = argparse.BooleanOptionalAction,
                                                                help     = "Enable automatic install of all package dependencies.",
                                                                default  = False)
        
        # TODO: passthrough to underlying user logic
        self.argParser.add_argument(      "--verbose",          type      = bool, 
                                                                action    = argparse.BooleanOptionalAction,
                                                                help      = """Enable extra logging above and beyond. 
                                                                               Custom logic defined in app.""",
                                                                default   = False)
        
        self.argParser.add_argument("-v", "--version",          action    = "version",
                                                                version   = f"{self.appName} {self.version}",
                                                                help      = "Show app version and exit.")

    def parseArguments(self):
        args = None
        
        try:
            args = self.argParser.parse_args()
            if args is not None:
                # Enable logging to file?
                logsDir = args.log_dir
                if logsDir != "":
                    self.logMgr = logs.ConfigureDefaultLogging(self.appName + "_Logger", args.log_dir)
                # Debugging flag?
                self.isDebugMode = args.debug
                if not self.isDebugMode:
                    self.logMgr.suppressLogger("DEBUG") # Disable logging

                # Start logging after we've initialized
                self.logger.debug(f"Sys args: {sys.argv}")
                self.logger.debug(f"Logs dir: {logsDir}")
                self.logger.debug(f"Debug: {self.isDebugMode}")
                
                # Disable logging for this level and below.
                self.disableLoggingLevel = args.disable_logging
                if self.disableLoggingLevel != "":
                    self.logMgr.suppressLogger(self.disableLoggingLevel)
                self.logger.debug(f"Disable log level: {self.disableLoggingLevel}")
    
                # Program mode
                self.logger.debug(f"Mode: {self.context.mode}")
    
                # Environment variables can come from either environment file or os.env
                self.envFilepath = args.environment_file
                if self.envFilepath != "":
                    self.context.configureEnvVariables(os.path.expanduser(self.envFilepath))
                self.logger.debug(f"Env filepath: {self.envFilepath}")
    
                # Secrets which also utilizes .env format
                self.secretsFilepath = args.secrets_file
                if self.secretsFilepath != "":
                    self.context.configureSecrets(os.path.expanduser(self.secretsFilepath))
                self.logger.debug(f"Secrets filepath: {self.secretsFilepath}")

                # Env file and secrets can be overriden by params
                # For now triggering an exception to avoid careless error
                if args.set:
                    for entry in args.set:
                        kind, key, value = entry
                        if kind == "param":
                            self.context.setEnvVariable(key, value)
                        elif kind == "secret":
                            self.context.setSecret(key, value)
                        else:
                            raise Exception(f"Can't set key-value pair as '{kind}' is unknown.")
                            
    
                # Verbose enable
                self.context.isVerboseMode = args.verbose
                self.logger.debug(f"Verbose: {self.context.isVerboseMode}")
                
        except Exception as e:
            self.logger.exception("Unable to parse one or more arguments.")
            args = None # Failed to parse arguments

        return args

    # A bit of a chicken and the egg issue where interactive mode has to be known before the arguments are parsed
    # to install the appropriate sub_parser.
    def getModeFromArgv(self):
        modes = [m.value for m in CLIProgramMode]
        for index in range(0, len(sys.argv)-1):
            curr = sys.argv[index].lower()
            if curr == "-m" or curr == "--mode":
                mode = sys.argv[index+1].lower()
                if mode in modes:
                    self.context.mode = CLIProgramMode(mode)

        # Default to "command" mode
        if self.context.mode == CLIProgramMode.Undefined:
            self.context.mode = CLIProgramMode.Command
            
        return self.context.mode
     
    def run(self, program):
        exitCode = os.EX_USAGE    

        if program is not None:
            # If running in interactive mode create a new parser
            pgmParser = self.argParser 
            if self.getModeFromArgv() == CLIProgramMode.Interactive:
                pgmParser = CLIAppArgParser("Enter command:")
            program.initParser(pgmParser, self.context)

             # Parse env variables and configuration to successfully run program.
            parsedArgs = self.parseArguments()

            # For convenience, intercept and write out requirements.txt for 
            if parsedArgs is not None and parsedArgs.install_deps:
                status = self.writeDeps(os.getcwd(), True, False) and program.writeDeps(os.getcwd(), True)

            # Execute either as command, interactive program or (background) service
            if parsedArgs is not None and program.configure():
                try:
                    if self.context.mode == CLIProgramMode.Interactive:
                        self.logger.info(f"Running {self.appName} in interactive mode.")
                        exitCode = program.runInteractive()
                    elif self.context.mode == CLIProgramMode.Service:
                        self.logger.info(f"Running {self.appName} as a service.")
                        exitCode = program.runService()
                    elif self.context.mode == CLIProgramMode.Command:
                        self.logger.info(f"Executing a {self.appName} command.")
                        exitCode = program.runCommand(parsedArgs)
                    else:
                        self.logger.error(f"Unknown program mode: {self.context.mode}")
                        exitCode = os.EX_USAGE
                except Exception as e:
                    self.logger.exception("Exception encountered while running program.")
                    exitCode = os.EX_SOFTWARE
                
            elif program is None:
                self.logger.error("Must pass in a valid program to CLIApp's 'run'.") 
                exitCode = os.EX_SOFTWARE
            else:
                self.logger.error("CLIApp not able to parse arguments and/or configure the program.") 
                exitCode = os.EX_USAGE
        else:
            self.logger.error("CLIApp must be given a valid program to run.")

        sys.exit(exitCode)

class ArgValidator:
    def parseDirPath(path):
        if path == "" or Path(GetFullPath(path)).is_dir():
            return path
        else:
            raise NotADirectoryError(path)
                

    def parseFilePath(path):
        if path == "" or Path(GetFullPath(path)).is_file():
            return path
        else:
            raise FileNotFoundError(path)
            
def main():
    app = CLIApp("CLIApp", "CLIApp main function and simple demo.")
    app.run(CLICommand())

if __name__ == '__main__':
    main()