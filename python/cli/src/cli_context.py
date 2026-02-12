from dotenv         import dotenv_values, set_key
from pathlib        import Path
from typing         import TypeVar

import os

from .cli_program_mode import *
from .cli_utilities    import *

# Generic type
T = TypeVar("T")

class CLIContext:
    def __init__(self, logger):
        self.envVariables  = {}
        
        self.mode           = CLIProgramMode.Undefined
        self.isVerbose      = False
        self.lookInOSEnv    = True
        self.logger         = logger

        self.envPath        = ""

    def configureEnvVariables(self, path: Path):
        self.envPath = GetFullPath(path)
        self.logger.debug("Env Path: " + self.envPath)
        self.envVariables = dotenv_values(self.envPath)

    def setLookInOSEnv(self, enabled: bool):
        self.lookInOSEnv = enabled

    def getEnvVariableBool(self, key: str) -> bool:
        value = self.getEnvVariableStr(key, "false")
        # Unless explicitly set to false/0 or true/1 then raise exception
        # as value not supported for bool.
        if value.lower() == "false" or value == 0:
            return False
        elif value.lower() == "true" or value == 1:
            return True
        else:
            raise Exception(f"Env variable {key} has non bool value {value}")
    
    # Get environment variables either from OS environment or file
    def getEnvVariable(self, key: str, defaultValue = None):
        value = None

        # Look first in app env variables
        if key in self.envVariables:
            value = self.envVariables[key]
        # Fall back to OS env if enabled
        elif self.lookInOSEnv and key in os.environ:
            value = os.environ[key]

        # Throw exception if this variable must be set?
        if value is None:
            value = defaultValue

        # Warn user that env file may not have been loaded
        if value is None:
            self.logger.warning(f"Unable to find {key} perhaps because env file not loaded.")

        return value
    
    def getEnvVariableOfType(self, key: str, defaultValue: T) -> T:
        value: T = defaultValue

        config = self.getEnvVariable(key, defaultValue)
        if value is not None:
            value = type(defaultValue)(config)

        return value
    
    def getEnvVariableStr(self, key: str, defaultValue = "") -> str:
        return str(self.getEnvVariable(key, defaultValue))

    def setEnvVariable(self, key, value, warnIfSet = True, doPersist = True):
        if key in self.envVariables and warnIfSet:
            self.logger.warning(f"{key} param already set.")
        self.envVariables[key] = value

        if doPersist:
            set_key(self.envPath, key, value)


    def getDirectory(self, envDirectory) -> Path:
        dirPath = Path()
        try:
            pathStr = self.getEnvVariable(envDirectory)
            if pathStr is not None:
                path = Path(Path(pathStr).expanduser().resolve())
                if not path.is_dir():
                    raise Exception(f"Directory '{path}' does not exist.")
                dirPath = path
            else:
                raise Exception("Unable to fetch env variable: '{envDirectory}'")
        except Exception as e:
            self.logger.exception(f"Unable to get directory from env var")
        
        return dirPath