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
        self.filter_sets = filter_sets
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
                data = self.rd_chn.pop()
                self.raw_stats['noc_multicast'] += len(data)
                # print "ifmap_to_pe", ymin, ymax, data
                for y in range(ymin, ymax):
                    for x in range(self.arr_x):
                        self.wr_chns[y][x].push(data[y-ymin])

                self.curr_set += 1
                if self.curr_set == self.ifmap_sets:
                    self.curr_set = 0

class PSumRdNoC(Module):
    def instantiate(self, rd_chn, wr_chns, chn_per_word):
        self.chn_per_word = chn_per_word
        self.name = 'psum_rd_noc'
        
        self.stat_type = 'show'
        self.raw_stats = {'noc_multicast' : 0}

        self.rd_chn = rd_chn
        self.wr_chns = wr_chns

        self.psum_sets = 0

        self.curr_set = 0

    def configure(self, psum_sets):
        self.psum_sets = psum_sets

        self.curr_set = 0

    def tick(self):
        # Feed psums to the PE array from the GLB
        if self.rd_chn.valid():
            # Dispatch ifmap read if space is available and not at edge
            xmin = self.curr_set*self.chn_per_word
            xmax = xmin + self.chn_per_word
            vacancy = True
            for x in range(xmin, xmax):
                vacancy = vacancy and self.wr_chns[x].vacancy()

            if vacancy:
                data = self.rd_chn.pop()
                self.raw_stats['noc_multicast'] += len(data)
                for x in range(xmin, xmax):
                    self.wr_chns[x].push(data[x-xmin])
                    print ("psum_to_pe: xmin, xmax, x, data: ", xmin, xmax, x, data)

                self.curr_set += 1
                if self.curr_set == self.psum_sets:
                    self.curr_set = 0

class PSumWrNoC(Module):
    def instantiate(self, rd_chns, glb_chn, output_chn, chn_per_word):
        self.chn_per_word = chn_per_word
        self.name = 'psum_wr_noc'
        
        self.stat_type = 'show'
        self.raw_stats = {'noc_multicast' : 0}

        self.rd_chns = rd_chns
        self.glb_chn = glb_chn
        self.output_chn = output_chn

        self.num_iteration = 0
        self.fmap_per_iteration = 0
        self.psum_sets = 0

        self.iteration = 0
        self.curr_set = 0
        self.psum_idx = 0

    def configure(self, num_iteration, fmap_per_iteration,
            psum_sets):
        self.num_iteration = num_iteration
        self.fmap_per_iteration = fmap_per_iteration
        self.psum_sets = psum_sets

        self.iteration = 0
        self.curr_set = 0
        self.psum_idx = 0

    def tick(self):
        # Check if psum available for write-back
        valid = True
        xmin = self.curr_set*self.chn_per_word
        xmax = xmin + self.chn_per_word
        for x in range(xmin, xmax):
            valid = valid and self.rd_chns[x].valid()

        if valid:
            target_chn = self.output_chn if self.iteration == \
                    self.num_iteration-1 else self.glb_chn
            if target_chn.vacancy():
                print ("psum_to_glb: iteration, psum_idx, xmin, xmax: ", self.iteration, self.psum_idx, xmin, xmax)
                data = [ self.rd_chns[x].pop() for x in range(xmin, xmax) ]
                target_chn.push(data)
                self.raw_stats['noc_multicast'] += len(data)

                self.curr_set += 1
                if self.curr_set == self.psum_sets:
                    self.curr_set = 0
                    self.psum_idx += 1
                if self.psum_idx == self.fmap_per_iteration:
                    self.psum_idx = 0
                    # print "---- Finished psum iteration: %d ----" % self.iteration
                    # self.glb.dump()
                    self.iteration += 1
