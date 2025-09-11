from abc            import ABC, abstractmethod
from collections    import OrderedDict
from dataclasses    import dataclass
from enum           import Enum
from threading      import Lock
from typing         import Dict, Generic, Iterator, Optional, Set, TypeVar

# Defines
K = TypeVar('K')
V = TypeVar('V')

UnboundedCacheSize:int = -1

# Support some basic policies
class CacheReplacementPolicy(Enum):
    LRU = "LRU" # Least recently used
    LFU = "LFU" # Least frequently used

class CacheDict(ABC, Generic[K, V]):
    def __init__(self, maxBound: int = UnboundedCacheSize):
        self.maxBound = maxBound

    @abstractmethod
    def get(self, key: K) -> Optional[V]:
        pass

    @abstractmethod
    def put(self, key: K, value: V):
        pass

    @abstractmethod
    def prune(self) -> Optional[tuple[K, V]]:
        pass

    @abstractmethod
    def _keys(self) -> Iterator[K]:
        pass

    @abstractmethod
    def __len__(self) -> int:
        pass

    def __iter__(self) -> Iterator[K]:
        return iter(self._keys())

# Least recently used dictionary 
class LRUDict(CacheDict[K, V]):
    def __init__(self, maxBound: int = UnboundedCacheSize):
        super().__init__(maxBound)
        self.dict: OrderedDict[K, V] = OrderedDict()

    def get(self, key: K) -> Optional[V]:
        ret: Optional[V] = None
        if key in self.dict:
            ret = self.dict[key]
            # Move to the end as it was most recently accessed
            self.dict.move_to_end(key, last = True)
        return ret

    def put(self, key: K, value: V):
        if key in self.dict:
            raise ValueError(f"An item already exists in cache with key {key}")
        else:
            self.dict[key] = value

    def prune(self) -> Optional[tuple[K, V]]:
        ret: Optional[tuple[K,V]] = None
        if self.maxBound != UnboundedCacheSize and len(self.dict) > self.maxBound:
            if len(self.dict) > 0:
                ret = self.dict.popitem(last = False) # Pop front item as it's least recently used
            else:
                raise IndexError("Trying to prune an empty cache.")
        
        return ret
    
    def _keys(self) -> Iterator[K]:
        return iter(self.dict.keys())

    def __len__(self) -> int:
        return len(self.dict)


# Least frequently used dictionary
class LFUDict(CacheDict[K, V]):
    def __init__(self, maxBound: int = UnboundedCacheSize):
        super().__init__(maxBound)
        self.lookup:    Dict[K, tuple[V, int] ] = {}
        self.frequency: Dict[int, Set[K] ]      = {}

        self.maxFrequency:int = 0
        self.minFrequency:int = 0

    def get(self, key: K) -> Optional[V]:
        ret: Optional[V] = None
        if key in self.lookup:
            valueFreq = self.lookup[key]
            # Increase frequency
            self._incrFreq(key, valueFreq)
            # Return value
            return valueFreq[0]
        return ret

    def put(self, key: K, value: V):
        if key in self.lookup:
            raise ValueError(f"An item already exists in cache with key {key}")
        else:
            # Add to lookup
            valueFreq:tuple[V, int] = (value, 1)
            self.lookup[key] = valueFreq
            self._addToFreq(key, 1)

    def prune(self) -> Optional[tuple[K, V]]:
        ret: Optional[tuple[K, V]] = None

        # If defined as bounded cache
        if self.maxBound != UnboundedCacheSize and len(self.lookup) > self.maxBound and len(self.lookup) > 0:
            # Get an item from lowest frequency bin
            minSet: Set[K] = self.frequency[self.minFrequency]
            key = minSet.pop()
            # Bin is empty. Is there a higher frequency bin to remove from next time?
            if len(minSet) == 0 and self.minFrequency < self.maxFrequency:
                self.minFrequency = self.minFrequency + 1
            if key in self.lookup:
                valueFreq = self.lookup[key]
                del self.lookup[key]
                ret = (key, valueFreq[0])
            else:
                raise IndexError(f"Couldn't find key {key} in lookup while pruning.")
        else:
            raise IndexError("Trying to prune an empty cache.")
        
        return ret
        
    def _addToFreq(self, key: K, freq: int):
        # Add to frequency
        if not freq in self.frequency:
            self.frequency[freq] = set()
        # Add entry
        self.frequency[freq].add(key)
        # Higher frequency bin exists now?
        if freq > self.maxFrequency:
            self.maxFrequency = freq

    def _incrFreq(self, key: K, valueFreq: tuple[V, int]):
        # If item can be looked up it should in the frequency dictionary also
        oldFreq = valueFreq[1]
        if oldFreq not in self.frequency:
            raise ValueError(f"Could not find key {key} in frequency lookup.")
        else:
            # Remove key from old frequency set
            oldSet = self.frequency[oldFreq]
            oldSet.remove(key)
            self._addToFreq(key, oldFreq + 1)
            # Update lowest frequency bin if lowest is now empty
            if len(oldSet) == 0 and self.minFrequency == oldFreq:
                self.minFrequency = self.minFrequency + 1

    def _keys(self) -> Iterator[K]:
        return iter(self.lookup.keys())

    def __len__(self) -> int:
        return len(self.lookup)

