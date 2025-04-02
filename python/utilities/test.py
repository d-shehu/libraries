import time

from .common import *

# Basic test to make sure key functions work. Pass in the class of tracker.
def fnTestProgressTracker(progressTrackerClass, description, minVal, maxVal, stepVal, delayInSecs = .100):
    success = False
    
    try:
        progressTracker = progressTrackerClass(minVal, maxVal, description)

        print("Info: testing progress tracking using value...")
        for i in range(minVal, maxVal, stepVal):
            progressTracker.set_value(i + stepVal)
            time.sleep(delayInSecs)

        if progressTracker.is_complete():
            progressTracker.reset()
            print("Info: testing progress tracking using percent...")
            for i in range(0, 101, 5):
                progressTracker.set_percent(i)
                time.sleep(delayInSecs)

            success = progressTracker.is_complete()

    except Exception as e:
        print()
        print("Error: encountered exception while running ProgressTrackerCLI tests")
        print(e)

    return success

# TODO: should be run from Jupyter notebook
def fnTestProgressTrackers(testCLI = True, testGUI = False):
    if testCLI:
        progressTrackerClass = ProgressTrackerCLI
        if fnTestProgressTracker(progressTrackerClass, "Progress: ", 3, 30, 3, delayInSecs = .05):
            print("Info: ProgressTrackerCLI test passed")
        else:
            print("Info: ProgressTrackerCLI test failed")
        

    if testGUI:
        progressTrackerClass = ProgressTrackerGUI
        if fnTestProgressTracker(progressTrackerClass, "Progress: ", 3, 30, 3, delayInSecs = .05):
            print("Info: ProgressTrackerCLI test passed")
        else:
            print("Info: ProgressTrackerCLI test failed")

# Main Function: run tests
def main():
    fnTestProgressTrackers()
    
if __name__=="__main__":
    main()