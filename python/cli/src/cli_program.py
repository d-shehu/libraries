import argparse
from enum import Enum
import inspect
import os
import shlex
import sys
from typing import get_type_hints

# Local package
from .cli_context      import *
from .cli_argparser    import *

class CLIProgram:
    def __init__(self):
        self.isDone      = False
        self.cmdParser   = None
        self.cmdHandlers = {}
        self.context     = None
        self.logger      = None

    def initParser(self, argParser, context, logger):
        self.context     = context
        self.argParser   = argParser
        self.cmdParser   = self.argParser.add_subparsers(dest = "command", help = "Interactive command help") 
        self.logger      = logger

        # Declare handlers. This can be overriden in subclass.
        self.defineHandlers()
        
    def configure(self) -> bool:
        self.logger.warning("Recommend overriding configure to further initialize your program based on given context.")
        return True

        # Further initialization based on configs
        return self.doConfigure()
    
    # Handlers for built-in functionality
    def defineHandlers(self):
        self.cmdHandlers = {
            "help":  CLICommand(self.cmdParser, "help",  self.handleHelp,  "Print usage information."),
            "usage": CLICommand(self.cmdParser, "usage", self.handleUsage, "Print help information.")
        }

        if self.context.mode == CLIProgramMode.Interactive:
            self.addHandler(
                CLICommand(self.cmdParser, "quit",  self.handleQuit,  "Exit from interactive mode.")
            )

        # Install interactive handlers
        self.defineCustomHandlers()

    # To be overriden by child program class
    def defineCustomHandlers(self):
        raise Exception("CLIProgram's 'defineCustomHandlers' function must be overriden in child class.")
    
    # Dynamically add handler for commands in interactive mode
    def addHandler(self, cliCommand):
        success = False
        
        name = cliCommand.name
        if name in self.cmdHandlers:
            self.logger.error(f"Command {name} already has a handler")
        else:
            self.cmdHandlers[name] = cliCommand
            success = True

        return success

    # Dynamically remove handler for commands in interactive mode
    def removeHandler(self, cliCommand):
        success = False
        
        name = cliCommand.name
        if name in self.cmdHandlers:
            self.cmdHandlers.pop(name)
            # TODO: remove from command parser
        else:
            self.logger.error(f"Command {name} doesn't have a handler")

        return success
            
    def runInteractive(self):
        exitCode = os.EX_OK
        
        while not self.isDone and exitCode == os.EX_OK:
            parsedArgs = None
            
            try:
                userInput = input("Enter command: ")
                parsedArgs = self.argParser.parse_args(shlex.split(userInput)) 
                
                # Keep running until user exits
                if self.runCommand(parsedArgs) != os.EX_OK and parsedArgs is not None:
                    self.logger.debug(f"Failed to run command: {parsedArgs}")
                    self.argParser
            # Intercept but don't exit for malformed arguments in interactive mode
            except (argparse.ArgumentError, CLIAppArgumentError, CLIAppParserExit) as e:
                self.logger.error(e)
                self.logger.error(f"Enter <command> -h for the specific interactive command.") 
            # Intercept ctlr-c so user can exit without triggering exception
            except KeyboardInterrupt as e:
                exitCode = os.EX_USAGE
            # Intercept all other exceptions and set flag to generic "usage" error
            except Exception as e:
                self.logger.exception(e)
                exitCode = os.EX_USAGE

        return exitCode

    def runCommand(self, parsedArgs):
        exitCode = os.EX_USAGE

        if parsedArgs is not None and getattr(parsedArgs, "command", None) is not None:
            try:
                if self.cmdHandlers[parsedArgs.command].invoke(parsedArgs):
                    exitCode = os.EX_OK
                else:
                    exitCode = os.EX_SOFTWARE
            except Exception as e:
                self.logger.exception(f"Unable to run '{parsedArgs.command}' with parameters '{parsedArgs}':")
                exitCode = os.EX_SOFTWARE
        # If no command specify explicitly print usage.
        elif getattr(parsedArgs, "command", None) is None:
            self.argParser.print_usage()

        return exitCode
                
    def runService(self):
        self.logger.error("CLIProgram's 'runService' method must be defined in child class for batch mode.")
        return os.EX_UNAVAILABLE

    def handleHelp(self) -> bool:
        self.argParser.print_help()
        return True
        
    def handleUsage(self) -> bool:
        self.argParser.print_usage()
        return True
        
    def handleQuit(self) -> bool:
        self.isDone = True
        return True

