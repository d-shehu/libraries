import os

from dotenv import dotenv_values

from .cli_program_mode import *

class CLIContext:
    def __init__(self, logger):
        self.envVariables  = {}
        self.secrets       = {}
        self.mode          = CLIProgramMode.Undefined
        self.isVerbose     = False
        self.lookInOSEnv   = True
        self.logger        = logger
        
    def configureEnvVariables(self, path):
        self.envVariables = dotenv_values(path)

    def configureSecrets(self, path):
        self.secrets = dotenv_values(path)

    def setLookInOSEnv(self, enabled):
        self.lookInOSEnv = enabled

    # Get environment variables either from OS environment or file
    def getEnvVariable(self, key, defaultValue = None):
        value = None

        # Look first in app env variables
        if key in self.envVariables:
            value = self.envVariables[key]
        # Fall back to OS env if enabled
        elif self.lookInOSEnv and key in os.environ:
            value = os.environ[key]

        # Throw exception if this variable must be set
        if value is None:
            value = defaultValue

        # Warn user that env file may not have been loaded
        if value is None:
            self.logger.warning(f"Unable to find {key} perhaps because env file not loaded.")

        return value

    def getSecret(self, key):
        value =  None

        if key in self.secrets:
            value = self.secrets[key]

        return value