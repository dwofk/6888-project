import pytest
from nnsim.module import Module, HWError
from nnsim.reg import Reg
import nnsim.simulator as sim

class RegTB(Module):
    def instantiate(self):
        self.ra = Reg(0)
        self.rb = Reg(10)

    def tick(self):
        print("ra val: %d" % self.ra.rd())
        print("rb val: %d" % self.rb.rd())
        self.ra.wr(self.ra.rd() + 1)
        self.rb.wr(self.ra.rd() + self.rb.rd())

def test_reg_rd_wr():
    reg_tb = RegTB()
    sim.run_tb(reg_tb, 10, True)
