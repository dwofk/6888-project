from nnsim.module import Module
from nnsim.ram import SRAM, RD, WR
from nnsim.channel import Channel

class IFMapGLB(Module):
    def instantiate(self, wr_chn, rd_chn, glb_depth, chn_per_word):
        self.wr_chn = wr_chn
        self.rd_chn = rd_chn
        self.chn_per_word = chn_per_word
        self.name = 'ifmap_glb'

        self.stat_type = 'show'
        self.raw_stats = {'size' : (glb_depth, chn_per_word), 'rd': 0, 'wr': 0}


        self.sram = SRAM(glb_depth, chn_per_word)
        self.last_read = Channel(3)

        self.image_size = (0, 0)
        self.filter_size = (0, 0)
        self.fmap_sets = 0
        self.fmap_per_iteration = 0

        self.curr_set = 0
        self.fmap_idx = 0
        self.iteration = 0
        self.wr_done = False

    def configure(self, image_size, filter_size, fmap_sets, fmap_per_iteration):
        self.wr_done = False

        self.image_size = image_size
        self.filter_size = filter_size
        self.fmap_sets = fmap_sets
        self.fmap_per_iteration = fmap_per_iteration
        self.curr_set = 0
        self.fmap_idx = 0
        self.iteration = 0
        self.wr_done = False

    def tick(self):
        num_iteration = self.filter_size[0]*self.filter_size[1]
        offset_x = (self.filter_size[0] - 1)//2
        offset_y = (self.filter_size[1] - 1)//2
        filter_x = self.iteration % self.filter_size[0] - offset_x
        filter_y = self.iteration // self.filter_size[0] - offset_y

        if not self.wr_done:
            # Write to GLB
            if self.wr_chn.valid():
                data = self.wr_chn.pop()
                self.raw_stats['wr'] += len(data)
                # print "ifmap_glb wr"
                # Write ifmap to glb
                # print "ifmap_to_glb: ", in_sets, self.fmap_idx, self.curr_set
                addr = self.fmap_sets*self.fmap_idx + self.curr_set
                self.curr_set += 1
                self.sram.request(WR, addr, data)
                if self.curr_set == self.fmap_sets:
                    self.curr_set = 0
                    self.fmap_idx += 1
                if self.fmap_idx == self.fmap_per_iteration:
                    # Done initializing ifmaps and psums
                    # self.sram.dump()
                    self.fmap_idx = 0
                    self.wr_done = True
        else:
            # Read from GLB and deal with SRAM latency
            if self.rd_chn.vacancy(1) and self.iteration < num_iteration:
                fmap_x = self.fmap_idx % self.image_size[0]
                fmap_y = self.fmap_idx  // self.image_size[0]
                ifmap_x, ifmap_y = (fmap_x + filter_x, fmap_y + filter_y)
                if (ifmap_x < 0) or (ifmap_x >= self.image_size[0]) or \
                        (ifmap_y < 0) or (ifmap_y >= self.image_size[1]):
                    # print "ifmap req zero", self.iteration, self.fmap_idx
                    self.last_read.push(True)
                else:
                    fmap_idx = (ifmap_y*self.image_size[0]) + ifmap_x
                    addr = self.fmap_sets*fmap_idx + self.curr_set
                    # print "ifmap req glb", self.iteration, self.fmap_idx
                    self.sram.request(RD, addr)
                    self.last_read.push(False)
                self.curr_set += 1

                if self.curr_set == self.fmap_sets:
                    self.curr_set = 0
                    self.fmap_idx += 1
                if self.fmap_idx == self.fmap_per_iteration:
                    self.fmap_idx = 0
                    self.iteration += 1

            # Process the last read sent to the GLB SRAM
            if self.last_read.valid():
                is_zero = self.last_read.pop()
                data = [0]*self.chn_per_word if is_zero else \
                        [e for e in self.sram.response()]
                # print "ifmap rd glb", data

                self.rd_chn.push(data)
                self.raw_stats['rd'] += len(data)

