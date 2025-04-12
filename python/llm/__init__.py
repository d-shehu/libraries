import os
import subprocess
import sys

def init():
    packagePath = os.path.abspath(os.path.dirname(__file__))
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-qr", 
                           os.path.join(packagePath, "requirements.txt")])

    from .src import llm_manager

init()
