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
        self.bias_idx = 0
        

    def configure(self, ifmap, weights, biases, image_size, filter_size):
        #self.ifmap = ifmap
        #self.weights = weights
        self.biases = biases

        self.image_size = image_size
        self.filter_size = image_size
        self.num_tiles = 4
        
        self.send_ifmap = True
        self.fmap_idx = 0
        self.fmap_tile = 0
        self.weight_idx = 0
        
        self.bias_sets = 2

        self.fmap_wr_done = False
        self.weight_wr_done = False
        self.bias_wr_done = False
        self.pass_done.wr(False)
        
        # pad the ifmaps
        ifmap_padded = np.pad(ifmap,1,'constant')
        ifmap_padded = ifmap_padded[:,:,1:5]
        
        # Winograd transforms
        B_T = np.array([ [1,0,-1,0],
                     [0,1,1,0],
                     [0,-1,1,0],
                     [0,1,0,-1] ])
        B = B_T.transpose()
        G = np.array([ [1,0,0],
                   [0.5,0.5,0.5],
                   [0.5,-0.5,0.5],
                   [0,0,1] ])
        G_T = G.transpose()
        A_T = np.array([ [1,1,1,0],
                     [0,1,-1,-1] ])
        A = A_T.transpose()
        
        C = 4 # num channels
        K = 8 # num filters
        T = 4 # num tiles
        U = np.zeros([4,4,C,K]) # 4,4,4,8
        V = np.zeros([4,4,C,T]) # 4,4,4
        # FOR LOOPS USED B/C NOT COUNTING OFF CHIP PROCESSING IN PERFORMANCE STATISTICS (will unroll loops in on chip processing)
        for t in range(T):
            for k in range(K): # filter
                for c in range(C): # channel
                    g = weights[:, :, c, k]# 3x3 filter
                    U[:,:,c,k] = np.dot(G,np.dot(g,G_T)) # 4x4
            for c in range(C): # channel
                x_idx = (t // 2)*2
                y_idx = (t % 2)*2
                d = ifmap_padded[x_idx:x_idx+4,y_idx:y_idx+4,c] # 4x4 ifmap tile
                V[:,:,c,t] = np.dot(B_T,np.dot(d,B)) 
        # Convert to integers for on chip processing, LOSE ACCURACY -> bit shift
        U = 128*U; # left shift by 7 bits to avoid precision loss when convert float to int
        V = 128*V;
        self.weights = U.astype(np.int64) # transformed weights
        self.ifmap = V.astype(np.int64) # transformed ifmap
        print ("U ser: ", self.weights)
        print ("V ser: ", self.ifmap)

    def tick(self):
        if self.pass_done.rd():
            return

        in_sets = self.arr_y // self.chn_per_word # 1
        out_sets = self.arr_x//self.chn_per_word # 2
        
        fmap_per_iteration = self.image_size[0]*self.image_size[1]
        weights_per_filter = self.filter_size[0]*self.filter_size[1]

        if self.arch_input_chn.vacancy() and not self.pass_done.rd():
            if not self.bias_wr_done:
                kmin = self.bias_idx*self.chn_per_word
                kmax = kmin + self.chn_per_word
                data = np.array([self.biases[k] for k in range(kmin,kmax)])
                self.bias_idx += 1
                print ("input ser kmin,kmax,biases: ",kmin,kmax,data)                
            elif not self.fmap_wr_done: # send ifmap
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
                self.weight_wr_done = True
                self.pass_done.wr(True)
            if self.bias_idx == self.bias_sets: #2
                self.bias_wr_done = True


class InputDeserializer(Module): # TODO WHERE WE LEFT OFF
    def instantiate(self, arch_input_chn, ifmap_chn, weights_chn, bias_chn, # TODO CONNECT BIAS NOT PSUM CHN
            arr_x, arr_y, chn_per_word):
        self.chn_per_word = chn_per_word
        self.arr_x = arr_x
        self.arr_y = arr_y

        self.stat_type = 'aggregate'
        self.raw_stats = {'dram_rd' : 0, 'dram_to_glb_acc' : 0, 'dram_to_pe_acc' : 0, 'dram_to_post_tr' : 0}

        self.arch_input_chn = arch_input_chn
        self.ifmap_chn = ifmap_chn
        self.weights_chn = weights_chn
        self.bias_chn = bias_chn

        self.image_size = (0, 0)

        self.fmap_idx = 0
        self.curr_set = 0

    def configure(self, image_size, filter_size):
        self.image_size = image_size
        self.filter_size = filter_size

        self.fmap_idx = 0
        self.fmap_tile = 0
        self.num_tiles = 4
        self.curr_set = 0
        self.fmap_wr_done = False
        self.weight_wr_done = False
        self.bias_wr_done = False
        self.curr_filter = 0
        self.weight_idx = 0
        self.bias_idx = 0
        

    def tick(self):
        in_sets = self.arr_y//self.chn_per_word # 1
        out_sets = self.arr_x//self.chn_per_word # 2
        fmap_per_iteration = self.image_size[0]*self.image_size[1]
        weights_per_filter = self.image_size[0]*self.image_size[1]
 
        if not self.bias_wr_done:
            target_chn = self.bias_chn
            target_str = "bias"
        elif not self.fmap_wr_done:
            target_chn = self.ifmap_chn
            target_str = 'ifmap'
        else:
            target_chn = self.weights_chn
            target_str = 'weights'

        if self.arch_input_chn.valid():
            if target_chn.vacancy():
                data = [e for e in self.arch_input_chn.pop()]
                print ("des to ", target_str, data)
                target_chn.push(data)
                self.raw_stats['dram_rd'] += len(data)
                if target_str == 'ifmap':
                    self.raw_stats['dram_to_glb_acc'] += len(data)
                    self.fmap_tile += 1
                if target_str == 'weights':
                    self.raw_stats['dram_to_pe_acc'] += len(data)
                    self.curr_filter += 1
                if target_str == 'bias':
                    self.raw_stats['dram_to_post_tr'] += len(data)
                    self.bias_idx+=1
                if self.bias_idx == 2:
                    self.bias_wr_done = True
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
                    self.weight_wr_done = True

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
    def instantiate(self, arch_output_chn, arr_x, arr_y, chn_per_word, finish_signal_chn):
        # PE static configuration (immutable)
        self.arr_x = arr_x
        self.arr_y = arr_y
        self.chn_per_word = chn_per_word

        self.arch_output_chn = arch_output_chn
        
        self.finish_signal_chn = finish_signal_chn

        self.ofmap = None
        self.ofmap_transformed = None
        self.reference = None

        self.image_size = (0, 0)

        self.curr_set = 0
        self.fmap_idx = 0
        
        self.pass_done = Reg(False)

    def configure(self, ofmap, reference, image_size, bias):
        self.ofmap = np.zeros((image_size[0], image_size[1], self.arr_x, 4)).astype(np.int64) # 4x4x8x4
        self.ofmap_transformed = np.zeros((image_size[0], image_size[1], self.arr_x)).astype(np.int64) # 4x4x8
        self.reference = reference
        self.num_tiles = 4
        self.curr_tile = 0

        self.image_size = image_size
        self.bias = bias # TODO

        self.curr_set = 0
        self.fmap_idx = 0
        self.curr_chn = 0
        self.A_T = np.array([ [1,1,1,0],[0,1,-1,-1] ])
        self.A = self.A_T.transpose()

        self.pass_done.wr(False)

    def tick(self):
        if self.pass_done.rd():
# partly parallelized to be on chip:
#            x_idx = (self.curr_tile // 2)*2
#            y_idx = (self.curr_tile % 2)*2
#            self.ofmap_transformed[x_idx:x_idx+2, y_idx:y_idx+2, self.curr_chn] += np.dot(self.A_T, np.dot(self.ofmap[:,:,self.curr_chn, self.curr_tile],self.A))
#            self.curr_tile += 1
#            if self.curr_tile == 4:
#                self.curr_tile = 0
#                self.ofmap_transformed[:,:,self.curr_chn] += self.bias[self.curr_chn] # add bias
#                self.curr_chn += 1
#            if self.curr_chn == 8:                
#                print ("reference shape: ", self.reference.shape)
#                print ("ofmap shape: ", self.ofmap.shape)

    # FOR LOOPS USED B/C NOT COUNTING OFF CHIP PROCESSING IN PERFORMANCE STATISTICS (will unroll loops in on chip processing)
            for k in range(8):
                self.ofmap_transformed[:,:,k] += self.bias[k] # add bias
                for t in range(self.num_tiles):
                    x_idx = (t // 2)*2
                    y_idx = (t % 2)*2
                    self.ofmap_transformed[x_idx:x_idx+2,y_idx:y_idx+2,k] += np.dot(self.A_T,np.dot(self.ofmap[:,:,k,t],self.A))
            self.finish_signal_chn.push(True)
            if np.all(self.ofmap_transformed == self.reference):
                raise Finish("Success")
            else:
                print ("ofmap: ")
                print(self.ofmap_transformed)
                print ("reference: ")
                print(self.reference)
                print ("difference: ")
                print(self.ofmap_transformed-self.reference)
                raise Finish("Validation Failed")
        
        else:
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
                    self.curr_tile = 0
                    self.ofmap = self.ofmap//(128*128)
                    self.pass_done.wr(True)

