import pytest
from nnsim.module import Module
from nnsim.reg import Reg
from nnsim.fifo import FIFO, FIFOError
import nnsim.simulator as sim

class FIFOTB(Module):
    def instantiate(self, check_fifo=True):
        self.check_fifo = check_fifo
        self.counter = Reg(0)
        self.fifo = FIFO(4)

    def tick(self):
        count = self.counter.rd()
        self.counter.wr((count + 1) % 256)

        if count % 4 < 2 and (self.fifo.not_full() or not self.check_fifo):
            self.fifo.enq(count)
            print("enq: %d" % count)

        if count % 4 == 3 and (self.fifo.not_empty() or not self.check_fifo):
            peek = self.fifo.peek()
            self.fifo.deq()
            print("deq: %d" % peek)


def test_fifo_checked():
    fifo_tb = FIFOTB(True)
    sim.run_tb(fifo_tb, 20, True)


def test_fifo_unchecked():
    with pytest.raises(FIFOError):
          fifo_tb = FIFOTB(False)
          sim.run_tb(fifo_tb, 20, True)