# Encapsulate interactive command
class CLICommand:
    def __init__(self,
                 subparsers,
                 name,
                 funHandler, 
                 helpStr = "",
                 inferArgs = True
                 ):
        self.name       = name
        self.funHandler = funHandler
        self.helpStr    = helpStr
        self.inferArgs  = inferArgs

        # Add parser for this argument
        self.parser     = subparsers.add_parser(self.name, help = self.helpStr)
        
        # Infer arguments from handler signature
        if self.inferArgs:
            self.__deriveArgs()

    # Try to derive automatically from function sig
    def __deriveArgs(self):
        try:
            funSignature = inspect.signature(self.funHandler)
            # For each parameter
            for name, param in funSignature.parameters.items():
                self.__addArgument(name, param.kind, param.annotation, param.default)
        except Exception as e:
            raise Exception("Unable to derive argParser args from function signature: ", e)

    def __addArgument(self, name, argKind, argType, defaultVal):
        action  = None
        
        # Fallback to string if type not specified
        if argType == inspect._empty:
            argType = str
        # Convert enum options to choices but the type becomes string in parser
        elif isinstance(argType, type(Enum)):
            action = CreateEnumAction(argType)
            argType = str

        params = {
            "type":    argType,
            "action":  action,
            "default": None
        }
        
        # If there's no default value it's required by the python function.
        isRequired = False
        if defaultVal != inspect._empty:
            name = "--" + name
            params["default"] = defaultVal
            params["required"] = isRequired
        else:
            isRequired = True
            
        if argKind == inspect.Parameter.VAR_POSITIONAL:
            # Either requires at least one or value or otherwise it can be empty and returns default.
            nargsVal = "+" if isRequired else "*" 
            params["nargs"] = nargsVal
            
        # Support only positional or variable. Python enforces ordering so variable args are at the end.
        if (argKind == inspect.Parameter.POSITIONAL_OR_KEYWORD or argKind == inspect.Parameter.VAR_POSITIONAL):
            self.parser.add_argument(name, **params)
        else:
            raise Exception(f"Only positional/keyword or variable arguments supported: {argKind}")

    # Get argument parser so user can customize as desired
    def getParser(self):
        return self.parser

    def invoke(self, parsedArgs):
        success = False
        
        try:
            funSignature = inspect.signature(self.funHandler)
            # For each parameter
            paramList = []
            for name, param in funSignature.parameters.items():
                # Fetch value for argument from parsed arguments and
                # append to param list. 
                argValue = getattr(parsedArgs, name)
                if type(argValue) is list:
                    paramList.extend(argValue)
                else:
                    paramList.append(argValue)

            # Invoke the function with the param list
            success = self.funHandler(*paramList)
        except Exception as e:
            raise Exception(f"Unable to invoke handler due to: {e}")

        return success

def CreateEnumAction(enumClass):
    class EnumAction(argparse.Action):
        def __init__(self, option_strings, dest, nargs=None, **kwargs):
            if nargs is not None:
                raise ValueError("nargs not allowed")
            
            kwargs["choices"] = [elem.value for elem in enumClass]
            super().__init__(option_strings, dest, **kwargs)
            
        def __call__(self, parser, namespace, values, option_string=None):
            converted = None
            if isinstance(values, str):
                converted = enumClass(values)
            else:
                converted = [enumClass(value) for value in values]
            setattr(namespace, self.dest, converted)

    return EnumAction