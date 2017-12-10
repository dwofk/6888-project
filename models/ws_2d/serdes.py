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

    def configure(self, ifmap, weights, bias, image_size, filter_size):
        self.ifmap = ifmap
        self.weights = weights
        self.bias = bias

        self.image_size = image_size
        self.filter_size = filter_size

        self.ifmap_psum_done = False
        self.pass_done.wr(False)

    def tick(self):
        if self.pass_done.rd():
            return

        in_sets = self.arr_y//self.chn_per_word
        out_sets = self.arr_x//self.chn_per_word
        fmap_per_iteration = self.image_size[0]*self.image_size[1]
        num_iteration = self.filter_size[0]*self.filter_size[1]

        if not self.ifmap_psum_done:
            if self.arch_input_chn.vacancy():
                # print "input append"

                x = self.fmap_idx % self.image_size[0]
                y = self.fmap_idx // self.image_size[0]

                if self.curr_set < in_sets:
                    cmin = self.curr_set*self.chn_per_word
                    cmax = cmin + self.chn_per_word
                    # Write ifmap to glb
                    data = np.array([ self.ifmap[x, y, c] for c in range(cmin, cmax) ])
                else:
                    cmin = (self.curr_set - in_sets)*self.chn_per_word
                    cmax = cmin + self.chn_per_word
                    # Write bias to glb
                    data = np.array([ self.bias[c] for c in range(cmin, cmax) ])
                self.arch_input_chn.push(data)
                self.curr_set += 1

                if self.curr_set == (in_sets+out_sets):
                    self.curr_set = 0
                    self.fmap_idx += 1
                if self.fmap_idx == fmap_per_iteration:
                    self.fmap_idx = 0
                    self.ifmap_psum_done = True
                    # print "---- Wrote inputs and biases ----"
        else:
            f_x = self.iteration % self.filter_size[0]
            f_y = self.iteration // self.filter_size[0]

            # Push filters to PE columns. (PE is responsible for pop)
            if self.arch_input_chn.vacancy() and self.iteration < num_iteration:
                cmin = self.curr_set*self.chn_per_word
                cmax = cmin + self.chn_per_word
                data = np.array([self.weights[f_x, f_y, c, self.curr_filter] \
                        for c in range(cmin, cmax) ])

                self.arch_input_chn.push(data)
                self.curr_set += 1
                if self.curr_set == in_sets:
                    self.curr_set = 0
                    self.curr_filter += 1
                if self.curr_filter == self.arr_x:
                    self.curr_filter = 0
                    # print "---- Wrote weights iteration: %d ----" % self.iteration
                    self.iteration += 1
                if self.iteration == num_iteration:
                    # print "---- Wrote all weights ----"
                    self.pass_done.wr(True)


class InputDeserializer(Module):
    def instantiate(self, arch_input_chn, ifmap_chn, weights_chn, psum_chn,
            arr_x, arr_y, chn_per_word):
        self.chn_per_word = chn_per_word
        self.arr_x = arr_x
        self.arr_y = arr_y

        self.stat_type = 'aggregate'
        self.raw_stats = {'dram_rd' : 0, 'dram_to_glb_acc' : 0, 'dram_to_pe_acc' : 0}

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
                self.raw_stats['dram_rd'] += len(data)
                #if (target_str == 'ifmap') or (target_str == 'psum'):
                #    self.raw_stats['dram_to_glb_acc'] += len(data)
                #if target_str == 'weights':
                #    self.raw_stats['dram_to_pe_acc'] += len(data)
                target_chn.push(data)
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
                self.raw_stats['dram_wr'] += len(data)
                self.arch_output_chn.push(data)

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

    def configure(self, ofmap, reference, image_size):
        self.ofmap = ofmap
        self.reference = reference

        self.image_size = image_size

        self.curr_set = 0
        self.fmap_idx = 0

        self.pass_done.wr(False)

    def tick(self):
        if self.pass_done.rd():
            return

        out_sets = self.arr_x//self.chn_per_word
        fmap_per_iteration = self.image_size[0]*self.image_size[1]

        if self.arch_output_chn.valid():
            data = [e for e in self.arch_output_chn.pop()]

            x = self.fmap_idx % self.image_size[0]
            y = self.fmap_idx // self.image_size[0]

            if self.curr_set < out_sets:
                cmin = self.curr_set*self.chn_per_word
                cmax = cmin + self.chn_per_word
                for c in range(cmin, cmax):
                    self.ofmap[x, y, c] = data[c-cmin]
            self.curr_set += 1

            if self.curr_set == out_sets:
                self.curr_set = 0
                self.fmap_idx += 1
            if self.fmap_idx == fmap_per_iteration:
                self.fmap_idx = 0
                self.pass_done.wr(True)
                if np.all(self.ofmap == self.reference):
                    raise Finish("Success")
                else:
                    print(self.ofmap)
                    print(self.reference)
                    print(self.ofmap-self.reference)
                    raise Finish("Validation Failed")
