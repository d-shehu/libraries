import argparse
from enum import Enum
import inspect
import os
import shlex
import sys
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
        action  = None
        
        # Fallback to string if type not specified
        if argType == inspect._empty:
            argType = str
        # Convert enum options to choices but the type becomes string in parser
        elif isinstance(argType, type(Enum)):
            action = CreateEnumAction(argType)
            argType = str
            
        # If there's no default value it's required by the python function.
        isRequired = False
        if defaultVal == inspect._empty:
            isRequired = True
            defaultVal = None
            
        # Support only positional or variable. Python enforces ordering so variable args are at the end.
        if argKind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
            self.parser.add_argument(name, type = argType, action = action, default = defaultVal)
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
            raise Exception(f"Unable to invoke handler due to: {e}")

def CreateEnumAction(enumClass):
    class EnumAction(argparse.Action):
        def __init__(self, option_strings, dest, nargs=None, **kwargs):
            if nargs is not None:
                raise ValueError("nargs not allowed")
            
            kwargs["choices"] = [elem.value for elem in enumClass]
            super().__init__(option_strings, dest, **kwargs)
            
        def __call__(self, parser, namespace, values, option_string=None):
            print(f"EnumAction: {parser}, {namespace}, {values}, {option_string}")
            converted = None
            if isinstance(values, str):
                converted = enumClass(values)
            else:
                converted = [enumClass(value) for value in values]
            setattr(namespace, self.dest, converted)

    return EnumAction

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
        # Disable built-in behavior of argparser in interactive mode
        # and handle errors explicitly.
        self.argParser.setBuiltInErrorHandling(False)
        
        while not self.isDone:
            parsedArgs = None
            try:
                userInput = input("Enter command: ")
            except KeyboardInterrupt as e:
                sys.exit(os.EX_USAGE)
                
            try:
                parsedArgs = self.argParser.parse_args(shlex.split(userInput))
                self.logger.debug(f"Cmd: {parsedArgs}")    
            except Exception as e:
                self.logger.error(e)

            if parsedArgs is not None and parsedArgs.command is not None:
                try:
                    self.cmdHandlers[parsedArgs.command].invoke(parsedArgs)
                except KeyboardInterrupt as e:
                    sys.exit(os.EX_USAGE)

    def runBatch(self):
        raise Exception("CLIProgram's 'runBatch' method must be defined in child class for batch mode.")

    def handleHelp(self):
        self.argParser.print_help()
        
    def handleUsage(self):
        self.argParser.print_usage()
        
    def handleQuit(self):
        self.isDone = True