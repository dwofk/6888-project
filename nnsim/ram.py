from nnsim.module import Module, HWError
from nnsim.reg import Reg
import numpy as np

RD = True
WR = False

class RAMError(HWError):
    pass

class SRAM(Module):
    def instantiate(self, depth, width=1, nports=1, dtype=np.int64):
        # depth: The number of address stored in the RAM
        # width: The number of words stored per address (NOT bits)
        # word-size is application dependent and implicit but <64b

        self.width = width
        self.nports = nports
        self.port_used = [False]*nports
        self.data = np.zeros((depth, width)).astype(dtype)

        # Emulate read latency
        self.output_reg = np.zeros((nports, width)).astype(dtype)
        self.rd_nxt = np.zeros((nports, width)).astype(dtype)

        # Emulate write latency
        self.port_wr = [False]*nports
        self.wr_nxt = np.zeros((nports, width)).astype(dtype)
        self.wr_addr_nxt = np.zeros(nports).astype(np.uint32)


    def request(self, access, address, data=None, port=0):
        if self.port_used[port]:
            raise RAMError("Port conflict on port %d" % port)
        self.port_used[port] = True

        if access == RD:
            self.rd_nxt[port, :] = self.data[address, :]
        elif access == WR:
            self.port_wr[port] = True
            self.wr_addr_nxt[port] = address
            if self.width == 1:
                self.wr_nxt[port, 0] = data
            else:
                self.wr_nxt[port, :] = data[:]

    def response(self, port=0):
        data = self.output_reg[port]
        return data[0] if self.width == 1 else data

    def __ntick__(self):
        self.output_reg[:] = self.rd_nxt[:]
        for port in range(self.nports):
            self.port_used[port] = False

            if self.port_wr[port]:
                self.port_wr[port] = False
                self.data[self.wr_addr_nxt[port], :] = self.wr_nxt[port, :]

    def dump(self):
        for i in range(self.data.shape[0]):
            print(i, self.data[i])

# class NoLatencyRF(Module):
#     def instantiate(self, depth, width=1, dtype=np.uint64):
#         # depth: The number of address stored in the RAM
#         # width: The number of words stored per address (NOT bits)
#         # word-size is application dependent and implicit but <64b
# 
#         self.width = width
#         self.rd_port_used = None
#         self.wr_port_used = None
#         self.data = np.zeros((depth, width)).astype(dtype)
# 
#     def rd(self, address):
#         if self.rd_port_used is not None:
#             raise RAMError("2 reads on a RAM with 1 rd-port")
#         self.rd_port_used = address
#         if self.width == 1:
#             return self.data[address, 0]
#         else:
#             return self.data[address]
#         return self.data_s
# 
#     def wr(self, address, data):
#         if self.wr_port_used is not None:
#             raise RAMError("2 writes on a RAM with 1 wr-port")
#         self.wr_port_used = address
#         if self.width == 1:
#             return self.data[address, 0] = data
#         else:
#             return self.data[address] = data
# 
#     def __ntick__(self):
#         self.rd_port_used = None
#         self.wr_port_used = None
