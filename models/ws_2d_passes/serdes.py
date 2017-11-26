from nnsim.module import Module
from nnsim.reg import Reg
from nnsim.simulator import Finish

import numpy as np

class InputSerializer(Module):
    def instantiate(self, arch_input_chn, psum_chn, arr_x, arr_y, chn_per_word):
        # PE static configuration (immutable)
        self.arr_x = arr_x
        self.arr_y = arr_y
        self.chn_per_word = chn_per_word

        self.arch_input_chn = arch_input_chn
        self.psum_chn = psum_chn

        self.ifmap = None
        self.weights = None
        self.bias = None

        self.image_size = (0, 0)
        self.filter_size = (0, 0)

        self.ifmap_psum_done = True
        self.pass_done = Reg(False)

        # State Counters
        self.curr_set = 0
        self.curr_filter = 0
        self.iteration = 0
        self.fmap_idx = 0

    def configure(self, ifmap, weights, bias, image_size, filter_size, curr_pass):
        self.ifmap = ifmap
        self.weights = weights
        self.bias = bias

        self.image_size = image_size
        self.filter_size = filter_size

        self.ifmap_psum_done = False
        self.pass_done.wr(False)

        self.curr_pass = curr_pass
        self.curr_set = 0
        self.curr_filter = 0
        self.iteration = 0
        self.fmap_idx = 0

    def tick(self):
        if self.pass_done.rd():
            return

        in_sets = self.arr_y//self.chn_per_word
        out_sets = self.arr_x//self.chn_per_word
        fmap_per_iteration = self.image_size[0]*self.image_size[1]
        num_iteration = self.filter_size[0]*self.filter_size[1]

        if not self.ifmap_psum_done and (self.psum_chn.valid() or self.curr_pass % 2 == 0):
            if self.arch_input_chn.vacancy():
                # print "input append"

                x = self.fmap_idx % self.image_size[0]
                y = self.fmap_idx // self.image_size[0]

                if self.curr_set < in_sets:
                    cmin = self.curr_set*self.chn_per_word + (self.curr_pass % 2)*4
                    cmax = cmin + self.chn_per_word
                    # Write ifmap to glb
                    #print ("serdes: write ifmap to glb")
                    # print ("ifmap indices1 cmin,cmax: ", cmin,cmax)
                    data = np.array([ self.ifmap[x, y, c] for c in range(cmin, cmax) ])
                else:
                    if (self.curr_pass % 2 == 0): # read biases
                        cmin = (self.curr_set - in_sets)*self.chn_per_word + (self.curr_pass // 2)*8
                        cmax = cmin + self.chn_per_word
                        # Write bias to glb
                        #print ("serdes: write bias to glb")
                        # print ("ifmap indices2 cmin,cmax: ", cmin,cmax)
                        data = np.array([ self.bias[c] for c in range(cmin, cmax) ])
                    else: # read partial sums
                        data = [e for e in self.psum_chn.pop()]
                self.arch_input_chn.push(data)
                self.curr_set += 1

                if self.curr_set == (in_sets+out_sets):
                    self.curr_set = 0
                    self.fmap_idx += 1
                if self.fmap_idx == fmap_per_iteration:
                    self.fmap_idx = 0
                    self.ifmap_psum_done = True
                    # print ("---- Wrote inputs and biases ----")
        else:
            f_x = self.iteration % self.filter_size[0]
            f_y = self.iteration // self.filter_size[0]

            # Push filters to PE columns. (PE is responsible for pop)
            if self.arch_input_chn.vacancy() and self.iteration < num_iteration:
                cmin = self.curr_set*self.chn_per_word+(self.curr_pass % 2)*4
                cmax = cmin + self.chn_per_word
                filter_idx = self.curr_filter + (self.curr_pass // 2)*8
                # print ("weight indices cmin,cmax,filter_idx: ",cmin,cmax,filter_idx)
                data = np.array([self.weights[f_x, f_y, c, filter_idx] \
                        for c in range(cmin, cmax) ])

                self.arch_input_chn.push(data)
                self.curr_set += 1
                if self.curr_set == in_sets:
                    self.curr_set = 0
                    self.curr_filter += 1
                if self.curr_filter == self.arr_x:
                    self.curr_filter = 0
                    # print ("---- Wrote weights iteration: %d ----" % self.iteration)
                    self.iteration += 1
                if self.iteration == num_iteration:
                    # print ("---- Wrote all weights ----")
                    self.pass_done.wr(True)

class InputDeserializer(Module):
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
        self.curr_set = 0

    def tick(self):
        in_sets = self.arr_y//self.chn_per_word
        out_sets = self.arr_x//self.chn_per_word
        fmap_per_iteration = self.image_size[0]*self.image_size[1]

        if self.fmap_idx < fmap_per_iteration:
            if self.curr_set < in_sets:
                target_chn = self.ifmap_chn
                target_str = 'ifmap'
            else:
                target_chn = self.psum_chn
                target_str = 'psum'
        else:
            target_chn = self.weights_chn
            target_str = 'weights'

        if self.arch_input_chn.valid():
            if target_chn.vacancy():
                # print "des to ", target_str
                data = [e for e in self.arch_input_chn.pop()]
                target_chn.push(data)
                self.raw_stats['dram_rd'] += len(data)
                self.curr_set += 1
                if self.fmap_idx < fmap_per_iteration:
                    if self.curr_set == (in_sets+out_sets):
                        self.curr_set = 0
                        self.fmap_idx += 1

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
    def instantiate(self, arch_output_chn, psum_chn, arr_x, arr_y, chn_per_word):
        # PE static configuration (immutable)
        self.arr_x = arr_x
        self.arr_y = arr_y
        self.chn_per_word = chn_per_word

        self.arch_output_chn = arch_output_chn
        self.psum_chn = psum_chn

        self.ofmap = None
        self.reference = None

        self.image_size = (0, 0)

        self.curr_set = 0
        self.fmap_idx = 0

        self.pass_done = Reg(False)

    def configure(self, ofmap, reference, image_size, curr_pass):
        if (curr_pass == 0): # so that ofmap doesnt get rewritten with zeros
            self.ofmap = ofmap

        self.reference = reference

        self.image_size = image_size

        self.curr_set = 0
        self.fmap_idx = 0
        self.curr_pass = curr_pass
        self.num_passes = 4

        self.pass_done.wr(False)

    def tick(self):
        if self.pass_done.rd():
            return

        out_sets = self.arr_x//self.chn_per_word
        fmap_per_iteration = self.image_size[0]*self.image_size[1]

        if self.arch_output_chn.valid() and (self.psum_chn.vacancy() or self.curr_pass % 2 == 1):
            data = [e for e in self.arch_output_chn.pop()]
            if ((self.curr_pass % 2) == 0): # push ofmap psum to serializer on pass 0 and 2
                self.psum_chn.push(data)

            x = self.fmap_idx % self.image_size[0]
            y = self.fmap_idx // self.image_size[0]

            if self.curr_set < out_sets:
                channel_offset = 0
                if (self.curr_pass > 1):
                    channel_offset = 8
                cmin = self.curr_set*self.chn_per_word + channel_offset
                cmax = cmin + self.chn_per_word
                for c in range(cmin, cmax):
                    self.ofmap[x, y, c] = data[c-cmin]

            self.curr_set += 1

            if self.curr_set == out_sets:
                self.curr_set = 0
                self.fmap_idx += 1
            if self.fmap_idx == fmap_per_iteration:
                self.fmap_idx = 0
                if (self.curr_pass == self.num_passes-1):
                    self.pass_done.wr(True)
                    if np.all(self.ofmap == self.reference):
                        raise Finish("Success")
                    else:
                        print(self.ofmap)
                        print(self.reference)
                        print(self.ofmap-self.reference)
                        raise Finish("Validation Failed")
