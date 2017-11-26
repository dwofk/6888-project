from nnsim.module import HWError
from collections import defaultdict

class CostError(HWError):
    pass

# default values for 65nm process
#   ALU:1, RF:1, PE/LN:2, GB:6, DRAM:200

# Track number of accesses, and accumulate total energy (normalized over ALU)
class CostModel:
    def init(self,bitwidth=32,registers=128,num_pe=200,buffer_kb=100):
        self.uses=defaultdict(int)

        self.cost=defaultdict(int)
        self.ALU(bitwidth)
        self.RegisterFile(registers, bitwidth)
        self.LocalNetwork(num_pe)
        self.GlobalBuffer(buffer_kb*1024)
        self.DRAM(num_pe)

    def count(self, event, count=1):
        self.uses[event] += count

    def ALU(self, bitwidth=32):
        self.cost["ALU"] = 1


    def RegisterFile(self, registers=128, bitwidth=32):
        """RF register file energy
        Dependent on the number of registers.
        If within 0.5 - 1kB total assume 1x ALU"""

        bytes = registers * bitwidth / 8
        if bytes > 1024:
            raise CostError("Estimate RF cost if you need a larger register file")
        self.cost["RF"] = 1 # RF -> PE
        # register read/write

# PE - Local PE network
#   assume talking to neighbors only
#   for 200-1000 PEs total
    def LocalNetwork(self, num_pes = 200):
        if num_pes > 1000:
            raise CostError("Estimate cost if you need a large number of PEs")
        self.cost["LN"] = 2 # PE -> PE

# GB Global Buffer
#   assume all PEs have direct access
#   no dynamic network
#   for 100-500kB assume 6x
    def GlobalBuffer(self, bytes = 100*1024):
        if bytes > 500*1024:
            raise CostError("Estimate cost if you need a larger Global Buffer")
        self.cost["GB"] = 6 # GB -> PE

    def DRAM(self, controllers=1):
        self.cost["DRAM"] = 200 # DRAM -> GB

    def energy(self, verbose=True):
        """Tally up energy consumption"""
        total=0
        for c in self.uses:
            energy = self.cost[c] * self.uses[c]
            if verbose:
                print("%s\t%d\t%d\t%d\n" % (c, self.cost[c], self.uses[c], energy))
            total += energy
        if verbose:
            print("%s\t  \t\t%d\n" % ("Total", total))
        return total
