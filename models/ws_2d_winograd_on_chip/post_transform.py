from nnsim.module import Module, HWError
from nnsim.reg import Reg
from nnsim.channel import Channel


class PostTransform(Module):
    def instantiate(self, locx, locy, bias_chn, ofmap_in_chn, ofmap_out_chn): #ofmap_in
        self.locx = locx
        self.locy = locy
        self.bias_chn = bias_chn
        self.ofmap_in_chn = ofmap_in_chn
        self.ofmap_out_chn = ofmap_out_chn
        self.transform_done = Reg(False)

        self.stat_type = 'aggregate'
        self.raw_stats = {'post_tr_alu_comp' : 0, 'post_tr_rf_rd' : 0, 'post_tr_rf_wr' : 0}

    def configure(self):
        self.bias = 0
        self.iteration = 0
        self.y00 = None
        self.y01 = None
        self.y10 = None
        self.y11 = None
        self.transform_done.wr(False)
        self.bias_read = False

# Explanation of algorithm: transform ofmap M into y, performing inverse Winograd transform y = A_T*M*A
#    M = [M00 M01 M02 M03
#         M10 M11 M12 M13
#         M20 M21 M22 M23
#         M30 M31 M32 M33]
#
#    A_T = [1  1  1  0
#           0  1 -1 -1]
#
#    A = [1  0
#         1  1
#         1 -1
#         0 -1]
#
# Performing this transform yields a 2x2 output for a given 4x4 input:
#
#    y = [y00 y01
#         y10 y11]
#    ... such that:
#    y00 = M00+M01+M02+M10+M11+M12+M20+M21+M22
#    y01 = M01-M02-M03+M11-M12-M13+M21-M22-M23
#    y10 = M10+M11+M12-M20-M21-M22-M30-M31-M32
#    y11 = M11-M12-M13-M21+M22+M23-M31+M32+M33

    def tick(self):
        if self.transform_done.rd():
            return
        if self.bias_chn.valid(): # should only ever be valid once
            self.bias = self.bias_chn.pop()
            self.bias_read = True
            self.y00 = self.bias
            self.y01 = self.bias
            self.y10 = self.bias
            self.y11 = self.bias
            self.raw_stats['post_tr_alu_comp'] += 4
            self.raw_stats['post_tr_rf_wr'] += 4
        elif self.ofmap_in_chn.valid() and self.ofmap_out_chn.vacancy():
            m = (self.ofmap_in_chn.pop())//(128) # right shift by 7 bits
            self.raw_stats['post_tr_alu_comp'] += 1
            #print("post tr -- iteration ", self.iteration)
            if (self.iteration == 0):    # get M_00
                self.y00 += m
                self.raw_stats['post_tr_alu_comp'] += 1
                self.raw_stats['post_tr_rf_rd'] += 1
                self.raw_stats['post_tr_rf_wr'] += 1
                self.iteration += 1
            elif (self.iteration == 1):  # get M_01
                self.y00 += m
                self.y01 += m
                self.raw_stats['post_tr_alu_comp'] += 2
                self.raw_stats['post_tr_rf_rd'] += 2
                self.raw_stats['post_tr_rf_wr'] += 2
                self.iteration += 1
            elif (self.iteration == 2):  # get M_02
                self.y00 += m
                self.y01 -= m
                self.raw_stats['post_tr_alu_comp'] += 2
                self.raw_stats['post_tr_rf_rd'] += 2
                self.raw_stats['post_tr_rf_wr'] += 2
                self.iteration += 1
            elif (self.iteration == 3):  # get M_03
                self.y01 -= m
                self.raw_stats['post_tr_alu_comp'] += 1
                self.raw_stats['post_tr_rf_rd'] += 1
                self.raw_stats['post_tr_rf_wr'] += 1
                self.iteration += 1
            elif (self.iteration == 4):  # get M_10
                self.y00 += m
                self.y10 += m
                self.raw_stats['post_tr_alu_comp'] += 2
                self.raw_stats['post_tr_rf_rd'] += 2
                self.raw_stats['post_tr_rf_wr'] += 2
                self.iteration += 1
            elif (self.iteration == 5):  # get M_11
                self.y00 += m
                self.y01 += m
                self.y10 += m
                self.y11 += m
                self.raw_stats['post_tr_alu_comp'] += 4
                self.raw_stats['post_tr_rf_rd'] += 4
                self.raw_stats['post_tr_rf_wr'] += 4
                self.iteration += 1
            elif (self.iteration == 6):  # get M_12
                self.y00 += m
                self.y01 -= m
                self.y10 += m
                self.y11 -= m
                self.raw_stats['post_tr_alu_comp'] += 4
                self.raw_stats['post_tr_rf_rd'] += 4
                self.raw_stats['post_tr_rf_wr'] += 4
                self.iteration += 1
            elif (self.iteration == 7):  # get M_13
                self.y01 -= m
                self.y11 -= m
                self.raw_stats['post_tr_alu_comp'] += 2
                self.raw_stats['post_tr_rf_rd'] += 2
                self.raw_stats['post_tr_rf_wr'] += 2
                self.iteration += 1
            elif (self.iteration == 8):  # get M_20
                self.y00 += m
                self.y10 -= m
                self.raw_stats['post_tr_alu_comp'] += 2
                self.raw_stats['post_tr_rf_rd'] += 2
                self.raw_stats['post_tr_rf_wr'] += 2
                self.iteration += 1
            elif (self.iteration == 9):  # get M_21
                self.y00 += m
                self.y01 += m
                self.y10 -= m
                self.y11 -= m
                self.raw_stats['post_tr_alu_comp'] += 4
                self.raw_stats['post_tr_rf_rd'] += 4
                self.raw_stats['post_tr_rf_wr'] += 4
                self.iteration += 1
            elif (self.iteration == 10 and self.bias_read == True): # get M_22
                self.y00 += m
                self.y01 -= m
                self.y10 -= m
                self.y11 += m
                self.raw_stats['post_tr_alu_comp'] += 4
                self.raw_stats['post_tr_rf_rd'] += 4
                self.raw_stats['post_tr_rf_wr'] += 4
                self.iteration += 1
                #print("post tr pushing y00: ", self.y00, self.bias)
                self.ofmap_out_chn.push(self.y00) # y00 done
                self.raw_stats['post_tr_rf_wr'] -= 1 # send y00 immediately w/o writing to rf
            elif (self.iteration == 11): # get M_23
                self.y01 -= m
                self.y11 += m
                self.raw_stats['post_tr_alu_comp'] += 2
                self.raw_stats['post_tr_rf_rd'] += 2
                self.raw_stats['post_tr_rf_wr'] += 2
                self.iteration += 1
                #print("post tr pushing y01: ", self.y01, self.bias)
                self.ofmap_out_chn.push(self.y01) # y01 done
                self.raw_stats['post_tr_rf_wr'] -= 1 # send y01 immediately w/o writing to rf
            elif (self.iteration == 12): # get M_30
                self.y10 -= m
                self.raw_stats['post_tr_alu_comp'] += 1
                self.raw_stats['post_tr_rf_rd'] += 1
                self.raw_stats['post_tr_rf_wr'] += 1
                self.iteration += 1
            elif (self.iteration == 13): # get M_31
                self.y10 -= m
                self.y11 -= m
                self.raw_stats['post_tr_alu_comp'] += 2
                self.raw_stats['post_tr_rf_rd'] += 2
                self.raw_stats['post_tr_rf_wr'] += 2
                self.iteration += 1
            elif (self.iteration == 14): # get M_32
                self.y10 -= m
                self.y11 += m
                self.raw_stats['post_tr_alu_comp'] += 2
                self.raw_stats['post_tr_rf_rd'] += 2
                self.raw_stats['post_tr_rf_wr'] += 2
                self.iteration += 1
                #print("post tr pushing y10: ", self.y10, self.bias)
                self.ofmap_out_chn.push(self.y10) # y10 done
                self.raw_stats['post_tr_rf_wr'] -= 1 # send y10 immediately w/o writing to rf
            elif (self.iteration == 15): # get M_33
                self.y11 += m
                self.raw_stats['post_tr_alu_comp'] += 1
                self.raw_stats['post_tr_rf_rd'] += 1
                self.raw_stats['post_tr_rf_wr'] += 1
                self.iteration += 1
                #print("post tr pushing y11: ", self.y11, self.bias)
                self.ofmap_out_chn.push(self.y11) # y11 done
                self.raw_stats['post_tr_rf_wr'] -= 1 # send y11 immediately w/o writing to rf
            #self.iteration += 1
        if self.iteration == 16:
            self.transform_done.wr(True)
