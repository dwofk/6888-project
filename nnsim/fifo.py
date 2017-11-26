from nnsim.module import Module, HWError
from nnsim.reg import Reg

class FIFOError(HWError):
    pass

class FIFO(Module):
    def instantiate(self, depth=2):
        self.data = [0]*depth
        self.depth = depth

        self.rd_ptr = Reg(0)
        self.wr_ptr = Reg(0)

    def peek(self):
        if self.wr_ptr.rd() ==  self.rd_ptr.rd():
            raise FIFOError("Reading from empty FIFO")
        return self.data[self.rd_ptr.rd() % self.depth]

    def enq(self, x):
        if (self.wr_ptr.rd() - self.rd_ptr.rd()) % (2*self.depth) == self.depth:
            raise FIFOError("Enqueueing into full FIFO")
        self.data[self.wr_ptr.rd() % self.depth] = x
        self.wr_ptr.wr((self.wr_ptr.rd() + 1) % (2*self.depth))

    def deq(self):
        if self.wr_ptr.rd() ==  self.rd_ptr.rd():
            raise FIFOError("Dequeueing from empty FIFO")
        self.rd_ptr.wr((self.rd_ptr.rd() + 1) % (2*self.depth))

    def not_full(self):
        return not ((self.wr_ptr.rd() - self.rd_ptr.rd()) % (2*self.depth) == self.depth)

    def not_empty(self):
        return not (self.wr_ptr.rd() == self.rd_ptr.rd())

    def reset(self):
        self.rd_ptr.wr(self.wr_ptr.rd())

class WindowFIFO(Module):
    def instantiate(self, depth, peek_window, enq_window, deq_window):
        self.data = [0]*depth
        self.depth = depth
        self.peek_window = peek_window
        self.enq_window = enq_window
        self.deq_window = deq_window

        self.rd_ptr = Reg(0)
        self.wr_ptr = Reg(0)

    def peek(self):
        if (self.wr_ptr.rd() - self.rd_ptr.rd()) % (2*self.depth) \
                < self.peek_window:
            raise FIFOError("Reading from empty FIFO")
        peek_output = [0]*self.peek_window
        for i in xrange(self.peek_window):
            peek_output[i] = self.data[(self.rd_ptr.rd() + i)% self.depth]
        return peek_output

    def enq(self, x):
        if (self.wr_ptr.rd() - self.rd_ptr.rd() + self.enq_window - 1) % \
                (2*self.depth) >= self.depth:
            raise FIFOError("Enqueueing into full FIFO")
        for i in xrange(self.enq_window):
            self.data[(self.wr_ptr.rd() + i) % self.depth] = x[i]
        self.wr_ptr.wr((self.wr_ptr.rd() + self.enq_window) % (2*self.depth))

    def deq(self):
        if (self.wr_ptr.rd() - self.rd_ptr.rd()) % (2*self.depth) \
                < self.deq_window:
            raise FIFOError("Dequeueing from empty FIFO")
        self.rd_ptr.wr((self.rd_ptr.rd() + self.deq_window) % (2*self.depth))

    def not_full(self):
        return not ((self.wr_ptr.rd() - self.rd_ptr.rd() + self.enq_window - 1) %
                (2*self.depth) >= self.depth)

    def valid(self):
        return not ((self.wr_ptr.rd() - self.rd_ptr.rd()) % (2*self.depth)
                < self.peek_window)

    def not_empty(self):
        return not ((self.wr_ptr.rd() - self.rd_ptr.rd()) % (2*self.depth) < self.deq_window)

    def clear(self):
        self.rd_ptr.wr(self.wr_ptr.rd())
