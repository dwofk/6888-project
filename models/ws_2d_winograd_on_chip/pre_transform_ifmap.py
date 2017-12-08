from nnsim.module import Module, HWError
from nnsim.reg import Reg
from nnsim.channel import Channel


class PostTransform(Module):
    def instantiate(self, locx, locy, ifmap_in_chn, ifmap_out_chn): #ofmap_in
        self.locx = locx
        self.locy = locy
        self.ifmap_in_chn = ifmap_in_chn
        self.ifmap_out_chn = ifmap_out_chn
        self.transform_done = Reg(False)
        
    def configure(self):
        self.iteration = 0
        self.v00 = 0
        self.v01 = 0
        self.v02 = 0
        self.v03 = 0
        self.v10 = 0
        self.v11 = 0
        self.v12 = 0
        self.v13 = 0
        self.v20 = 0
        self.v21 = 0
        self.v22 = 0
        self.v23 = 0
        self.v30 = 0
        self.v31 = 0
        self.v32 = 0
        self.v33 = 0
        self.transform_done.wr(False)
        
# Explanation of algorithm: transform ifmap D into V, performing Winograd transform v = B_T*D*M
#    D = [D00 D01 D02 D03
#         D10 D11 D12 D13
#         D20 D21 D22 D23
#         D30 D31 D32 D33]
#
#    B_T = [1  0 -1  0
#           0  1  1  0
#           0 -1  1  0
#           0  1  0 -1]
#
#    B = [ 1   0  0  0
#          0   1 -1  1
#         -1   1  1  0
#          0   0  0 -1]
#
# Performing this transform yields a 4x4 output for a given 4x4 input:
#
#    V = [v00 v01 v02 v03
#         v10 v11 v12 v13
#         v20 v21 v22 v23
#         v30 v31 v32 v33]
#    ... such that:
#    v00 = (D00 - D02 - D20 + D22)>>7;
#    v01 = (D01 + D02 - D21 - D22)>>7;
#    v02 = (D02 - D01 + D21 - D22)>>7;
#    v03 = (D01 - D03 - D21 + D23)>>7;
#    v10 = (D10 - D12 + D20 - D22)>>7;
#    v11 = (D11 + D12 + D21 + D22)>>7;
#    v12 = (D12 - D11 - D21 + D22)>>7;
#    v13 = (D11 - D13 + D21 - D23)>>7;
#    v20 = (D12 - D10 + D20 - D22)>>7;
#    v21 = (D21 - D12 - D11 + D22)>>7;
#    v22 = (D11 - D12 - D21 + D22)>>7;
#    v23 = (D13 - D11 + D21 - D23)>>7;
#    v30 = (D10 - D12 - D30 + D32)>>7;
#    v31 = (D11 + D12 - D31 - D32)>>7;
#    v32 = (D12 - D11 + D31 - D32)>>7;
#    v33 = (D11 - D13 - D31 + D33)>>7;

    def tick(self):
        if self.transform_done.rd():
            return
        if self.ifmap_in_chn.valid() and self.ifmap_out_chn.vacancy():
            d = (self.dfmap_in_chn.pop())*128 # left shift by 7 bits # TODO: NECESSARY???
            print("post tr -- iteration ", self.iteration)
            if (self.iteration == 0):    # get D_00
                self.v00 += d
                self.iteration += 1
            elif (self.iteration == 1):  # get D_01
                self.v01 += d
                self.v02 -= d
                self.v03 += d
                self.iteration += 1
            elif (self.iteration == 2):  # get D_02     
                self.v00 -= d
                self.v01 += d
                self.v02 += d
                self.iteration += 1
            elif (self.iteration == 3):  # get D_03
                self.v03 -= d
                self.iteration += 1
            elif (self.iteration == 4):  # get D_10     
                self.v10 += d
                self.v20 -= d
                self.v30 += d
                self.iteration += 1
            elif (self.iteration == 5):  # get D_11     
                self.v11 += d
                self.v12 -= d
                self.v13 += d
                self.v21 -= d
                self.v22 += d
                self.v23 -= d
                self.v31 += d
                self.v32 -= d
                self.v33 += d
                self.iteration += 1
            elif (self.iteration == 6):  # get D_12
                self.v10 -= d
                self.v11 += d
                self.v12 += d
                self.v20 += d
                self.v21 -= d
                self.v22 -= d
                self.v30 -= d
                self.v31 += d
                self.v32 += d
                self.iteration += 1
            elif (self.iteration == 7):  # get D_13
                self.v13 -= d
                self.v23 += d
                self.v33 -= d
                self.iteration += 1
            elif (self.iteration == 8):  # get D_20
                self.v00 -= d
                self.v10 += d
                self.v20 += d
                self.iteration += 1
            elif (self.iteration == 9):  # get D_21     
                self.v01 -= d
                self.v02 += d
                self.v03 -= d
                self.v11 += d
                self.v22 -= d
                self.v13 += d
                self.v21 += d
                self.v22 -= d
                self.v23 += d
                self.iteration += 1
            elif (self.iteration == 10): # get D_22       
                self.v00 += d
                self.v01 -= d
                self.v02 -= d
                self.v10 -= d
                self.v11 += d
                self.v12 += d
                self.v20 -= d
                self.v21 += d
                self.v22 += d
                self.iteration += 1
                print("post tr pushing y00: ", self.y00, self.bias)
                self.ofmap_out_chn.push(self.y00) # y00 done
            elif (self.iteration == 11): # get D_23
                self.v03 += d
                self.v13 -= d
                self.v23 -= d
                self.iteration += 1
                print("post tr pushing y01: ", self.y01, self.bias)
                self.ofmap_out_chn.push(self.y01) # y01 done
            elif (self.iteration == 12): # get D_30     
                self.v30 -= d
                self.iteration += 1
            elif (self.iteration == 13): # get D_31
                self.v31 -= d
                self.v32 += d
                self.v33 -= d
                self.iteration += 1
            elif (self.iteration == 14): # get D_32     
                self.v30 += d
                self.v31 -= d
                self.v32 -= d
                self.iteration += 1
                print("post tr pushing y10: ", self.y10, self.bias)
                self.ofmap_out_chn.push(self.y10) # y10 done
            elif (self.iteration == 15): # get D_33
                self.v33 += d
                self.iteration += 1
                print("post tr pushing y11: ", self.y11, self.bias)
                self.ofmap_out_chn.push(self.y11) # y11 done
            #self.iteration += 1
        if self.iteration == 16:
            self.transform_done.wr(True)
