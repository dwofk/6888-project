from nnsim.module import Module, HWError
from nnsim.reg import Reg
from nnsim.channel import Channel




class PostTransform(Module):
    def instantiate(self, bias_chn, ofmap_in_chn, ofmap_out_chn, locx, locy): #ofmap_in
        self.locx = locx
        self.locy = locy
        self.bias_chn = bias_chn
        self.ofmap_in_chn = ofmap_in_chn
        self.ofmap_out_chn = ofmap_out_chn
        
    def configure(self, locx, locy):
        self.iteration = 0
        self.y00 = 0
        self.y01 = 0
        self.y10 = 0
        self.y11 = 0

    def tick(self):
        if self.ofmap_in_chn.valid() and self.bias_chn.valid(): # and self.iteration < 16:
            bias = self.bias_chn.peek()
            self.ofmap_in_chn.pop()
            # TODO PERFORM MATH HERE
            self.iteration += 1
        if self.iteration == 16 and self.ofmap_out_chn.vacancy():
            self.ofmap_out_chn.push([self.y00,self.y01,self.y10,self.y11]) # TODO
            # done w/ all computations here, can make a done reg