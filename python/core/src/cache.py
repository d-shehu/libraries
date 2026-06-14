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

    # Use this when iterating over items without
    # affecting the caching.
    @abstractmethod
    def items(self) -> Iterator[tuple[K,V]]:
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
    
    def items(self) -> Iterator[tuple[K,V]]:
        for key,entry in self.dict.items():
            yield key, entry

    def __len__(self) -> int:
        return len(self.dict)

@dataclass
class LFUEntry[K,V]:
    key: K
    value: V
    count: int
    prev: Optional["LFUEntry"] = None
    next: Optional["LFUEntry"] = None

@dataclass
class LFUBin[K,V]:
    head: Optional[LFUEntry[K,V]] = None
    tail: Optional[LFUEntry[K,V]] = None

    @property
    def isEmpty(self) -> bool:
        return self.head is None and self.tail is None

# Least frequently used dictionary
class LFUDict(CacheDict[K, V]):
    def __init__(self, maxBound: int = UnboundedCacheSize):
        super().__init__(maxBound)
        self.lookup:    Dict[K, LFUEntry[K,V] ]   = {}
        self.frequency: Dict[int, LFUBin[K,V] ]   = {}

        self.minFrequency:int = 1

    def get(self, key: K) -> Optional[V]:
        ret: Optional[V] = None

        if key in self.lookup:
            entry = self.lookup[key]
            # Increase frequency on access
            self._incr(key, entry)
            ret = entry.value
            
        return ret

    def put(self, key: K, value: V):
        if key in self.lookup:
            raise ValueError(f"An item already exists in cache with key {key}")
        else:
            # Add to lookup
            entry = LFUEntry(key, value, 1)
            self.lookup[key] = entry
            self._addToBin(entry)

    def prune(self) -> Optional[tuple[K, V]]:
        ret: Optional[tuple[K, V]] = None

        # If defined as bounded cache
        if self.maxBound != UnboundedCacheSize and len(self.lookup) > self.maxBound:
            if len(self.lookup) > 0:
                # Get an item from lowest frequency bin
                minSet: LFUBin[K,V] = self.frequency[self.minFrequency]
                entry = self._popFromBin(minSet)
                
                # Remove item from cache
                if entry is not None and entry.key in self.lookup:
                    del self.lookup[entry.key]
                    ret = (entry.key, entry.value)
                else:
                    raise IndexError(f"Couldn't find entry in lookup while pruning.")
            else:
                raise IndexError("Trying to prune an empty cache.")
        
        return ret

    def _incr(self, key: K, entry: LFUEntry):
        # Remove from old bin and add to new higher frequency count
        self._removeFromBin(entry)
        entry.count = entry.count + 1
        self._addToBin(entry)

    def _addToBin(self, entry: LFUEntry[K,V]) -> LFUBin[K,V]:
        # Does the bin exist? If not create it.
        if not entry.count in self.frequency:
            currBin = LFUBin[K,V]()
            self.frequency[entry.count] = currBin
        else:
            currBin = self.frequency[entry.count]

        # Bin is empty and this is the 1st element?
        if currBin.isEmpty:
            currBin.tail = entry
            currBin.head = entry
            entry.next = None
            entry.prev = None
        # Otherwise add to the end of bin
        elif currBin.tail is not None:
            currBin.tail.prev = entry
            entry.next = currBin.tail
            entry.prev = None
            currBin.tail = entry
        else:
            raise Exception("Tail of curr frequency bin is null.")

        # New lower freq bin should be the min
        if entry.count < self.minFrequency:
            self.minFrequency = entry.count

        return currBin

    def _popFromBin(self, currBin: LFUBin[K, V]) -> Optional[LFUEntry[K, V]]:
        evictedEntry: Optional[LFUEntry] = None

        if currBin.tail is not None:
            evictedEntry = currBin.tail
            self._removeFromBin(currBin.tail)
        else:
            raise IndexError("Couldn't remove entry from bin as it's empty")

        return evictedEntry
    
    def _removeFromBin(self, entry: LFUEntry[K, V]) -> LFUBin[K, V]:
        if not entry.count in self.frequency:
            raise IndexError(f"Couldn't find entry with value {entry.value} in frequency bin.")
        else:
            currBin = self.frequency[entry.count]

            # Preserve the links 
            if entry.prev is not None:
                entry.prev.next = entry.next
            if entry.next is not None:
                entry.next.prev = entry.prev
            
            # Update the head and tail
            if currBin.tail == entry:
                if entry.next is None or entry.next.count == entry.count:
                    currBin.tail = entry.next
            if currBin.head == entry:
                if entry.prev is None or entry.prev.count == entry.count:
                    currBin.head = entry.prev

        if currBin.isEmpty and self.minFrequency == entry.count:
            self.minFrequency = self.minFrequency + 1

        return currBin
        
    def _keys(self) -> Iterator[K]:
        return iter(self.lookup.keys())
    
    def items(self) -> Iterator[tuple[K,V]]:
        for key,entry in self.lookup.items():
            yield key, entry.value

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



