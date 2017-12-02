from nnsim.module import Module
from nnsim.reg import Reg
from nnsim.simulator import Finish

import numpy as np

class InputSerializer(Module):
    def instantiate(self, arch_input_chn, arr_x, arr_y, chn_per_word):
        # PE static configuration (immutable)
        self.arr_x = arr_x
        self.arr_y = arr_y
        self.chn_per_word = chn_per_word
        
        self.arch_input_chn = arch_input_chn

        self.ifmap = None
        self.weights = None

        self.image_size = (0, 0)
        self.filter_size = (0, 0)

        self.ifmap_psum_done = True
        self.pass_done = Reg(False)

        # State Counters
        self.curr_set = 0
        self.curr_filter = 0
        self.iteration = 0
        self.fmap_idx = 0

    def configure(self, ifmap, weights, image_size, filter_size):
        self.ifmap = ifmap
        self.weights = weights

        self.image_size = image_size
        self.filter_size = image_size
        self.num_tiles = 4
        
        self.send_ifmap = True
        self.fmap_idx = 0
        self.fmap_tile = 0
        self.weight_idx = 0

        self.fmap_wr_done = False
        self.pass_done.wr(False)

    def tick(self):
        if self.pass_done.rd():
            return

        in_sets = self.arr_y // self.chn_per_word # 1
        out_sets = self.arr_x//self.chn_per_word # 2
        
        fmap_per_iteration = self.image_size[0]*self.image_size[1]
        weights_per_filter = self.filter_size[0]*self.filter_size[1]

        if self.arch_input_chn.vacancy() and not self.pass_done.rd():

            if not self.fmap_wr_done: # send ifmap
                # send 4 elements of ifmap
                x = self.fmap_idx % self.image_size[0]
                y = self.fmap_idx // self.image_size[0]
                cmin = self.curr_set*self.chn_per_word # 0
                cmax = cmin + self.chn_per_word # 4
                data = np.array([ self.ifmap[x, y, c, self.fmap_tile] for c in range(cmin, cmax) ])
                self.fmap_tile += 1
                print ("input ser x,y,cmin,cmax,ifmaps: ",x,y,cmin,cmax,data)
            else: # send weight
                # send 4 elements of weights (twice in succession)
                x = self.weight_idx % self.filter_size[0]
                y = self.weight_idx // self.filter_size[1]
                cmin = 0
                cmax = cmin + self.chn_per_word
                data = np.array([self.weights[x, y, c, self.curr_filter] for c in range(cmin, cmax) ])
                self.curr_filter += 1
                print ("input ser x,y,cmin,cmax,curr_filter,weights: ",x,y,cmin,cmax,self.curr_filter,data)
            self.arch_input_chn.push(data)    
            if self.fmap_tile == self.num_tiles:
                self.fmap_tile = 0
                self.fmap_idx += 1
            if self.fmap_idx == fmap_per_iteration:
                self.fmap_wr_done = True
                self.fmap_idx = 0
            if self.curr_filter == self.arr_x:
                self.weight_idx += 1
                self.curr_filter = 0
            if self.weight_idx == weights_per_filter:
                self.pass_done.wr(True)


class InputDeserializer(Module): # TODO WHERE WE LEFT OFF
    def instantiate(self, arch_input_chn, ifmap_chn, weights_chn, psum_chn,
            arr_x, arr_y, chn_per_word):
        self.chn_per_word = chn_per_word
        self.arr_x = arr_x
        self.arr_y = arr_y

        self.stat_type = 'aggregate'
        self.raw_stats = {'dram_rd' : 0}

        self.arch_input_chn = arch_input_chn
        self.ifmap_chn = ifmap_chn
        self.weights_chn = weights_chn
        self.psum_chn = psum_chn

        self.image_size = (0, 0)

        self.fmap_idx = 0
        self.curr_set = 0

    def configure(self, image_size):
        self.image_size = image_size

        self.fmap_idx = 0
        self.fmap_tile = 0
        self.num_tiles = 4
        self.curr_set = 0
        self.fmap_wr_done = False

    def tick(self):
        in_sets = self.arr_y//self.chn_per_word # 1
        out_sets = self.arr_x//self.chn_per_word # 2
        fmap_per_iteration = self.image_size[0]*self.image_size[1]
 
        if not self.fmap_wr_done:
            target_chn = self.ifmap_chn
            target_str = 'ifmap'
        else:
            target_chn = self.weights_chn
            target_str = 'weights'

        if self.arch_input_chn.valid():
            if target_chn.vacancy():
                # print "des to ", target_str
                data = [e for e in self.arch_input_chn.pop()]
                target_chn.push(data)
                self.raw_stats['dram_rd'] += len(data)
                self.fmap_tile += 1
                if self.fmap_tile == self.num_tiles:
                    self.fmap_tile = 0
                    self.fmap_idx += 1
                if self.fmap_idx == fmap_per_iteration:
                    self.fmap_wr_done = True
                    self.fmap_idx = 0       
                        

