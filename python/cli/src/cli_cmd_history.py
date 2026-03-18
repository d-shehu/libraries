import readline

from logging            import Logger
from pathlib            import Path

from threading          import Lock
from typing             import Deque

# Local packages
from utilities          import background_task

class CLICmdHistory(background_task.BackgroundTask):
    DEFAULT_HISTORY             = 1000  # Derive from bash
    ESTIMATED_MAX_CMD_LEN       = 256   # Rough approximation of max len of command in bytes
    DEF_AUTOSAVE_INTERVAL_SECS  = 30    # Save every 30 seconds unless user overrides

    # For extra safety flush after each command
    # Interval can be increased if program ends
    # up issuing lots of commands. But unlikely 
    # in interactive mode
    def __init__(self, cmdHistoryFilepath: Path, logger: Logger, maxEntries: int = DEFAULT_HISTORY, flushIntervalSecs: int = DEF_AUTOSAVE_INTERVAL_SECS):
        self.cmdHistoryFilepath     = cmdHistoryFilepath
        self.logger                 = logger
        self.maxEntries             = maxEntries
        self.flushIntervalSecs      = flushIntervalSecs

        self.commands               = Deque[str]()
        self.commandsUpdated        = False 

        # Autosave and other maint. periodically in case service dies
        self.__lock                 = Lock()
        self.__autosaveRunner       = background_task.BackgroundRunner(self, CLICmdHistory.DEF_AUTOSAVE_INTERVAL_SECS)

        # Instruct readline to preserve up maxEntries commands
        readline.set_history_length(self.maxEntries)

    def __del__(self):
        self.unload()

    def load(self) -> bool:
        success = False

        # Make sure parent exists. History file may not yet exist if this is the 1st run.
        if not self.cmdHistoryFilepath.parent.exists():
            self.logger.error(f"Path to cmd history parent dir not found: {self.cmdHistoryFilepath}")

        # If there is a history file read it.
        elif self.cmdHistoryFilepath.exists():
            try:
                with self.__lock:
                    # Support special characters
                    with open(self.cmdHistoryFilepath, encoding="utf-8") as f:
                        lines = [line.rstrip("\n") for line in f]

                        # Store up to max entries which may be different from previous runs of the
                        # program if the user changed maxEntries.
                        for line in lines[:self.maxEntries -1]:
                            cmd = line.strip()
                            self.__tryAdd(cmd)
                            readline.add_history(cmd)

                        # If not exception assume all commands written to file
                        success = True
            except Exception as e:
                self.logger.exception(f"Unable to read commands ")
        else:
            success = True # No history file exists yet. 

        # Only start auto-save if directory exists. Auto save is optional.
        if self.cmdHistoryFilepath.parent.exists() and self.__autosaveRunner is not None:
            if not self.__autosaveRunner.start():
                self.logger.error("Unable to start autosave background runner for cmd history.")
            
        return success
    
    def unload(self) -> bool:
       return self.__autosaveRunner.stop()
    
    def __tryAdd(self, cmd: str) -> bool:
        success = False

        # Safely append command to history. Trim to maximum allowed history.
        doAdd = len(self.commands) == 0 or self.commands[-1] != cmd
        if doAdd:
            try:
                self.commands.append(cmd)
                if len(self.commands) > self.maxEntries:
                    self.commands.popleft()

                success = True # No error
            except Exception as e:
                self.logger.exception("Unable to add command to history.")

        return success

    def add(self, line: str) -> bool:
        # Readline automatically manages it's own history        
        with self.__lock:
            self.commandsUpdated = self.__tryAdd(line.strip())
            return self.commandsUpdated
    
    def doTask(self):
        # A relatively simple synchronization approach where the assumption is 
        # the user is only running a small number of commands infrequently.
        # While it's a bit inefficient to re-write all the commands if just one has
        # changed, this should happen relatively infrequently that it's not worth
        # using a more complex data structure or buffered I/O and only writing out
        with self.__lock:
            # the one or 2 commands that have changed.
            if self.commandsUpdated:
                with open(self.cmdHistoryFilepath, mode="w", encoding="utf-8") as f:
                    for cmd in self.commands:
                        f.write(cmd + "\n")

                    # Assume if no exception write succeeded.
                    self.commandsUpdated = False
                    

    def onTaskException(self):
        self.logger.exception("Unable to persist commands to history file.")
