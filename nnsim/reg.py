from nnsim.module import Module, HWError

class RegError(HWError):
    pass

class Reg(Module):
    def instantiate(self, reset_val):
        self.reset_val = reset_val
        self.data_s = reset_val
        self.data_m = None

    def rd(self):
        return self.data_s

    def wr(self, x):
        if self.data_m is not None:
            raise RegError("Double write on register")
        self.data_m = x

    def reset(self):
        self.data_s = self.reset_val
        self.data_m = None

    def __ntick__(self):
        if self.data_m is not None:
            self.data_s = self.data_m
            self.data_m = None
