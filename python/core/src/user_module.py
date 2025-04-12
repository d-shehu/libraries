from collections import deque
from importlib import reload # Reload packages
import importlib.util
import os
from pathlib import Path
import pkgutil
import subprocess
import sys
from types import ModuleType

from .logs import *

# Assume user module reside under the packages directory as shown here:
# ... / <packages> / <package_1> / <src> / module
class UserModule:
    def __init__(self, module, projectDir = "."):
        self.logger = ConfigureConsoleOnlyLogging("UserModuleLogger").getSysLogger()
        self.module = module
        self.packagePath = os.path.abspath(os.path.dirname(os.path.dirname(module.__file__)))

        # Search only within user's project or otherwise derive package's parent directory
        if projectDir != ".":
            self.projectDir = projectDir    
        else:
            self.projectDir = os.path.abspath(os.path.dirname(self.packagePath))
    
    def getLogger(self):
        return self.logger

    def setLogger(self, logger):
        self.logger = logger

    def getProjectDir(self):
        return self.projectDir

    def setProjectDir(self, projectDir):
        self.projectDir = projectDir
    
    def getModule(self):
        return self.module
        
    def getPackagePath(self):
        return self.packagePath

    # Install dependencies of associated package and all other packages upon which this module is dependent.
    # Useful for debugging and testing.
    def installDeps(self, recursive = True):
        action = InstallDepsAction()
        if recursive:
            self.iterateDeps(action)
        else:
            action(self)

        return self

    def writeDeps(self, outPath, recursive = True):
        action = GetDepsAction()
        if recursive:
            self.iterateDeps(action)
        else:
            action(self)

        lsRequirements = action.getRequirements()
        try:
            with open(outPath, "w") as file:
                for requirement in lsRequirements:
                    file.write(requirement)
        except Exception as e:
            self.logger.exception(LogLine("Unable to write exception for ", self.module))

    # Reload just this module or also all of it's dependencies recursively.
    # Inspiration: https://stackoverflow.com/questions/15506971/recursive-version-of-reload
    def reload(self, recursive = True):
        action = ReloadAction()
        if recursive:
            self.iterateDeps(action)
        else:
            action(self)
            
        return self

    def iterateDeps(self, action):
        q = deque() # Track of dependencies
        q.appendleft(self)

        while len(q) > 0:
            currUserModule = q.pop()
            currModule = currUserModule.module
            action(currUserModule)

            # Recusrively get user packages that are reference by this module
            for attribute_name in dir(currModule):
                attribute = getattr(currModule, attribute_name)
    
                if (type(attribute) is ModuleType
                    and hasattr(attribute, '__file__') 
                    and attribute.__file__ 
                   ):
                    self.logger.debug(f"Dep Module: {attribute}") 
                    pathToModule = os.path.abspath(attribute.__file__)
                    if pathToModule.startswith(self.projectDir):
                        # Qualifies as a user module on which to action
                        q.appendleft(UserModule(module = attribute, projectDir = self.projectDir))


class Action:
    def __init__(self):
        # To avoid re-running the same action over and over, track modules.
        self.actionSet = set() 
        
    def __call__(self, userModule):
        userModuleFile = os.path.abspath(userModule.getModule().__file__)
        if not userModuleFile in self.actionSet:
            self.actionSet.add(userModuleFile)
            self._doAction(userModule)
        else:
            userModule.getLogger().debug(f"Action already run on {userModuleFile}")

    def _doAction(self):
        raise Exception("Implement Action's _doAction() in child class")
        
class InstallDepsAction(Action):        
    def _doAction(self, userModule):
        path = userModule.getPackagePath()
        InstallDependencies(path, userModule.getLogger())

class GetDepsAction(Action):
    def __init__(self):
        lsRequirements = []
        
    def _doAction(self, userModule):
        requirementsPath = Path(f"{path}/requirements.txt")
        if requirementsPath.is_file():
            try:
                with open(requirementsPath, "r") as file:
                    for line in file:
                        self.lsRequirements.append(line)
                        
            except Exception as e:
                userModule.getLogger().exception(f"Unable to read packages from requirements file: {requirementsPath}")

    def getRequirements():
        self.lsRequirements.sort()
        return self.lsRequirements
        
        
class ReloadAction(Action):
    def _doAction(self, userModule):
        userModule.getLogger().debug(LogLine("Reload: ", userModule.getModule()))
        reload(userModule.getModule())

def InstallDependencies(path, logger):
    logger.debug(f"Installing dependencies from {path} ...")
    requirementsPath = Path(f"{path}/requirements.txt")
    if requirementsPath.is_file():
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-qr", requirementsPath])
    else:
        logger.warning(f"Requirements file missing from: {path}") 

def LoadFromFile(moduleName, package, libPath = ".", doInstall = True, doReload =  False, projectDir = "."):
    
    # TODO: consider if it's possible to configure logging before loading module.
    logger = ConfigureConsoleOnlyLogging("LoadFromFile").getSysLogger()
    
    packagePath = Path(libPath) / Path(package.replace(".", os.path.sep))

    # Must install deps before loading module.
    InstallDependencies(packagePath, logger)
    
    module = importlib.import_module("." + moduleName, package + ".src")    
    userModule = UserModule(module, projectDir)
    
    # Simplify dev for local packages by reloading all modules and deps recursively
    if doInstall:
        userModule.installDeps(True)
    if doReload:
        userModule.reload(True) 
    
    return module
