from nnsim.module import Module
from nnsim.channel import Channel
from .ws import WSArch
from .stimulus import Stimulus

class WSArchTB(Module):
    def instantiate(self):
        self.name = 'tb'
        self.image_size = (4, 4)
        self.filter_size = (3, 3)
        self.in_chn = 8
        self.out_chn = 16
        self.chn_per_word = 4

        self.arr_x = self.out_chn // 2
        self.arr_y = self.in_chn // 2

        self.input_chn = Channel()
        self.output_chn = Channel()
        self.psum_chn = Channel(128)
        self.curr_pass = 0
        self.tick_counter = 0

        ifmap_glb_depth = self.image_size[0]*self.image_size[1]* \
                (self.in_chn//2)//self.chn_per_word
        psum_glb_depth = self.image_size[0]*self.image_size[1]* \
                (self.out_chn//2)//self.chn_per_word

        self.stimulus = Stimulus(self.arr_x, self.arr_y, self.chn_per_word,
            self.input_chn, self.output_chn, self.psum_chn)
        self.dut = WSArch(self.arr_x, self.arr_y, self.input_chn,
                self.output_chn, self.chn_per_word, ifmap_glb_depth,
                psum_glb_depth)

        self.configuration_done = False

    def tick(self):
        # print ("current pass: ", self.curr_pass)
        self.tick_counter+=1
        if (self.curr_pass < 4):
            if (self.tick_counter == 353):
                self.tick_counter = 0
                self.curr_pass += 1
                self.configuration_done = False
            if not self.configuration_done:
                self.stimulus.configure(self.image_size, self.filter_size, self.in_chn, self.out_chn, self.curr_pass)
                self.dut.configure(self.image_size, self.filter_size, self.in_chn, self.out_chn)
                self.configuration_done = True


if __name__ == "__main__":
    from nnsim.simulator import run_tb
    ws_tb = WSArchTB()
    run_tb(ws_tb, verbose=False)
