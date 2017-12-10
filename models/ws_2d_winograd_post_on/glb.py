from nnsim.module import Module
from nnsim.ram import SRAM, RD, WR
from nnsim.channel import Channel

class IFMapGLB(Module):
    def instantiate(self, wr_chn, rd_chn, glb_depth, chn_per_word):
        self.wr_chn = wr_chn
        self.rd_chn = rd_chn
        self.chn_per_word = chn_per_word
        self.glb_depth = glb_depth
        self.name = 'ifmap_glb'
        
        self.stat_type = 'show'
        self.raw_stats = {'size' : (glb_depth, chn_per_word), 'ifmap_glb_rd': 0, 'ifmap_glb_wr': 0}


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
        self.curr_tile = 0
        self.num_tiles = 4
        self.addr = 0
        print ("ifmap glb_size: ", self.glb_depth)

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
                self.raw_stats['ifmap_glb_wr'] += len(data)
                # print "ifmap_glb wr"
                # Write ifmap to glb
                addr = self.fmap_sets*self.curr_tile + self.curr_set + self.fmap_idx*self.num_tiles
                print ("ifmap_to_glb: ", self.curr_tile, self.fmap_idx, addr)
                self.curr_set += 1
                self.sram.request(WR, addr, data)
                if self.curr_set == self.fmap_sets:
                    self.curr_set = 0
                    self.curr_tile += 1
                if self.curr_tile == self.num_tiles:
                    # Done initializing ifmaps and psums
                    # self.sram.dump()
                    self.curr_tile = 0
                    self.fmap_idx += 1
                if self.fmap_idx == self.fmap_per_iteration:
                    self.wr_done = True
        else:
            if self.rd_chn.vacancy(1) and self.addr < self.glb_depth:
                # Read from GLB and deal with SRAM latency
                self.sram.request(RD, self.addr)
                print ("read_ifmap_glb: ", self.addr)
                self.addr += 1
                self.last_read.push(False)

                # Process the last read sent to the GLB SRAM
            if self.last_read.valid():
                print ("ifmap_glb_to_noc")
                is_zero = self.last_read.pop()
                data = [e for e in self.sram.response()]
                # print "ifmap rd glb", data
                self.rd_chn.push(data)
                self.raw_stats['ifmap_glb_rd'] += len(data)
                
class BiasGLB(Module):
    def instantiate(self, wr_chn, rd_chn):
        self.wr_chn = wr_chn
        self.rd_chn = rd_chn
        self.name = 'bias_glb'
        
        self.stat_type = 'show'
        self.raw_stats = {'size' : (0, 0), 'bias_glb_rd': 0, 'bias_glb_wr': 0}
        
    def tick(self):
        if self.wr_chn.valid() and self.rd_chn.vacancy():
            data = self.wr_chn.pop()
            self.rd_chn.push(data)
            #self.raw_stats['bias_glb_rd'] += len(data)
            #self.raw_stats['bias_glb_rd'] += len(data)

class WeightsGLB(Module):
    def instantiate(self, wr_chn, rd_chn):
        self.wr_chn = wr_chn
        self.rd_chn = rd_chn
        self.name = 'weight_glb'
        
        self.stat_type = 'show'
        self.raw_stats = {'size' : (0, 0), 'weight_glb_rd': 0, 'weight_glb_wr': 0}
        
    def tick(self):
        if self.wr_chn.valid() and self.rd_chn.vacancy():
            data = self.wr_chn.pop()
            self.rd_chn.push(data)
            #self.raw_stats['weight_glb_rd'] += len(data)
            #self.raw_stats['weight_glb_wr'] += len(data)





