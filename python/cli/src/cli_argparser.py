import argparse

# Based on limited research there doesn't seem to be a way to cleanly intercept errors
# in argparser to customize handling. For example, when should the program print an
# error like "wrong command" vs exiting because arguments are clearly bogus/mallformed.
class CLIAppArgParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setBuiltInErrorHandling(False)
    
    def error(self, message):
        # Retain error handling for application arguments but ...
        if self.builtInErrorHandling:
            super().error(message)
        # ... handle subparser and other errors explicitly rather than always exiting.
        else:
            raise CLIAppArgumentError(f"CLIAppArgParser unable to parse: {message}")

    def exit(self, status=0, message=None):
        
        # Print the message (usually usage/help), but do not exit
        if self.builtInErrorHandling:
            super().exit(status, message)  
        # ... handle subparser and other errors explicitly rather than always exiting.
        elif status != 0 or message is not None:
            raise CLIAppParserExit(f"CLIAppArgParser tried to exit with status: {status} and message: {message}")
        else:
            raise CLIAppParserExitNoError("CLIAppArgParser exited but with no errors likely due to help/usage.")


    def parse_args(self, args = None, namespace = None):
        parseResult = None

        try:
            parseResult = super().parse_args(args, namespace)
        except CLIAppParserExitNoError as e:
            parseResult = None
        except SystemExit as e:
            self.print_usage()

        return parseResult
        
    def setBuiltInErrorHandling(self, enabled):
        self.builtInErrorHandling = enabled
        self.exit_on_error = enabled


class CLIAppArgumentError(Exception):
    pass

class CLIAppParserExit(Exception):
    pass

class CLIAppParserExitNoError(Exception):
    pass