from nnsim.module import Module


class IFMapTiler(Module):

    # tiles a padded 4x4 array (essentially a 6x6 array) into four 4x4 tiles

    def instantiate(self, wr_chn, rd_chns, chn_per_word):
        self.wr_chn = wr_chn
        self.rd_chns = rd_chns
        self.chn_per_word = chn_per_word

        self.name = "ifmap_tiler"

    def configure(self, arr_x):
        self.tile_fmap_idx = [0, 0, 0, 0] # fmap idx for each of the four tiles
        # self.num_tile_elem = 16 # tiles are 4x4 -- contain 16 elems

        self.arr_x = arr_x

        self.curr_tile = 0
        self.popped_ifmap_idx = 0

        self.num_tiles = 4

        # list appropriate tile chns for each of the 16
        # nonzero elements in the padded 4x4 ifmap

        self.tile_chn_list = [[0],
                            [0, 1],
                            [0, 1],
                            [1],
                            [0, 2],
                            [0, 1, 2, 3],
                            [0, 1, 2, 3],
                            [1, 3],
                            [0, 2],
                            [0, 1, 2, 3],
                            [0, 1, 2, 3],
                            [1, 3],
                            [2],
                            [2, 3],
                            [2, 3],
                            [3]]


    def tick(self):

        #sending_zero_to_tile = [(self.curr_tile == 0) and ((self.tile_fmap_idx[0] < 4) or ((self.tile_fmap_idx[0] % 4) == 0)),
        #                        (self.curr_tile == 1) and ((self.tile_fmap_idx[1] < 4) or ((self.tile_fmap_idx[1] % 3) == 0)),
        #                        (self.curr_tile == 2) and ((self.tile_fmap_idx[2] > 11) or ((self.tile_fmap_idx[2] % 4) == 0)),
        #                        (self.curr_tile == 3) and ((self.tile_fmap_idx[3] > 11) or ((self.tile_fmap_idx[3] % 3) == 0))]

        will_pop_ifmap_value = True
        print ("tile fmap idx -- ", self.tile_fmap_idx)

        for tile in range(self.num_tiles):

            sending_zero_to_tile = [(tile == 0) and ((self.tile_fmap_idx[0] < 4) or ((self.tile_fmap_idx[0] > 0) and ((self.tile_fmap_idx[0] % 4) == 0))),
                                (tile == 1) and ((self.tile_fmap_idx[1] < 4) or ((self.tile_fmap_idx[1] > 0) and ((self.tile_fmap_idx[1] % 3) == 0))),
                                (tile == 2) and ((self.tile_fmap_idx[2] > 11) or ((self.tile_fmap_idx[2] >= 0) and ((self.tile_fmap_idx[2] % 4) == 0))),
                                (tile == 3) and ((self.tile_fmap_idx[3] > 11) or ((self.tile_fmap_idx[3] > 0) and ((self.tile_fmap_idx[3] % 3) == 0)))]

            will_pop_ifmap_value = will_pop_ifmap_value and (not sending_zero_to_tile[tile])
            if sending_zero_to_tile[tile]:
                # check vacancy, push to tile, increment tile's tile_fmap_idx
                vacancy = True
                for x in range(self.arr_x):
                    vacancy = vacancy and self.rd_chns[tile][x].vacancy()
                if vacancy:
                    for x in range(self.arr_x):
                        self.rd_chns[tile][x].push(0)
                    self.tile_fmap_idx[tile] = self.tile_fmap_idx[tile] + 1

        if will_pop_ifmap_value and self.wr_chn.valid():

            vacancy = True
            for tile_chn in self.tile_chn_list[self.popped_ifmap_idx]:
                for x in range(self.arr_x):
                    vacancy = vacancy and self.rd_chns[tile_chn][x].vacancy()

            if vacancy:
                data = self.wr_chn.pop()

                for tile_chn in self.tile_chn_list[self.popped_ifmap_idx]:
                    for x in range(self.arr_x):
                        self.rd_chns[tile_chn][x].push(data[x])
                    self.tile_fmap_idx[tile_chn] = self.tile_fmap_idx[tile_chn] + 1

                self.popped_ifmap_idx += 1
