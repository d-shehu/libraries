import logging
import os.path
import sys
import uuid

# A thin wrapper that simplifies logging further to the most common use cases.

# Log levels bits corresponding to severity and levels used by Python.
# Bits can be combined to write to multiple log files.
DEBUG              = 0x01  # Dev only and diagnostics
INFO               = 0x02  # Possibly relevant to users
WARNING            = 0x04  # Anomalous behavior that probably should be reported to user
ERROR              = 0x08  # Errors but not a show stopper
CRITICAL           = 0x10  # Critical errors likely leading to failed execution

# Unless specified logs are written to current directory
ALL_LEVELS         = DEBUG | INFO | WARNING | ERROR | CRITICAL
DEF_LOG_DIR        = "."
DEF_LOG_FILENAME   = "all.log"

INDEX_UNDEFINED    = -1
NOT_FIXED_WIDTH    = -1

#TODO JSON formatted logger

# See fields: https://docs.python.org/3/library/logging.html#formatter-objects
LOG_FIELDS_LIST_DEFAULT   = [ "levelname", "asctime", "msg" ]
LOG_FIELDS_DEBUG_DETAILED = [ "levelname", "asctime", "module", "lineno", "msg" ]
LOG_DATE_FORMAT           = "%Y-%m-%d %H:%M:%S"

# Module functions
def ConvertLevelToStr(strStartingLevel):
    level = logging.NOTSET
    
    match strStartingLevel:
        case "DEBUG":
            level = logging.DEBUG
        case "INFO":
            level = logging.INFO
        case "WARNING":
            level = logging.WARNING
        case "ERROR":
            level = logging.ERROR
        case "CRITICAL":
            level = logging.CRITICAL
        case _:
            raise Exception(f"Unknown starting level {strStartingLevel}")

    return level

class LogFormatterTxt(logging.Formatter):
    def __init__(self, 
                 lsFields   = LOG_FIELDS_LIST_DEFAULT,
                 delimiter  = "|",
                 dateFormat = LOG_DATE_FORMAT,
                 fieldWidth = 8):
        # Create format
        logFormat = ""
        if len(lsFields) > 0:
            field = lsFields[0]
            logFormat = LogFormatterTxt.getFieldFormat(field, fieldWidth)
            
            for i in range(1, len(lsFields)):
                field = lsFields[i]
                logFormat = logFormat + " " + delimiter + " " + LogFormatterTxt.getFieldFormat(field, fieldWidth)
                
        # Piggyback on parent class
        super().__init__(fmt = logFormat, datefmt = dateFormat, style = "%")
        
    def getFieldFormat(field, fieldWidth):
        formattedField = ""
        if fieldWidth == NOT_FIXED_WIDTH:
            formattedField = f"%({field})s"
        else:
            formattedField = f"%({field})-{fieldWidth}s"

        return formattedField

class LogFilter(logging.Filter):
    def __init__(self, logLevels):
        self.logLevels = logLevels
        super().__init__()
        
    def filter(self, record: logging.LogRecord) -> bool:
        match = False
        
        level = record.levelno
        if level == logging.DEBUG:
            match = ((self.logLevels & DEBUG) != 0)
        elif level == logging.INFO:
            match = ((self.logLevels & INFO) != 0)
        elif level == logging.WARNING:
            match = ((self.logLevels & WARNING) != 0)
        elif level == logging.ERROR:
            match = ((self.logLevels & ERROR) != 0)
        elif level == logging.CRITICAL:
            match = ((self.logLevels & CRITICAL) != 0)
        else:
            raise Exception(f"Uknown log level {level}.")

        return match
            
        
class Logger:
    def __init__(self, 
                 logLevels, 
                 formatter 
                ):
        super().__init__()
        
        self.id         = uuid.uuid4()
        self.logLevels  = logLevels
        self.formatter  = formatter
        self.logHandler = None

    def _get_handler(self):
        # Defer creation until it's needed
        if self.logHandler is None:
            self.logHandler = self._create()
            self.logHandler.setFormatter(self.formatter)
            # Allow all messages by default. Use custom filter to select messages.
            self.logHandler.setLevel(logging.DEBUG) 
            self.logHandler.addFilter(LogFilter(self.logLevels))
            
        return self.logHandler

    # Override this in child class
    def _create(self):
        raise Exception("LogHandler child class must override _create.")

    def get_id(self):
        return self.id
        
    def install(self, sysLogger):
        sysLogger.addHandler(self._get_handler())

    def uninstall(self, sysLogger):
        sysLogger.removeHandler(self._get_handler())

    def flush(self):
        self._get_handler().flush()
        
    
