from nnsim.module import Module, HWError
from nnsim.reg import Reg
from nnsim.channel import Channel


class PE(Module):
    def instantiate(self, loc_x, loc_y,
            ifmap_chn, filter_chn,
            psum_in_chn, psum_out_chn):
        # PE identifier (immutable)
        self.loc_x = loc_x
        self.loc_y = loc_y
        
        self.stat_type = 'aggregate'
        self.raw_stats = {'pe_mac' : 0}

        # IO channels
        self.ifmap_chn = ifmap_chn
        self.filter_chn = filter_chn
        self.psum_in_chn = psum_in_chn
        self.psum_out_chn = psum_out_chn

        # PE controller state (set by configure)
        self.fmap_per_iteration = 0
        self.num_iteration = 0

        self.fmap_idx = None
        self.iteration = None

    def configure(self, fmap_per_iteration, num_iteration):
        self.fmap_per_iteration = fmap_per_iteration
        self.num_iteration = num_iteration

        self.fmap_idx = 0
        self.iteration = 0

    def tick(self):
        #print ("psum_in_chn, ifmap_chn, filter_chn: ",self.psum_in_chn.valid(),self.ifmap_chn.valid(), self.filter_chn.valid())
        if self.psum_in_chn.valid() and self.ifmap_chn.valid() and \
                self.filter_chn.valid():
            if self.psum_out_chn.vacancy():
                in_psum = self.psum_in_chn.pop()
                ifmap = self.ifmap_chn.pop()
                weight = self.filter_chn.peek()
                self.psum_out_chn.push(in_psum+ifmap*weight)
                self.raw_stats['pe_mac'] += 1
                #print("PE(%d, %d) fired @ (%d, %d)" % (self.loc_x, self.loc_y, self.iteration, self.fmap_idx))

                self.fmap_idx += 1
                if self.fmap_idx == self.fmap_per_iteration:
                    self.fmap_idx = 0
                    self.filter_chn.pop()
                    self.iteration += 1
