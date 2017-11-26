from nnsim.fifo import FIFO

class Pipeline(Module):
    def instantiate(self, stages=2):
        self.stages = []
        for stage in xrange(stages):
            self.stages.append(FIFO(depth=1))

    def rd(self):
        if not self.rd_rdy():
            raise FIFOError("Pipeline not ready for read")
        self.stages[-1].deq()
        return self.stages[-1].peek()

    def wr(self, x):
        if not self.wr_rdy():
            raise FIFOError("Pipeline not ready for write")
        self.stages[0].enq(x)

    def deq(self):
        if self.wr_ptr.rd() ==  self.rd_ptr.rd():
            raise FIFOError("Dequeueing from empty FIFO")
        self.rd_ptr.wr((self.rd_ptr.rd() + 1) % (2*self.depth))

    def wr_rdy(self):
        return self.stages[0].not_full()

    def rd_rdy(self):
        return self.stages[-1].not_empty()
