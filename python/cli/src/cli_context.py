import os

from dotenv import dotenv_values

class CLIContext:
    def __init__(self):
        self.envVariables  = {}
        self.secrets       = {}
        self.isInteractive = False
        self.isVerbose     = False
        
    def configureEnvVariables(self, path):
        self.envVariables = dotenv_values(path)

    def configureSecrets(self, path):
        self.secrets = dotenv_secrets(path)

    # Get environment variables either from OS environment or file
    def getEnvVariables(self, key, required = False, fromOS = False):
        value = None
        
        if fromOS and key in os.environ:
            value = os.environ[key]
        elif not fromOS and key in self.envVariables:
            value = self.envVariables

        # Throw exception if this variable must be set
        if value is None and required:
            raise Exception(f"Env variable with key {key} not found.")

        return value

    def getSecret(self, key):
        value =  None

        if key in self.secrets:
            value = self.secrets[key]
        else:
            raise Exception(f"Secret {key} not found.")

        return value