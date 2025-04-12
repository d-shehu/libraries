import argparse
from enum import Enum
import inspect
import os
import shlex
from typing import get_type_hints

# Local package
from .cli_context import *

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
        
        choices = None
        # Fallback to string if type not specified
        if argType == inspect._empty:
            argType = str
        # Convert enum options to choices but the type becomes string in parser
        elif isinstance(argType, type(Enum)):
            choices = [elem.value for elem in argType] 
            argType = str

        # If there's no default value it's required by the python function.
        isRequired = False
        if defaultVal == inspect._empty:
            isRequired = True
            defaultVal = None
            
        # Support only positional or variable. Python enforces ordering so variable args are at the end.
        if argKind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
            self.parser.add_argument(name, type=argType, choices = choices, default = defaultVal)
        elif argKind == inspect.Parameter.VAR_POSITIONAL:
            # Either requires at least one or value or otherwise it can be empty and returns default.
            nargsVal = "+" if isRequired else "*" 
            self.parser.add_argument(name, type=argType, nargs = nargsVal, default = defaultVal)
        else:
            raise Exception(f"Only positional/keyword or variable arguments supported: {argKind}")

    # Get argument parser so user can customize as desired
    def getParser(self):
        return self.parser

    def invoke(self, parsedArgs):
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
            self.funHandler(*paramList)
        except Exception as e:
            raise Exception("Unable to invoke handler due to: ", e)

class CLIProgram:
    def __init__(self):
        self.isDone      = False
        self.cmdParser   = None
        self.cmdHandlers = {}
        self.context     = None
        self.logger      = None

    def configure(self, argParser, context, logger):
        self.argParser   = argParser
        self.cmdParser   = self.argParser.add_subparsers(dest = "command", help = "Interactive command help")
        self.context     = context
        self.logger      = logger

        # Declare handlers. This can be overriden in subclass.
        self.defineHandlers()

    # Handlers built-in
    def defineHandlers(self):
        self.cmdHandlers = {
            "help":  CLICommand(self.cmdParser, "help",  self.handleHelp,  "Print usage information."),
            "usage": CLICommand(self.cmdParser, "usage", self.handleUsage, "Print help information."),
            "quit":  CLICommand(self.cmdParser, "quit",  self.handleQuit,  "Exit from interactive mode.")
        }
    
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
        while not self.isDone:
            userInput = input("Enter command: ")
            parsedArgs = self.argParser.parse_args(shlex.split(userInput))
            self.logger.debug(f"Cmd: {parsedArgs}")
            self.cmdHandlers[parsedArgs.command].invoke(parsedArgs)

    def runBatch(self):
        raise Exception("CLIProgram's 'runBatch' method must be defined in child class for batch mode.")

    def handleHelp(self):
        self.argParser.print_help()
        
    def handleUsage(self):
        self.argParser.print_usage()
        
    def handleQuit(self):
        self.isDone = True