class PSumGLB(Module):
    def instantiate(self, dram_wr_chn, noc_wr_chn, rd_chn, glb_depth, chn_per_word):
        self.dram_wr_chn = dram_wr_chn
        self.noc_wr_chn = noc_wr_chn
        self.rd_chn = rd_chn
        self.chn_per_word = chn_per_word
        self.name = 'psum_glb'

        self.stat_type = 'show'
        self.raw_stats = {'size' : (glb_depth, chn_per_word), 'rd': 0, 'wr': 0}

        self.sram = SRAM(glb_depth, chn_per_word, nports=2)
        self.last_read = Channel(3)

        self.filter_size = (0, 0)
        self.fmap_sets = 0
        self.fmap_per_iteration = 0

        self.rd_set = 0
        self.fmap_rd_idx = 0
        self.iteration = 0

        self.wr_set = 0
        self.fmap_wr_idx = 0
        self.wr_done = False

    def configure(self, filter_size, fmap_sets, fmap_per_iteration):
        self.wr_done = False

        self.filter_size = filter_size
        self.fmap_sets = fmap_sets
        self.fmap_per_iteration = fmap_per_iteration

        self.rd_set = 0
        self.fmap_rd_idx = 0
        self.iteration = 0

        self.wr_set = 0
        self.fmap_wr_idx = 0
        self.wr_done = False

    def tick(self):
        num_iteration = self.filter_size[0]*self.filter_size[1]

        if not self.wr_done:
            # Write to GLB
            if self.dram_wr_chn.valid():
                data = self.dram_wr_chn.pop()
                self.raw_stats['wr'] += len(data)
                # print "psum_glb wr"
                # Write ifmap to glb
                #print ("ifmap_to_glb: ", self.fmap_wr_idx, self.wr_set)
                addr = self.fmap_sets*self.fmap_wr_idx + self.wr_set
                self.wr_set += 1
                self.sram.request(WR, addr, data, port=0)
                if self.wr_set == self.fmap_sets:
                    self.wr_set = 0
                    self.fmap_wr_idx += 1
                if self.fmap_wr_idx == self.fmap_per_iteration:
                    # Done initializing ifmaps and psums
                    # self.sram.dump()
                    self.fmap_wr_idx = 0
                    self.wr_done = True
        else:
            # Read from GLB and deal with SRAM latency
            # print self.rd_chn.vacancy(1), self.rd_chn.rd_ptr.rd(), self.rd_chn.wr_ptr.rd()
            if self.rd_chn.vacancy(1) and self.iteration < num_iteration:
                addr = self.fmap_sets*self.fmap_rd_idx + self.rd_set
                #print ("psum req glb", self.iteration, self.fmap_rd_idx, self.rd_set)
                self.sram.request(RD, addr, port=0)
                self.last_read.push(False)
                self.rd_set += 1

                if self.rd_set == self.fmap_sets:
                    self.rd_set = 0
                    self.fmap_rd_idx += 1
                if self.fmap_rd_idx == self.fmap_per_iteration:
                    self.fmap_rd_idx = 0
                    self.iteration += 1

            # Process the last read sent to the GLB SRAM
            if self.last_read.valid():
                is_zero = self.last_read.pop()
                data = [0]*self.chn_per_word if is_zero else \
                        [e for e in self.sram.response()]
                self.rd_chn.push(data)
                self.raw_stats['rd'] += len(data)
                #print ("psum rd glb", data)

            if self.noc_wr_chn.valid():
                #print ("psum_to_glb: ", self.fmap_wr_idx, self.wr_set)
                data = self.noc_wr_chn.pop()
                self.raw_stats['wr'] += len(data)
                addr = self.fmap_sets*self.fmap_wr_idx + self.wr_set
                #print ("psum wr glb", self.fmap_wr_idx, self.wr_set, data)
                self.wr_set += 1
                self.sram.request(WR, addr, data, port=1)
                if self.wr_set == self.fmap_sets:
                    self.wr_set = 0
                    self.fmap_wr_idx += 1
                if self.fmap_wr_idx == self.fmap_per_iteration:
                    # Done initializing ifmaps and psums
                    # self.sram.dump()
                    self.fmap_wr_idx = 0

class WeightsGLB(Module):
    def instantiate(self, wr_chn, rd_chn):
        self.wr_chn = wr_chn
        self.rd_chn = rd_chn
        self.name = 'weight_glb'

        self.stat_type = 'show'
        self.raw_stats = {'size' : (0, 0), 'rd': 0, 'wr': 0}

    def tick(self):
        if self.wr_chn.valid() and self.rd_chn.vacancy():
            data = self.wr_chn.pop()
            self.rd_chn.push(data)
            self.raw_stats['rd'] += len(data)
            self.raw_stats['wr'] += len(data)
