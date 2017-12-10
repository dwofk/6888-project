from nnsim.module import Module

class WeightsNoC(Module):
    def instantiate(self, rd_chn, wr_chns, chn_per_word):
        self.chn_per_word = chn_per_word
        self.name = 'weight_noc'
        
        self.stat_type = 'show'
        self.raw_stats = {'noc_multicast' : 0}

        self.rd_chn = rd_chn
        self.wr_chns = wr_chns

        self.filter_sets = 0
        self.out_chn = 0

        self.curr_set = 0
        self.curr_filter = 0

    def configure(self, filter_sets, out_chn):
        self.filter_sets = filter_sets # this is 1
        self.out_chn = out_chn

        self.curr_set = 0
        self.curr_filter = 0

    def tick(self):
        # Dispatch filters to PE columns. (PE is responsible for pop)
        if self.rd_chn.valid():
            vacancy = True
            ymin = self.curr_set*self.chn_per_word
            ymax = ymin + self.chn_per_word
            for y in range(ymin, ymax):
                vacancy = vacancy and self.wr_chns[y][self.curr_filter].vacancy()
            if vacancy:
                data = self.rd_chn.pop()
                self.raw_stats['noc_multicast'] += len(data)
                # print "filter_to_pe: ", self.curr_filter, data
                for y in range(ymin, ymax):
                    self.wr_chns[y][self.curr_filter].push(data[y])

                self.curr_set += 1
                if self.curr_set == self.filter_sets: 
                    self.curr_set = 0
                    self.curr_filter += 1
                if self.curr_filter == self.out_chn:
                    self.curr_filter = 0

class IFMapNoC(Module):
    def instantiate(self, rd_chn, wr_chns, arr_x, chn_per_word):
        self.arr_x = arr_x
        self.chn_per_word = chn_per_word
        self.name = 'ifmap_noc'
        
        self.stat_type = 'show'
        self.raw_stats = {'noc_multicast' : 0}

        self.rd_chn = rd_chn
        self.wr_chns = wr_chns

        self.ifmap_sets = 0

        self.curr_set = 0
        self.curr_filter = 0

    def configure(self, ifmap_sets):
        self.ifmap_sets = ifmap_sets

        self.curr_set = 0
        self.curr_filter = 0

    def tick(self):
        print ("ifmap noc valid signal: ",self.rd_chn.valid())
        # Feed inputs to the PE array from the GLB
        if self.rd_chn.valid():
            # Dispatch ifmap read if space is available and not at edge
            ymin = self.curr_set*self.chn_per_word
            ymax = ymin + self.chn_per_word
            vacancy = True
            for y in range(ymin, ymax):
                for x in range(self.arr_x):
                    vacancy = vacancy and self.wr_chns[y][x].vacancy()

            if vacancy:
                print ("ifmap noc sends data to PEs")
                data = self.rd_chn.pop()
                self.raw_stats['noc_multicast'] += len(data)
                # print "ifmap_to_pe", ymin, ymax, data
                for y in range(ymin, ymax):
                    for x in range(self.arr_x):
                        self.wr_chns[y][x].push(data[y-ymin])

                self.curr_set += 1
                if self.curr_set == self.ifmap_sets:
                    self.curr_set = 0
                    
class BiasNoC(Module):
    def instantiate(self, rd_chn, wr_chns, chn_per_word):
        self.chn_per_word = chn_per_word
        self.name = 'bias_noc'
        
        self.stat_type = 'show'
        self.raw_stats = {'noc_multicast' : 0}

        self.rd_chn = rd_chn
        self.wr_chns = wr_chns
        
    def configure(self, arr_x, arr_y):
        self.arr_x = arr_x
        self.arr_y = arr_y
        
        self.bias_sets = self.arr_x // self.chn_per_word
        self.curr_set = 0

    def tick(self):
        # Feed biases to the PostTransform array from the Bias GLB
        
        if self.rd_chn.valid():
        
            xmin = self.curr_set*self.chn_per_word
            xmax = xmin + self.chn_per_word
        
            vacancy = True
            for x in range(xmin, xmax):
                for y in range(self.arr_y):
                    vacancy = vacancy and self.wr_chns[y][x].vacancy()

            if vacancy:
                data = self.rd_chn.pop()
                self.raw_stats['noc_multicast'] += len(data)
                for x in range(xmin, xmax):
                    for y in range(self.arr_y):
                        self.wr_chns[y][x].push(data[x-xmin])
                        print ("bias_to_post_tr: x, data: ", x, 0)
                        
                self.curr_set += 1
                if self.curr_set == self.bias_sets:
                    self.curr_set = 0

