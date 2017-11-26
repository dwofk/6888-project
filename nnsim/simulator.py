import nnsim.module

class Finish(Exception):
    pass

class Simulator(object):
    def __init__(self, tb_module, dump_stats):
        self.tb_module = tb_module
        self.dump_stats = dump_stats
        self.clk_ticks = 0

        self.tb_module.__setup__()

    def reset(self):
        self.tb_module.__reset__()
        self.clk_ticks = 0

    def run(self, num_ticks, verbose=False):
        curr_ticks = 0
        try:
            while (num_ticks is None) or (curr_ticks < num_ticks):
                if verbose:
                    print("---- Tick #%d -----" % self.clk_ticks)
                self.tb_module.__tick__()
                if verbose:
                    print("---- NTick #%d ----" % self.clk_ticks)
                self.tb_module.__ntick__()
                self.clk_ticks += 1
                curr_ticks += 1
        except Finish as msg:
            if self.dump_stats:
                self.tb_module.finalize_stats()
                self.tb_module.dump_stats()
                
            print("\ncyc %d: %s" % (self.clk_ticks, msg))
        except KeyboardInterrupt:
            pass

def run_tb(tb_module, nticks=None, verbose=False, dump_stats=False):
    sim = Simulator(tb_module, dump_stats)
    sim.reset()
    sim.run(nticks, verbose)

