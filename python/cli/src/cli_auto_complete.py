import argparse
import readline

from typing         import Optional, List, Sequence

# Local packages
from utilities      import trie


class CLIAutoCompleteResults:
    def __init__(self):
        self.searchText: Optional[str]   = None  # Full text input by user
        self.lsMatches: List[str]        = []    # Next set of matches given above

    def doUpdate(self, searchText: str) -> bool:
        ret = self.searchText is None or searchText != self.searchText
        self.searchText = searchText
        return ret
    
    @staticmethod
    def __getPosArguments(searchText: str, cmdParser: argparse.ArgumentParser) -> List[str]:
        ret = []

        # See comment above on accessing private members ...
        #for action in cmdParser._action_groups:
        for action in cmdParser._positionals._actions:
            if action.option_strings == []:
                # '<' and '>' to instruct user to specify a value and not just the argument name.
                ret.append("<" + action.dest + ">")

        return ret
    
    @staticmethod
    def __getOptions(searchText: str, cmdParser: argparse.ArgumentParser, currOptions: List[str]) -> List[str]:
        ret = []

        fullNames = set[str]()
        # See comment above on accessing private members ...
        for key,action in cmdParser._option_string_actions.items():
            # Avoid duplicates like "-h" and "--help" which both signify "help" optional
            # Also don't include options already specified by user
            if (action.dest not in fullNames 
                and key not in currOptions
                and key.startswith(searchText)):
                ret.append(key)
                fullNames.add(action.dest)

        return ret
    
    def buildOptionsMatches(self, searchText:str, cmdParser: argparse.ArgumentParser, lsTokens: List[str]):

        # Any other complete tokens that follow command are options or arguments
        currOptions: List[str] = []

        for token in lsTokens:
            if token.startswith("-"):
                currOptions.append(token)

        # Add optional first
        self.lsMatches = self.__getOptions(searchText, cmdParser, currOptions)
    
        # Always add position arguments 2nd if user isn't searching for options
        if not searchText.startswith("-"):
            self.lsMatches.extend(self.__getPosArguments(searchText, cmdParser))

class CLIAutoComplete:
    def __init__(self, parser: argparse._SubParsersAction):
        self.argParser = parser

        # Create lookup for commands. 
        self.commands = self.__getCommands()
        self.cmdLookup = trie.Trie()
        self.cmdLookup.insertMany(inStrs=self.commands)

        # Create lookup for options and positional arguments for each command
        self.__result = CLIAutoCompleteResults()

    @property
    def results(self) -> CLIAutoCompleteResults:
        return self.__result
    
    def __getCommands(self) -> List[str]:
        ret = []

        # Accessing a private member of arg parser's sub parser but there doesn't 
        # seem to be a clean way around this.
        for choice in self.argParser._choices_actions:
            ret.append(choice.dest)

        return ret
    
    def __buildMatches(self, searchText: str):
        
        buffer      = readline.get_line_buffer()

        # Avoid unnecessary recalculation in between calls to completer when text hasn't changed
        if self.__result.doUpdate(buffer):
            startIndex  = readline.get_begidx()
            endIndex    = readline.get_endidx()

            # What part of the command is being completed
            beforeCursor = buffer[:startIndex]
            lsTokens = beforeCursor.split()

            # Completing command?
            if len(lsTokens) == 0:
                self.__result.lsMatches = self.cmdLookup.findMatches(searchText)
            # Completing options or positional arguments?
            else:
                # Assume command is the 1st token
                command = lsTokens[0]
                
                # Any other tokens are assumed to represent options or arguments the user has specified. Pass
                # them in so they get filtered from auto complete.
                self.__result.buildOptionsMatches(searchText, 
                                                self.argParser.choices[command], 
                                                lsTokens[1:])

    # Iterate over matches
    def __call__(self, searchText: str, state: int) -> Optional[str]:

        self.__buildMatches(searchText)

        numMatches = len(self.__result.lsMatches)
        # Only 1 match so append everything tha follows the prefix (searchText)
        if state == 0 and numMatches == 1:
            match = self.__result.lsMatches[state]
            readline.insert_text(match[len(searchText):] + " ")
            readline.redisplay()
            return None
        # Multiple matches
        elif state < len(self.__result.lsMatches):
            return self.__result.lsMatches[state]
        # No more matches
        else:
            return None
        
class CLIAutoCompleteDisplayHook:
    def __init__(self, completer: CLIAutoComplete):
        self.__completer = completer

    # readline (in c code) automatically sorts the list. This can be confusing and
    # will not match the order of function handlers for various commands. This
    # hook overrides the logic that prints the completion results and uses the cached
    # list of matches from auto complete.
    def __call__(self, substitution: str, matches: Sequence[str], longest_match_len: int):
        results = self.__completer.results

        print()
        print('  '.join(results.lsMatches)) 
        print(readline.get_line_buffer(), end='', flush=True)