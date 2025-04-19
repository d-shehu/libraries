# A simple moving average
# While there is a version in Numpy this avoids adding a dependence on pandas to this package
# which is otherwise not needed at this time.

class MovingAverage:
    def __init__(self, history: int):
        if history <= 0:
            raise Exception("History must be greater than 0")
        else:
            self.reset(history)

    def reset(self, history):
        self.history = history
        self.elems   = []
        self.pos     = -1
        self.cum     = 0

    def push_list(self, lstVal):
        for val in listVal:
            self.push(val)
        
    def push(self, newVal):
        self.pos = (self.pos + 1) % self.history
        if len(self.elems) == self.history:
            oldestVal = self.elems[self.pos]
            self.elems[self.pos] = newVal
            self.cum -= oldestVal
        else:
            self.elems.append(newVal)
        
        self.cum += newVal

    def average(self):
        if len(self.elems) > 0:
            return self.cum / len(self.elems)
        else:
            raise Exception("History is empty")
        