@dataclass
class CacheStats:
    cacheHit:   int
    cacheMiss:  int
    evictions:  int

# Help user define custom logic to fetch item automatically
# if not found in cache
class CacheFetchItemHandler(ABC, Generic[K,V]):
    @abstractmethod
    def __call__(self, key: K) -> Optional[V]:
        pass

# Help user define custom logic to persist item or do some
# other work if item gets evicted from cache.
class CacheEvictItemHandler(ABC, Generic[K,V]):
    @abstractmethod
    def __call__(self, key: K, value: V):
        pass

class Cache(Generic[K, V]):
    def __init__(self, maxBound: int = UnboundedCacheSize, policy: CacheReplacementPolicy = CacheReplacementPolicy.LRU):
        
        self.policy  = policy
        self.dict: Optional[CacheDict[K,V]] = None
        self.stats = CacheStats(0, 0, 0)
        self.fetchHandler: Optional[CacheFetchItemHandler] = None
        self.evictHandler: Optional[CacheEvictItemHandler] = None
        
        # TODO: add an unbounded cache option
        if self.policy == CacheReplacementPolicy.LRU:
            self.dict = LRUDict[K,V](maxBound)
        elif self.policy == CacheReplacementPolicy.LFU:
            self.dict = LFUDict[K,V](maxBound)
        else:
            raise ValueError(f"Unsupported cache replacement policy {self.policy}")
        
        self._lock   = Lock()

    def get(self, key: K, default: Optional[V] = None) -> Optional[V]:
        ret: Optional[V] = None
        if self.dict is not None:
            with self._lock:
                ret = self.dict.get(key)

            # If we handle bringing items in cache automatically.
            # While there is a race condition it's not too risky
            # and this minimizes locking on I/O or other slow ops.
            if ret is None and self.fetchHandler is not None:
                ret = self.fetchHandler(key)
                if ret is not None:
                    self.put(key, ret)
                
                with self._lock:
                    if ret is not None:
                        self.stats.cacheMiss = self.stats.cacheMiss + 1
            else:
                with self._lock:
                    if ret is not None:
                        self.stats.cacheHit = self.stats.cacheHit + 1
        else:
            raise IndexError("Cache dictionary not initialized.")

        if ret is None:
            ret = default

        return ret

    def put(self, key: K, value: V):
        if self.dict is not None:
            self.dict.put(key, value)
            evictedKV = self.dict.prune()
            if evictedKV is not None and self.evictHandler is not None:
                self.evictHandler(evictedKV[0], evictedKV[1])

        else:
            raise IndexError("Cache dictionary not initialized.")

    def setFetchHandler(self, handler: CacheFetchItemHandler):
        self.fetchHandler = handler

    def setEvictHandler(self, handler: CacheEvictItemHandler):
        self.evictHandler = handler

    # Acquire access to underlying collection of cached items
    # User must release after he/she is done with them.
    def acquireDict(self) -> Optional[CacheDict[K, V]]:
        self._lock.acquire()
        return self.dict
    
    def releaseDict(self):
        self._lock.release()