class LogFile(Logger):
    def __init__(self,
                 logLevels     = ALL_LEVELS, 
                 directory     = DEF_LOG_DIR, 
                 filename      = DEF_LOG_FILENAME, 
                 formatter     = LogFormatterTxt(), 
                ):
        super().__init__(logLevels, formatter)
        self.directory     = directory
        self.filename      = filename

    def _create(self):
        filepath = os.path.join(self.directory, self.filename)
        return logging.FileHandler(filepath)
        

class LogConsole(Logger):
    def __init__(self,
                 logLevels     = ALL_LEVELS, 
                 formatter     = LogFormatterTxt(),
                 stdError      = False
                ):
        super().__init__(logLevels, formatter)
        self.stdError = stdError
        
    def _create(self):
        sysStream = sys.stderr if self.stdError else sys.stdout
        return logging.StreamHandler(sysStream)

class LogMgr:
    def __init__(self, name, lsDefLoggers = [LogFile()]):
        self.name        = name
        self.sysLogger   = logging.getLogger(name)
        self.loggers     = {}

        self.sysLogger.setLevel(logging.DEBUG) # Show all messages
        self.sysLogger.handlers.clear()
        for logger in lsDefLoggers:
            self.addLogger(logger)     

    def addLogger(self, logger):
        # TODO: may want to check for duplicate or handlers that override each other.
        if logger is not None:
            self.loggers[logger.get_id()] = logger
            logger.install(self.sysLogger)

    def removeHandlerByID(self, loggerID):
        success = False
        if loggerID in self.loggers:
            self.loggers[loggerID].uninstall(self.sysLogger)
            self.loggers.pop(loggerID)
            success = True

        return success
 
    def suppressLogger(self, strStartingLevel):
        level = ConvertLevelToStr(strStartingLevel)
        logging.disable(level)

    def unsuppressLogger(self):
        logging.disable(logging.NOTSET)

    def getSysLogger(self):
        return self.sysLogger

    def flush(self):
        for logger in self.loggers.values():
            logger.flush()

# Format line like print does
class LogLine:
    def __init__(self, *args, sep = ' ', end = ''):
        self.logLine = ""
        
        # Convert each argument to string and concat
        numArgs = len(args)
        if numArgs > 0:
            self.logLine = str(args[0])
            for i in range(1, numArgs):
                self.logLine = self.logLine + sep + str(args[i])

    def __str__(self):
        return self.logLine
        
# Reasonable defaults for user and dev logging
def ConfigureConsoleOnlyLogging(loggerName):
    debugLogFormat    = LogFormatterTxt(LOG_FIELDS_DEBUG_DETAILED,   "|", LOG_DATE_FORMAT)
    standardLogFormat = LogFormatterTxt(LOG_FIELDS_LIST_DEFAULT, "|", LOG_DATE_FORMAT)

    lsLoggers = [
        # On console
        LogConsole(DEBUG,            debugLogFormat,    False),
        LogConsole(INFO | WARNING,   standardLogFormat, False),
        LogConsole(ERROR | CRITICAL, standardLogFormat, True)
    ]

    return LogMgr(loggerName, lsLoggers)
    
def ConfigureDefaultLogging(loggerName, logDir = DEF_LOG_DIR):
    debugLogFormat    = LogFormatterTxt(LOG_FIELDS_DEBUG_DETAILED,   "|", LOG_DATE_FORMAT)
    standardLogFormat = LogFormatterTxt(LOG_FIELDS_LIST_DEFAULT, "|", LOG_DATE_FORMAT)

    lsLoggers = [
        # On console
        LogConsole(DEBUG,            debugLogFormat,    False),
        LogConsole(INFO | WARNING,   standardLogFormat, False),
        LogConsole(ERROR | CRITICAL, standardLogFormat, True),
        # In file
        LogFile(DEBUG,               logDir, "debug.log", debugLogFormat),
        LogFile(INFO | WARNING,      logDir, "user.log",  standardLogFormat),
        LogFile(ERROR | CRITICAL,    logDir, "error.log", standardLogFormat)
    ]

    return LogMgr(loggerName, lsLoggers)
        
        
        


    