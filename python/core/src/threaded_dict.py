from collections    import UserDict
from threading      import Lock
from typing         import Generic, TypeVar

K = TypeVar('K')
V = TypeVar('V')

class ThreadedDict(UserDict, Generic[K, V]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock = Lock()

    def __getitem__(self, key: K) -> V:
        with self._lock:
            return super().__getitem__(key)
        
    def __setitem__(self, key: K, item: V) -> None:
        with self._lock:
            super().__setitem__(key, item)