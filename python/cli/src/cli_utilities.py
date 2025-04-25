import os

# Utility function that replaces env vars and convert to absolute path
def GetFullPath(path):
    return os.path.abspath(os.path.expandvars(path))
    