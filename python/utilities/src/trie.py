from queue              import Queue
from typing             import Iterable, List, Optional

class TrieNode:
    def __init__(self):
        self.children   = {}
        self.isLeaf     = False
        self.str        = ""

class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, inStr: str):
        node = self.root
        for char in inStr:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]

        node.str    = inStr
        node.isLeaf = False

    def insertMany(self, inStrs: Iterable[str], isSorted: bool = False):
        sortedStrs = inStrs
        if not isSorted:
            sortedStrs = sorted(inStrs)

        stack = [self.root]
        prev = ""

        for aStr in sortedStrs:
            # Common prefix
            i = 0
            while i < len(aStr) and i < len(prev) and aStr[i] == prev[i]:
                i += 1

            # Trim to prefix
            stack = stack[:i+1]
            node = stack[-1]

            for char in aStr[i:]:
                newNode = TrieNode()
                node.children[char] = newNode
                stack.append(newNode)
                node = newNode

            node.str = aStr
            node.isLeaf = True
            prev = aStr

    def search(self, inStr: str) -> bool:
        node = self.root
        for char in inStr:
            if char not in node.children:
                return False
            node = node.children[char]

        return node.isLeaf
    
    def findPrefixNode(self, prefix: str) -> Optional[TrieNode]:
        node = self.root
        for char in prefix:
            if char not in node.children:
                return None
            node = node.children[char]
            
        return node
    
    def isPrefix(self, prefix: str) -> bool:
        return self.findPrefixNode(prefix) is not None
    
    def findMatches(self, prefix: str) -> List[str]:
        matches = []

        node = self.findPrefixNode(prefix)
        if node is not None:
            queue = Queue[TrieNode]()
            queue.put(node)

            while not queue.empty():
                curr = queue.get()

                if not curr.isLeaf:
                    for _,child in curr.children.items():
                        queue.put(child)
                else:
                    matches.append(curr.str)
            
        return matches