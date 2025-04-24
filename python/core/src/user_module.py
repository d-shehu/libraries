from collections import deque
from importlib import reload # Reload packages
import importlib.util
import os
from pathlib import Path
import pkgutil
import sys
from types import ModuleType

from .logs    import *
from .install import *

# Assume user module reside under the packages directory as shown here:
# ... / <packages> / <package_1> / <src> / module
class UserModule:
    def __init__(self, 
                 logMgr = ConfigureConsoleOnlyLogging("UserModuleLogger"), 
                 module = None, 
                 projectDir = "."
                ):
        self._module = module if not module is None else sys.modules[self.__class__.__module__]
        self._packagePath = os.path.abspath(os.path.dirname(os.path.dirname(self.module.__file__)))
        self._logMgr = logMgr

        self.logger.debug(f"Module: {self._module}")
        self.logger.debug(f"Package Path: {self._packagePath}")

        # Search only within user's project or otherwise derive package's parent directory
        if projectDir != ".":
            self._projectDir = os.path.abspath(projectDir)    
        else:
            self._projectDir = os.path.abspath(os.path.dirname(self.packagePath))

    @property
    def logMgr(self):
        return self._logMgr

    # Logmgr can be overriden after initial initialization but not recommended as it can
    # break up logs.
    @logMgr.setter
    def logMgr(self, logMgr):
        self._logMgr = logMgr
    
    # Logger should be read only as only the logmgr can be modified.
    @property
    def logger(self):
        return self._logMgr.getSysLogger()

    @property
    def projectDir(self):
        return str(self._projectDir)

    @projectDir.setter
    def projectDir(self, projectDir):
        self._projectDir = projectDir

    @property
    def module(self):
        return self._module

    @property
    def packagePath(self):
        return self._packagePath

    # Install dependencies of associated package and all other packages upon which this module is dependent.
    # Useful for debugging and testing.
    def installDeps(self, recursive = True):
        action = InstallDepsAction()
        if recursive:
            self.iterateDeps(action)
        else:
            action(self)

        return self

    def writeDeps(self, outDir, recursive = True, append = True):
        success = False
        
        action = GetDepsAction()
        if recursive:
            self.iterateDeps(action)
        else:
            action(self)

        requirementsFilepath = Path(outDir) / Path("requirements.txt")
        try:
            if append:
                action.readRequirements(requirementsFilepath)
            self.logger.debug(f"Requirements for: {self.module}")
            lsRequirements = action.getRequirements()
            with open(requirementsFilepath, "w") as file:
                for requirement in lsRequirements:
                    file.write(requirement + "\n")
            success = True
        except Exception as e:
            self.logger.exception(LogLine("Unable to write exception for ", self.module))

        return success

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

        self.logger.debug(f"Project dir {self.projectDir}")
        self.logger.debug(f"Iterating on action {action} for {self}")
        
        while len(q) > 0:
            currUserModule = q.pop()
            currModule = currUserModule.module
            self.logger.debug(f"Action {action} on {currModule}")
            action(currUserModule)

            # Recusrively get user packages that are reference by this module
            for attribute_name in dir(currModule):
                attribute = getattr(currModule, attribute_name)
    
                if (type(attribute) is ModuleType
                    and hasattr(attribute, '__file__') 
                    and attribute.__file__ 
                   ):
                    pathToModule = os.path.abspath(attribute.__file__)
                    if pathToModule.startswith(self.projectDir):
                        self.logger.debug(f"Dep Module: {attribute} at {pathToModule}") 
                        self.logger.debug(f"Project dir {self.projectDir}")
                        # Qualifies as a user module on which to action
                        q.appendleft(UserModule(self.logMgr, module = attribute, projectDir = self.projectDir))


class Action:
    def __init__(self):
        # To avoid re-running the same action over and over, track modules.
        self.actionSet = set() 
        
    def __call__(self, userModule):
        userModuleFile = os.path.abspath(userModule.module.__file__)
        if not userModuleFile in self.actionSet:
            self.actionSet.add(userModuleFile)
            self._doAction(userModule)
        else:
            userModule.logger.debug(f"Action already run on {userModuleFile}")

    def _doAction(self):
        raise Exception("Implement Action's _doAction() in child class")
        
class InstallDepsAction(Action):
    def __init__(self):
        super().__init__()
        
    def _doAction(self, userModule):
        path = userModule.packagePath
        InstallDependencies(path, userModule.logger)

class GetDepsAction(Action):
    def __init__(self):
        super().__init__()
        self.lsRequirements = []
        
    def _doAction(self, userModule):
        self.readRequirements(
            Path(userModule.packagePath) / Path("requirements.txt")
        )
        

    def readRequirements(self, requirementsPath):
        if requirementsPath.is_file():
            try:
                with open(requirementsPath, "r") as file:
                    for line in file:
                        self.lsRequirements.append(line)
                        
            except Exception as e:
                userModule.logger.exception(f"Unable to read packages from requirements file: {requirementsPath}")
        

    # Remove duplicates, empty entries and sort
    def cleanup(self):
        self.lsRequirements = list(set(map(
            lambda item: item.strip(), filter(lambda item: item != "", self.lsRequirements)
        )))
        self.lsRequirements.sort()
        
    def getRequirements(self):
        self.cleanup()
        return self.lsRequirements
        
        
class ReloadAction(Action):
    def __init__(self):
        super().__init__()
        
    def _doAction(self, userModule):
        userModule.logger.debug(f"Reload {userModule.module}")
        reload(userModule.module)

def LoadFromFile(moduleName, package, libPath = ".", doInstall = True, doReload =  False, projectDir = "."):
    
    # TODO: consider if it's possible to configure logging before loading module.
    logger = ConfigureConsoleOnlyLogging("LoadFromFile").getSysLogger()
    
    packagePath = Path(libPath) / Path(package.replace(".", os.path.sep))

    # Must install deps before loading module.
    InstallDependencies(packagePath, logger)
    
    module = importlib.import_module("." + moduleName, package + ".src")    
    userModule = UserModule(logger, module, projectDir)
    
    # Simplify dev for local packages by reloading all modules and deps recursively
    if doInstall:
        userModule.installDeps(True)
    if doReload:
        userModule.reload(True) 
    
    return module