class OutputSerializer(Module):
    def instantiate(self, arch_output_chn, psum_chn):
        self.arch_output_chn = arch_output_chn
        self.psum_chn = psum_chn
        
        self.stat_type = 'aggregate'
        self.raw_stats = {'dram_wr' : 0}


    def configure(self):
        pass

    def tick(self):
        if self.psum_chn.valid():
            if self.arch_output_chn.vacancy():
                data = [e for e in self.psum_chn.pop()]
                self.arch_output_chn.push(data)
                self.raw_stats['dram_wr'] += len(data)

class OutputDeserializer(Module):
    def instantiate(self, arch_output_chn, arr_x, arr_y, chn_per_word):
        # PE static configuration (immutable)
        self.arr_x = arr_x
        self.arr_y = arr_y
        self.chn_per_word = chn_per_word

        self.arch_output_chn = arch_output_chn

        self.ofmap = None
        self.reference = None

        self.image_size = (0, 0)

        self.curr_set = 0
        self.fmap_idx = 0
        
        self.pass_done = Reg(False)

    def configure(self, ofmap, reference, image_size, bias):
        self.ofmap = np.zeros((image_size[0], image_size[1], self.arr_x, 4)).astype(np.int64) # 4x4x8x4
        #self.ofmap_transformed = ofmap
        self.reference = reference
        self.num_tiles = 4
        self.curr_tile = 0

        self.image_size = image_size
        self.bias = bias # TODO

        self.curr_set = 0
        self.fmap_idx = 0

        self.pass_done.wr(False)

    def tick(self):
        if self.pass_done.rd():
            return
        print ("output deser curr_tile, fmap_idx: ", self.curr_tile, self.fmap_idx)
        out_sets = self.arr_x//self.chn_per_word # 2
        fmap_per_iteration = self.image_size[0]*self.image_size[1]

        if self.arch_output_chn.valid():
            data = [e for e in self.arch_output_chn.pop()]

            x = self.fmap_idx % self.image_size[0]
            y = self.fmap_idx // self.image_size[0]

            if self.curr_set < out_sets:
                cmin = self.curr_set*self.chn_per_word
                cmax = cmin + self.chn_per_word
                for c in range(cmin, cmax):
                    self.ofmap[x, y, c, self.curr_tile] = data[c-cmin]
            self.curr_set += 1

            if self.curr_set == out_sets:
                self.curr_set = 0
                #self.fmap_idx += 1
                self.curr_tile += 1
            if self.curr_tile == 4:
                self.fmap_idx += 1
                self.curr_tile = 0
            if self.fmap_idx == fmap_per_iteration:
                self.fmap_idx = 0
                self.pass_done.wr(True)
                self.ofmap = self.ofmap//(128*128)
                print ("reference shape: ", self.reference.shape)
                print ("ofmap shape: ", self.ofmap.shape)
                if np.all(self.ofmap == self.reference):
                    raise Finish("Success")
                else:
                    print ("ofmap: ")
                    print(self.ofmap)
                    print ("reference: ")
                    print(self.reference)
                    print ("difference: ")
                    print(self.ofmap-self.reference)
                    raise Finish("Validation Failed")

