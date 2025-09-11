from dotenv         import dotenv_values
from enum           import Enum
from pathlib        import Path

import collections.abc
import os

from .cli_program_mode import *
from .cli_utilities    import *

class CLIContext:
    def __init__(self, logger):
        self.envVariables  = {}
        self.secrets       = {}
        self.mode          = CLIProgramMode.Undefined
        self.isVerbose     = False
        self.lookInOSEnv   = True
        self.logger        = logger
        
    def configureEnvVariables(self, path):
        self.logger.debug("Env Path: " + GetFullPath(path))
        self.envVariables = dotenv_values(GetFullPath(path))

    def configureSecrets(self, path):
        self.logger.debug("Secrets Path: " + GetFullPath(path))
        self.secrets = dotenv_values(GetFullPath(path))

    def setLookInOSEnv(self, enabled):
        self.lookInOSEnv = enabled

    def getEnvVariableBool(self, key) -> bool:
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
    def getEnvVariable(self, key, defaultValue = None):
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
    
    def getEnvVariableStr(self, key, defaultValue = "") -> str:
        return str(self.getEnvVariable(key, defaultValue))

    def setEnvVariable(self, key, value, warnIfSet = True):
        if key in self.envVariables and warnIfSet:
            self.logger.warning(f"{key} param already set.")
        self.envVariables[key] = value


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

    # TODO: consider changing to SecretStr
    def getSecret(self, key):
        value =  None

        if key in self.secrets:
            value = self.secrets[key]

        return value
    
    def getSecretStr(self, key) -> str:
        secret = self.getSecret(key)
        return secret if secret is not None else ""

    def setSecret(self, key, value, warnIfSet = True):
        if key in self.secrets and warnIfSet:
            self.logger.warning(f"{key} secret already set.")
        self.secrets[key] = value

    # TODO: caution as this returns all secrets to caller
    # A proper security model would restrict secrets base
    # on roles, etc.
    def getReadOnlySecrets(self):
        return self.secrets

class ROSecrets(collections.abc.Mapping):

    def __init__(self, data):
        self.__data = data

    def __getitem__(self, key): 
        return self.__data[key]

    def __len__(self):
        return len(self.__data)

    def __iter__(self):
        return iter(self.__data)