import time

from abc            import ABC, abstractmethod
from threading      import Event, Lock, Thread
from typing         import Generic, Optional, TypeVar

class BackgroundTask(ABC):
    # Override this method to do some work in subclass.
    @abstractmethod
    def doTask(self):
        pass

    # Override this method to handle unexpected exceptions.
    @abstractmethod
    def onTaskException(self, exception: Exception):
        pass

T = TypeVar('T', bound=BackgroundTask)

# A simple class for running background tasks on an interval. 
# By default it runs as a daemon so calling code must
# stop it explicitly.
class BackgroundRunner(Generic[T]):
    DEFAULT_RUN_INTERVAL = 60

    def __init__(self, 
                 task: T,
                 runIntervalSecs: int   = DEFAULT_RUN_INTERVAL,
                 runTaskOnStop: bool    = True,
                 threadName: str        = "",
                 runAsDaemon: bool      = True):                        
        
        # Thread created and started in start function
        self.__task             = task
        self.__runIntervalSecs  = runIntervalSecs
        self.__runTaskOnStop    = runTaskOnStop
        self.__threadName       = threadName
        self.__runAsDaemon      = runAsDaemon

        if self.__threadName == "":
            taskCls = type(task)
            self.__threadName = f"{taskCls.__qualname__}_Thread"

        self.__thread: Optional[Thread] = None
        self.__lock         = Lock()
        self.__stopEvent    = Event()

    def __del__(self):
        self.stop()

    def __isRunning(self) -> bool:
        return self.__thread is not None
    
    def isRunning(self) -> bool:
        with self.__lock:
            return self.__isRunning()

    def start(self) -> bool:
        success = False

        with self.__lock:
            if not self.__isRunning():
                self.__thread = Thread(name = self.__threadName, target = self.__doRun, daemon = self.__runAsDaemon) 
                if self.__thread is not None:
                    self.__stopEvent.clear()
                    self.__thread.start()
                    success = True
        
        return success
        
    def stop(self, timeout: float | None = None) -> bool:
        success = False

        with self.__lock:
            if self.__isRunning():
                self.__stopEvent.set()
                if self.__thread is not None:
                    self.__thread.join(timeout)
                    success = not self.__thread.is_alive()
                    del self.__thread
                    self.__thread = None

                # Run one last time in case stopped between cycles
                if self.__runTaskOnStop:
                    self.__task.doTask()

        return success
                
    def __doRun(self):
        while not self.__stopEvent.is_set():
            startTime = time.time()
            try:
                self.__task.doTask()
            except Exception as e:
                self.__task.onTaskException(e)
            remainingTime = time.time() - startTime

            # TODO: instrumentation in case task is running especially slow 
            # causing cycles to be missed. Timing not guaranteed obviously.
            if remainingTime < self.__runIntervalSecs:
                self.__stopEvent.wait(self.__runIntervalSecs - remainingTime)

    


 