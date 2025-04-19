import math
import sys
import time

from ipywidgets import FloatProgress, Label, HBox

from .filters import MovingAverage

class ProgressTracker:
    def __init__(self, minVal = 0, maxVal = 100, description = "Progress"):
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
        # Time calc
        self.currTime = 0
        self.currValue = 0
        self.estimatedTimeSecs = 0
        self.showTime = False
        self.totalTime = 0
        self.movAvg = MovingAverage(10) # Use 10 samples to smooth out estimate
        
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
        # Don't start tracking time until we're progress
        if self.value > 0:
            newTime = time.time()
            if self.currTime > 0:
                # Rough inst. calculation 
                deltaTime = newTime - self.currTime
                deltaVal  = self.value - self.currValue
                if deltaVal > 0:
                    self.movAvg.push((deltaTime / deltaVal))
                    estSecsPerUnit = self.movAvg.average()
                    self.estimatedTimeSecs = (self.maxVal - self.value) * estSecsPerUnit
                    
                self.totalTime += (newTime - self.currTime)
                
            self.currTime = newTime
            self.currValue = self.value

        self._do_update_progress()

    def get_time_estimate(self):
        estimateLabel = ""
        # Show estimate in seconds
        if self.estimatedTimeSecs > 10 and self.estimatedTimeSecs <= 60:
            estimateLabel = "{:2.0f} sec".format(self.estimatedTimeSecs)
        # Minutes and seconds
        elif self.estimatedTimeSecs > 60 and self.estimatedTimeSecs <= 3600:
            minutes = int(self.estimatedTimeSecs / 60)
            seconds = self.estimatedTimeSecs - (minutes * 60)
            estimateLabel = "{:2.0f} min {:2.0f} sec".format(minutes, seconds)
        # Hours, minutes and seconds
        elif self.estimatedTimeSecs > 3600 and self.estimatedTimeSecs < (3600 * 24):
            hours = int(self.estimatedTimeSecs / 3600)
            minutes = int((self.estimatedTimeSecs - hours * 3600) / 60)
            seconds = (self.estimatedTimeSecs - (hours * 3600 + minutes * 60))
            estimateLabel = "{:2.0f} h {:2.0f} mins {:2.0f} secs".format(hours, minutes, seconds)
        # Largest useful time estimates in days, hours, minutes and seconds
        elif self.estimatedTimeSecs > (3600*24):
            days = int(self.estimatedTimeSecs / (3600 * 24))
            hours = int((self.estimatedTimeSecs - (days * (3600 * 24))) / 3600)
            minutes = int((self.estimatedTimeSecs - (days * (3600 * 24) + (hours * 3600))) / 60)
            seconds = self.estimatedTimeSecs - (days * (3600 * 24) + (hours * 3600) + (minutes * 60))
            estimateLabel = "{:2.0f} d {:2.0f} h {:2.0f} mins {:2.0f} secs".format(days, hours, minutes, seconds)

        return estimateLabel
        
    def _do_update_progress(self):
        raise Exception("ProgressTracker _update_progress function must be implemented in child class.")


class ProgressTrackerGUI(ProgressTracker):
    def __init__(self, minVal = 0, maxVal = 100, description = "Progress", numDecimals = 1, progressBarLen = 80):
        self.numDecimals    = numDecimals
        self.progressBarLen = progressBarLen

        super().__init__(minVal, maxVal, description)
    
    def __del__(self):
        del self.progressBar

    def _init_bar(self):
        if hasattr(self, 'progressBar') and self.progressBar is not None:
            del self.progressBar

        self.progressPrefix = Label("")
        self.progressSuffix = Label("")
        layout = {"width": "{0}px".format(self.progressBarLen)}
        self.progressBar = FloatProgress(min = self.minVal, max = self.maxVal, description = self.description)
        self.labeledBar = HBox([self.progressPrefix, self.progressBar, self.progressSuffix])
        self.progressBarVisible = False

    def _do_update_progress(self):
        if self.progressBar is not None:
            # Prefix label shows % completed and ETA
            suffix = ""
            if self.value > self.minVal:
                progress = (self.value - self.minVal) / float(self.maxVal - self.minVal)
                percent = ("{0:." + str(self.numDecimals) + "f}%").format(100 * progress)
                suffix = percent

            # Suffix label shows ETA
            estTimeLabel = self.get_time_estimate()
            if estTimeLabel != "":
                suffix = suffix + " | " + estTimeLabel
                
            self.progressSuffix.value = suffix

            # Update the progress bar itself
            self.progressBar.value = self.value
            
            # Delay showing progress bar until we've started processing something
            if self.value > self.minVal and not self.progressBarVisible:
                display(self.labeledBar)
                self.progressBarVisible = True

class ProgressTrackerCLI(ProgressTracker):
    def __init__(self, minVal = 0, maxVal = 100, description = "Progress", numDecimals = 1, progressBarLen = 80):
        self.numDecimals    = numDecimals
        self.progressBarLen = progressBarLen
        
        super().__init__(minVal, maxVal, description)

    def _init_bar(self):
        self._update_progress()
    
    # Inspired by: https://stackoverflow.com/questions/3173320/text-progress-bar-in-terminal-with-block-characters
    def _do_update_progress(self):
        # Delay showing progress bar until we've started processing something
        if self.value > self.minVal:
            progress = (self.value - self.minVal) / float(self.maxVal - self.minVal)
            percent = ("{0:." + str(self.numDecimals) + "f}").format(100 * progress)
            
            fillLen = math.ceil(self.progressBarLen * progress)
            progressBar = fillLen * '█' + '-' * (self.progressBarLen - fillLen)

            estTimeLabel = self.get_time_estimate()
            print(f"\r{self.description}: |{progressBar}| {percent}% | {estTimeLabel}", end = "\r")
            # Show completion with newline if close enough to done.
            if self.value > (self.maxVal - sys.float_info.epsilon):
                print() 