class PostTrWrNoC(Module):
    def instantiate(self, rd_chns, wr_chns, chn_per_word):
        self.chn_per_word = chn_per_word
        self.name = 'post_tr_wr_noc'
        
        self.stat_type = 'show'
        self.raw_stats = {'noc_multicast' : 0}

        self.rd_chns = rd_chns
        self.wr_chns = wr_chns

    def configure(self, arr_x, arr_y):
        self.arr_x = arr_x
        self.arr_y = arr_y
        
        self.num_tiles = 4
        self.curr_tile = 0
        
        self.iteration = 0
        self.num_iterations = 16 # 4x4 ofmap in

    def tick(self):
        
        valid = True
        for x in range(self.arr_x):
            valid = valid and self.rd_chns[x].valid()
            #print("post tr wr noc -- rd chan %d valid" % x)

        if valid:
            
            vacancy = True
            for x in range(self.arr_x):
                    vacancy = vacancy and self.wr_chns[self.curr_tile][x].vacancy()
            
            if vacancy:
                
                for x in range(self.arr_x):
                    data = self.rd_chns[x].pop()
                    self.raw_stats['noc_multicast'] += 1
                    self.wr_chns[self.curr_tile][x].push(data)
                    #print("post tr wr noc -- pop from rd_chn %d, push to wr_chn %d %d", x, self.curr_tile, x)
                    #self.raw_stats['noc_multicast'] += len(data)

                self.curr_tile += 1
                if self.curr_tile == self.num_tiles:
                    self.curr_tile = 0
                    self.iteration += 1
                if self.iteration == self.num_iterations:
                    self.iteration = 0
                    
class PostTrRdNoC(Module):
    def instantiate(self, rd_chns, output_chn, chn_per_word):
        self.chn_per_word = chn_per_word
        self.name = 'post_tr_rd_noc'
        
        self.stat_type = 'show'
        self.raw_stats = {'noc_multicast' : 0}

        self.rd_chns = rd_chns
        self.output_chn = output_chn

    def configure(self):
        
        self.num_iterations = 4
        
        self.ofmap_sets = 2
        self.num_tiles = 4

        self.iteration = 0
        self.curr_set = 0
        self.curr_tile = 0

    def tick(self):
        # Check if psum available for write-back
        valid = True
        xmin = self.curr_set*self.chn_per_word
        xmax = xmin + self.chn_per_word
        for x in range(xmin, xmax):
            valid = valid and self.rd_chns[self.curr_tile][x].valid()

        if valid:
            target_chn = self.output_chn
            
            if target_chn.vacancy():
                data = [ self.rd_chns[self.curr_tile][x].pop() for x in range(xmin, xmax) ]
                #print("post tr rd noc -- pushing from rd_chn ", self.curr_tile, data)
                target_chn.push(data)
                self.raw_stats['noc_multicast'] += len(data)

                self.curr_set += 1
                if self.curr_set == self.ofmap_sets:
                    self.curr_set = 0
                    self.curr_tile += 1
                if self.curr_tile == self.num_tiles:
                    self.curr_tile = 0
                    self.iteration += 1
                if self.iteration == self.num_iterations:
                    self.iteration = 0

class PSumRdNoC(Module):
    def instantiate(self, wr_chns, chn_per_word):
        self.chn_per_word = chn_per_word
        self.name = 'psum_rd_noc'
        
        #self.stat_type = 'show'
        #self.raw_stats = {'noc_multicast' : 0}

        #self.rd_chn = rd_chn
        self.wr_chns = wr_chns

        #self.psum_sets = 0
        #self.curr_set = 0
        
    def configure(self, arr_x):
        self.arr_x = arr_x


    def tick(self):
        # Feed psums to the PE array from the GLB
        #if self.rd_chn.valid():
        
        # Dispatch ZERO if space is available and not at edge
        #xmin = self.curr_set*self.chn_per_word
        #xmax = xmin + self.chn_per_word
        vacancy = True
        for x in range(self.arr_x):
            vacancy = vacancy and self.wr_chns[x].vacancy()

        if vacancy:
            #self.raw_stats['noc_multicast'] += len(data)
            for x in range(self.arr_x):
                self.wr_chns[x].push(0)
                #print ("psum_to_pe: x, data: ", x, 0)

class PSumWrNoC(Module):
    def instantiate(self, rd_chns, output_chn, chn_per_word):
        self.chn_per_word = chn_per_word
        self.name = 'psum_wr_noc'
        
        self.stat_type = 'show'
        self.raw_stats = {'noc_multicast' : 0}

        self.rd_chns = rd_chns
        self.output_chn = output_chn

        #self.num_iteration = 0
        #self.fmap_per_iteration = 0
        #self.psum_sets = 0

        #self.iteration = 0
        #self.curr_set = 0
        #self.psum_idx = 0

    def configure(self, num_iteration, fmap_per_iteration,
            psum_sets):
        self.num_iteration = num_iteration
        #self.fmap_per_iteration = fmap_per_iteration
        self.psum_sets = psum_sets
        self.num_tiles = 4

        self.iteration = 0
        self.curr_set = 0
        self.tile_idx = 0

    def tick(self):
        # Check if psum available for write-back
        valid = True
        xmin = self.curr_set*self.chn_per_word
        xmax = xmin + self.chn_per_word
        for x in range(xmin, xmax):
            valid = valid and self.rd_chns[x].valid()

        if valid:
            target_chn = self.output_chn
            #print ("noc has valid psum data")
            
            if target_chn.vacancy():
                #print ("psum_to_glb: iteration, psum_idx, xmin, xmax: ", self.iteration, self.tile_idx, xmin, xmax)
                data = [ self.rd_chns[x].pop() for x in range(xmin, xmax) ]
                target_chn.push(data)
                self.raw_stats['noc_multicast'] += len(data)

                self.curr_set += 1
                if self.curr_set == self.psum_sets:
                    self.curr_set = 0
                    self.tile_idx += 1
                if self.tile_idx == self.num_tiles:
                    self.tile_idx = 0
                    # print "---- Finished psum iteration: %d ----" % self.iteration
                    # self.glb.dump()
                    self.iteration += 1
