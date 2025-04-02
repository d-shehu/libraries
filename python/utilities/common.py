from collections import deque
from importlib import reload # Reload packages
from ipywidgets import FloatProgress
import math
import os
import sys
from types import ModuleType

class ProgressTracker:
    def __init__(self, minVal = 0, maxVal = 100, description = "Progress: "):
        self.set_description(description)
        self.set_range(minVal, maxVal)
        self.reset()

    def __del__(self):
        self.reset()

    def set_range(self, minVal, maxVal):
        self.minVal      = minVal
        self.maxVal      = maxVal
        if self.maxVal <= self.minVal:
            raise Exception(f"Invalid ProgressTracker range: {self.minVal} - {self.maxVal}")
        self.reset()

    def set_description(self, description):
        self.description = description
        
    def reset(self):
        self.value = self.minVal
        self._init_bar()
        self._update_progress()
    
    def set_value(self, value):
        if value > (self.maxVal + sys.float_info.epsilon) or value < (self.minVal - sys.float_info.epsilon):
            raise Exception(f"Value of {value} is out of ProgressTracker range: {self.minVal} - {self.maxVal}")
        else:
            self.value = value
            self._update_progress()

    def increment_value(self, delta):
        self.set_value(self.value + delta)

    def set_percent(self, percent):
        if percent > (100 + sys.float_info.epsilon) or percent < (-sys.float_info.epsilon):
            raise Exception(f"ProgressTracker percent value of {percent}  must be in range of 0 - 100.0")
        else:
            self.value = ((percent/100.0) * (self.maxVal-self.minVal)) + self.minVal;
            self._update_progress()

    def increment_percent(self, delta):
        curr = (self.maxVal-self.minVal) / float(self.minVal)
        self.set_percent(self.value + delta)

    def complete(self):
        self.value = self.maxVal
        self._update_progress()

    def is_complete(self):
        return (math.fabs(self.maxVal - self.value) < sys.float_info.epsilon)

    def _init_bar(self):
        raise Exception("ProgressTracker _init_bar function must be implemented in child class.")
        
    def _update_progress(self):
        raise Exception("ProgressTracker _update_progress function must be implemented in child class.")


class ProgressTrackerGUI(ProgressTracker):
    def __init__(self, minVal = 0, maxVal = 100, description = "Progress: "):
        super().__init__(minVal, maxVal, description)

    def __del__(self):
        del self.progressBar

    def _init_bar(self):
        if hasattr(self, 'progressBar') and self.progressBar is not None:
            del self.progressBar
            
        self.progressBar = FloatProgress(min = self.minVal, max = self.maxVal, description = self.description)
        self.progressBarVisible = False

    def _update_progress(self):
        if self.progressBar is not None:
            self.progressBar.value = self.value
            # Delay showing progress bar until we've started processing something
            if self.value > self.minVal and not self.progressBarVisible:
                display(self.progressBar)
                self.progressBarVisible = True

class ProgressTrackerCLI(ProgressTracker):
    def __init__(self, minVal = 0, maxVal = 100, description = "Progress: ", numDecimals = 1, progressBarLen = 100):
        self.numDecimals    = numDecimals
        self.progressBarLen = progressBarLen
        super().__init__(minVal, maxVal, description)

    def _init_bar(self):
        self._update_progress()
        
    # Inspired by: https://stackoverflow.com/questions/3173320/text-progress-bar-in-terminal-with-block-characters
    def _update_progress(self):
        # Delay showing progress bar until we've started processing something
        if self.value > self.minVal:
            progress = (self.value - self.minVal) / float(self.maxVal - self.minVal)
            percent = ("{0:." + str(self.numDecimals) + "f}").format(100 * progress)
            
            fillLen = math.ceil(self.progressBarLen * progress)
            progressBar = fillLen * '█' + '-' * (self.progressBarLen - fillLen)
            
            print(f"\r{self.description}: |{progressBar}| {percent}% Complete", end = "\r")
            # Show completion with newline if close enough to done.
            if self.value > (self.maxVal - sys.float_info.epsilon):
                print() 

def fnInstallDependencies():
    scriptParentDir = pathlib.Path(__file__).parent.resolve()
    subprocess.check_call([sys.executable, "-m", "pip", "install", f"{scriptParentDir}/requirements.txt"])

# Reload user package and all other user packages it's dependent on. Useful for debugging and testing.
# Inpsiration from: https://stackoverflow.com/questions/15506971/recursive-version-of-reload
def fnRecursiveReload(module, projectDir = ""):
    if projectDir == "":
        # Assume user packages reside in the parent directory of this package.
        projectDir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
    print("Info: project directory: ", projectDir)
    q = deque()
    q.appendleft(module)

    while len(q) > 0:
        curr_module = q.pop()
        print("Info: reloading module: ", curr_module)
        reload(curr_module)
        
        # Recusrively get user packages that are reference by this module
        for attribute_name in dir(curr_module):
            attribute = getattr(curr_module, attribute_name)

            #print("Check attribute: ", attribute)
            #print("File Attr: ", hasattr(attribute, '__file__'))
            if (type(attribute) is ModuleType
                and hasattr(attribute, '__file__') 
                and attribute.__file__ 
                #and type(attribute) is ModuleType
               ):
                pathToModule = os.path.abspath(attribute.__file__)
                if pathToModule.startswith(projectDir):
                    # Qualifies as a module to be-reloaded
                    q.appendleft(attribute)