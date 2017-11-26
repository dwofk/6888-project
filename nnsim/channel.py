from nnsim.module import Module, HWError
from nnsim.reg import Reg

class ChannelError(HWError):
    pass

class Channel(Module):
    def instantiate(self, depth=2):
        self.data = [None]*depth
        self.depth = depth

        self.rd_ptr = Reg(0)
        self.wr_ptr = Reg(0)

    def peek(self, idx=0):
        if not self.valid(idx):
            raise ChannelError("Reading from empty channel")
        return self.data[(self.rd_ptr.rd() + idx) % self.depth]

    def push(self, x):
        if not self.vacancy():
            raise ChannelError("Enqueueing into full channel")
        self.data[self.wr_ptr.rd() % self.depth] = x
        self.wr_ptr.wr((self.wr_ptr.rd() + 1) % (2*self.depth))

    def free(self, count=1):
        if not self.valid(count-1):
            raise ChannelError("Dequeueing from empty channel")
        self.rd_ptr.wr((self.rd_ptr.rd() + count) % (2*self.depth))

    def pop(self):
        self.free(1)
        return self.peek(0)

    def valid(self, idx=0): # check not empty
        return ((self.wr_ptr.rd() - self.rd_ptr.rd()) % (2*self.depth)) > idx

    def vacancy(self, idx=0): # check not full
        return ((self.rd_ptr.rd() + self.depth - self.wr_ptr.rd()) %
                (2*self.depth)) > idx

    def clear(self):
        # Use with care since it conflicts with enq and deq
        self.rd_ptr.wr(self.wr_ptr.rd())

def EmptyChannel(Channel):
    def valid(self, idx=0):
        return False

def FullChannel(Channel):
    def vacancy(self):
        return False

