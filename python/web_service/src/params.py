from pathlib            import Path

ENV_SERVER_ADDRESS  = "SERVER_ADDRESS"
ENV_SERVER_PORT     = "SERVER_PORT"

ENV_USERS_DIR       = "USERS_DIR"
ENV_PROCESSING_DIR  = "PROCESSING_DIR"
ENV_SERVICE_USER    = "CONSOLE_USER"

DEF_SERVER_ADDRESS  = "0.0.0.0"
DEF_SERVER_PORT     = 8080

DEF_USERS_DIR       = "~/data/users"
DEF_PROCESSING_DIR  = "~/data/processing"
DEF_SERVICE_USER    = "automaton"

# User packages
from core import context

class ServiceParams:
    processingDir:  Path
    usersDir:       Path
    serviceUser:    str

    def __init__(self, serviceName: str):
        self.serviceName    = serviceName
        self.serverAddr     = ""
        self.serverPort     = 0

        self.processingDir  = Path()
        self.usersDir       = Path()
        self.serviceUser    = ""

    def configure(self, pgmContex: context.ProgramContext) -> bool:
        self.serverAddr     = pgmContex.getEnvVariableOfType(ENV_SERVER_ADDRESS, DEF_SERVER_ADDRESS)
        self.serverPort     = pgmContex.getEnvVariableOfType(ENV_SERVER_PORT, DEF_SERVER_PORT)

        self.processingDir  = pgmContex.getDirectory(ENV_PROCESSING_DIR, DEF_PROCESSING_DIR)
        self.usersDir       = pgmContex.getDirectory(ENV_USERS_DIR, DEF_USERS_DIR)

        if not self.processingDir.is_dir() or not self.usersDir.is_dir():
            pgmContex.logger.error("Unable to locate 'processing' or 'users' directory.")
            
        self.serviceUser    = pgmContex.getEnvVariableStr(ENV_SERVICE_USER, DEF_SERVICE_USER)
        if self.serviceUser == "":
            pgmContex.logger.error("Unable to get service user.")

        return self.isValid
    
    @property
    def isValid(self) -> bool:
        return (self.serviceName != ""
                and self.serverAddr != ""
                and self.serverPort != 0
                and self.processingDir.is_dir() 
                and self.usersDir.is_dir()
                and self.serviceUser != "")
