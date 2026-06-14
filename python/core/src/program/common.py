from typing import Optional, TypeVar, cast, Callable

import os

T = TypeVar("T", int, float, str, bool)

class TypeConverter[T]:
    @staticmethod
    def convert(valStr: Optional[str], defVal: T) -> T:
        retVal = defVal
        if valStr is not None:
            ctor = cast(Callable[[str], T], type(defVal))
            retVal = ctor(valStr)
        
        return retVal

# Utility function that replaces env vars and convert to absolute path
def GetFullPath(path):
    return os.path.abspath(os.path.expandvars(path))
    