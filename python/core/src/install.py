from pathlib import Path
import subprocess
import sys

from .logs import *

InstallFlag = "--install-deps"

# Set the flag in args to indicate if install dependencies.
# Useful for debugging when pip hasn't been run.
def SetInstallFlag(enabled: bool):
    if enabled and not InstallFlag in sys.argv:
        sys.argv.append(InstallFlag)
    elif not enabled and InstallFlag in sys.argv:
        sys.argv.remove(InstallFlag)

def InstallDependencies(path, logger = ConfigureConsoleOnlyLogging("InstallDependencies").getSysLogger()):
    if InstallFlag in sys.argv:
        logger.debug(f"Installing dependencies from {path} ...")
        requirementsPath = Path(f"{path}/requirements.txt")
        if requirementsPath.is_file():
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-qr", requirementsPath])
        else:
            logger.warning(f"Requirements file missing from: {path}")