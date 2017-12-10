import numpy as np

from nnsim.module import Module, HWError
from nnsim.reg import Reg
from nnsim.channel import Channel


class PreTransformIFMap(Module):
    def instantiate(self, locx, locy, ifmap_in_chn, ifmap_out_chn):
        self.locx = locx
        self.locy = locy
        self.ifmap_in_chn = ifmap_in_chn
        self.ifmap_out_chn = ifmap_out_chn
        self.transform_done = Reg(False)

        self.stat_type = 'aggregate'
        self.raw_stats = {'pre_tr_ifmap_alu_comp' : 0, 'pre_tr_ifmap_rf_rd' : 0, 'pre_tr_ifmap_rf_wr' : 0}

    def configure(self):
        self.iteration = 0
        self.push_ctr = 0
        self.V = np.zeros([4,4]).astype(np.int64)
        self.raw_stats['pre_tr_ifmap_rf_wr'] += 16 # write zeros into rf
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
#
#    ... such that:
#    v00 = (D00 - D02 - D20 + D22);
#    v01 = (D01 + D02 - D21 - D22);
#    v02 = (D02 - D01 + D21 - D22);
#    v03 = (D01 - D03 - D21 + D23);
#    v10 = (D10 - D12 + D20 - D22);
#    v11 = (D11 + D12 + D21 + D22);
#    v12 = (D12 - D11 - D21 + D22);
#    v13 = (D11 - D13 + D21 - D23);
#    v20 = (D12 - D10 + D20 - D22);
#    v21 = (D21 - D12 - D11 + D22);
#    v22 = (D11 - D12 - D21 + D22);
#    v23 = (D13 - D11 + D21 - D23);
#    v30 = (D10 - D12 - D30 + D32);
#    v31 = (D11 + D12 - D31 - D32);
#    v32 = (D12 - D11 + D31 - D32);
#    v33 = (D11 - D13 - D31 + D33);

    def tick(self):
        if self.transform_done.rd():
            return
        if self.ifmap_in_chn.valid() and self.ifmap_out_chn.vacancy():
            d = (self.ifmap_in_chn.pop())
            #print ("pre transform ifmap pop - locx, locy, data: ",self.locx,self.locy,d)
            if (self.iteration == 0):    # get D_00
                self.V[0][0] += d
                self.raw_stats['pre_tr_ifmap_alu_comp'] += 1
                self.raw_stats['pre_tr_ifmap_rf_rd'] += 1
                self.raw_stats['pre_tr_ifmap_rf_wr'] += 1
                self.iteration += 1
            elif (self.iteration == 1):  # get D_01
                self.V[0][1] += d
                self.V[0][2] -= d
                self.V[0][3] += d
                self.raw_stats['pre_tr_ifmap_alu_comp'] += 3
                self.raw_stats['pre_tr_ifmap_rf_rd'] += 3
                self.raw_stats['pre_tr_ifmap_rf_wr'] += 3
                self.iteration += 1
            elif (self.iteration == 2):  # get D_02
                self.V[0][0] -= d
                self.V[0][1] += d
                self.V[0][2] += d
                self.raw_stats['pre_tr_ifmap_alu_comp'] += 3
                self.raw_stats['pre_tr_ifmap_rf_rd'] += 3
                self.raw_stats['pre_tr_ifmap_rf_wr'] += 3
                self.iteration += 1
            elif (self.iteration == 3):  # get D_03
                self.V[0][3] -= d
                self.raw_stats['pre_tr_ifmap_alu_comp'] += 1
                self.raw_stats['pre_tr_ifmap_rf_rd'] += 1
                self.raw_stats['pre_tr_ifmap_rf_wr'] += 1
                self.iteration += 1
            elif (self.iteration == 4):  # get D_10
                self.V[1][0] += d
                self.V[2][0] -= d
                self.V[3][0] += d
                self.raw_stats['pre_tr_ifmap_alu_comp'] += 3
                self.raw_stats['pre_tr_ifmap_rf_rd'] += 3
                self.raw_stats['pre_tr_ifmap_rf_wr'] += 3
                self.iteration += 1
            elif (self.iteration == 5):  # get D_11
                self.V[1][1] += d
                self.V[1][2] -= d
                self.V[1][3] += d
                self.V[2][1] -= d
                self.V[2][2] += d
                self.V[2][3] -= d
                self.V[3][1] += d
                self.V[3][2] -= d
                self.V[3][3] += d
                self.raw_stats['pre_tr_ifmap_alu_comp'] += 9
                self.raw_stats['pre_tr_ifmap_rf_rd'] += 9
                self.raw_stats['pre_tr_ifmap_rf_wr'] += 9
                self.iteration += 1
            elif (self.iteration == 6):  # get D_12
                self.V[1][0] -= d
                self.V[1][1] += d
                self.V[1][2] += d
                self.V[2][0] += d
                self.V[2][1] -= d
                self.V[2][2] -= d
                self.V[3][0] -= d
                self.V[3][1] += d
                self.V[3][2] += d
                self.raw_stats['pre_tr_ifmap_alu_comp'] += 9
                self.raw_stats['pre_tr_ifmap_rf_rd'] += 9
                self.raw_stats['pre_tr_ifmap_rf_wr'] += 9
                self.iteration += 1
            elif (self.iteration == 7):  # get D_13
                self.V[1][3] -= d
                self.V[2][3] += d
                self.V[3][3] -= d
                self.raw_stats['pre_tr_ifmap_alu_comp'] += 3
                self.raw_stats['pre_tr_ifmap_rf_rd'] += 3
                self.raw_stats['pre_tr_ifmap_rf_wr'] += 3
                self.iteration += 1
            elif (self.iteration == 8):  # get D_20
                self.V[0][0] -= d
                self.V[1][0] += d
                self.V[2][0] += d
                self.raw_stats['pre_tr_ifmap_alu_comp'] += 3
                self.raw_stats['pre_tr_ifmap_rf_rd'] += 3
                self.raw_stats['pre_tr_ifmap_rf_wr'] += 3
                self.iteration += 1
            elif (self.iteration == 9):  # get D_21
                self.V[0][1] -= d
                self.V[0][2] += d
                self.V[0][3] -= d
                self.V[1][1] += d
                self.V[1][2] -= d
                self.V[1][3] += d
                self.V[2][1] += d
                self.V[2][2] -= d
                self.V[2][3] += d
                self.raw_stats['pre_tr_ifmap_alu_comp'] += 9
                self.raw_stats['pre_tr_ifmap_rf_rd'] += 9
                self.raw_stats['pre_tr_ifmap_rf_wr'] += 9
                self.iteration += 1
            elif (self.iteration == 10): # get D_22 & start pushing transformed data out
                self.V[0][0] += d
                self.V[0][1] -= d
                self.V[0][2] -= d
                self.V[1][0] -= d
                self.V[1][1] += d
                self.V[1][2] += d
                self.V[2][0] -= d
                self.V[2][1] += d
                self.V[2][2] += d
                self.raw_stats['pre_tr_ifmap_alu_comp'] += 9
                self.raw_stats['pre_tr_ifmap_rf_rd'] += 9
                self.raw_stats['pre_tr_ifmap_rf_wr'] += 9
                self.ifmap_out_chn.push(self.V[self.push_ctr // 4][self.push_ctr % 4]) # push v00
                self.raw_stats['pre_tr_ifmap_rf_rd'] -= 1 # push v00 immediately w/o writing to rf
                #print ("pre transform ifmap - locx, locy, iteration, transformed ifmap: ", \
                #       self.locx, self.locy, self.iteration, self.V[self.push_ctr // 4][self.push_ctr % 4])
                self.push_ctr += 1
                self.iteration += 1
            elif (self.iteration == 11): # get D_23
                self.V[0][3] += d
                self.V[1][3] -= d
                self.V[2][3] -= d
                self.raw_stats['pre_tr_ifmap_alu_comp'] += 3
                self.raw_stats['pre_tr_ifmap_rf_rd'] += 3
                self.raw_stats['pre_tr_ifmap_rf_wr'] += 3
                self.ifmap_out_chn.push(self.V[self.push_ctr // 4][self.push_ctr % 4]) # push v01
                self.raw_stats['pre_tr_ifmap_rf_rd'] += 1 # read v01 from rf
                #print ("pre transform ifmap - locx, locy, iteration, transformed ifmap: ", \
                #       self.locx, self.locy, self.iteration, self.V[self.push_ctr // 4][self.push_ctr % 4])
                self.push_ctr += 1
                self.iteration += 1
            elif (self.iteration == 12): # get D_30
                self.V[3][0] -= d
                self.raw_stats['pre_tr_ifmap_alu_comp'] += 1
                self.raw_stats['pre_tr_ifmap_rf_rd'] += 1
                self.raw_stats['pre_tr_ifmap_rf_wr'] += 1
                self.ifmap_out_chn.push(self.V[self.push_ctr // 4][self.push_ctr % 4]) # push v02
                self.raw_stats['pre_tr_ifmap_rf_rd'] += 1 # read v02 from rf
                #print ("pre transform ifmap - locx, locy, iteration, transformed ifmap: ", \
                #       self.locx, self.locy, self.iteration, self.V[self.push_ctr // 4][self.push_ctr % 4])
                self.push_ctr += 1
                self.iteration += 1
            elif (self.iteration == 13): # get D_31
                self.V[3][1] -= d
                self.V[3][2] += d
                self.V[3][3] -= d
                self.raw_stats['pre_tr_ifmap_alu_comp'] += 3
                self.raw_stats['pre_tr_ifmap_rf_rd'] += 3
                self.raw_stats['pre_tr_ifmap_rf_wr'] += 3
                self.ifmap_out_chn.push(self.V[self.push_ctr // 4][self.push_ctr % 4]) # push v03
                self.raw_stats['pre_tr_ifmap_rf_rd'] += 1 # read v03 from rf
                #print ("pre transform ifmap - locx, locy, iteration, transformed ifmap: ", \
                #       self.locx, self.locy, self.iteration, self.V[self.push_ctr // 4][self.push_ctr % 4])
                self.push_ctr += 1
                self.iteration += 1
            elif (self.iteration == 14): # get D_32
                self.V[3][0] += d
                self.V[3][1] -= d
                self.V[3][2] -= d
                self.raw_stats['pre_tr_ifmap_alu_comp'] += 3
                self.raw_stats['pre_tr_ifmap_rf_rd'] += 3
                self.raw_stats['pre_tr_ifmap_rf_wr'] += 3
                self.ifmap_out_chn.push(self.V[self.push_ctr // 4][self.push_ctr % 4]) # push v10
                self.raw_stats['pre_tr_ifmap_rf_wr'] += 1 # read v10 from rf
                #print ("pre transform ifmap - locx, locy, iteration, transformed ifmap: ", \
                #       self.locx, self.locy, self.iteration, self.V[self.push_ctr // 4][self.push_ctr % 4])
                self.push_ctr += 1
                self.iteration += 1
            elif (self.iteration == 15): # get D_33
                self.V[3][3] += d
                self.raw_stats['pre_tr_ifmap_alu_comp'] += 1
                self.raw_stats['pre_tr_ifmap_rf_rd'] += 1
                self.raw_stats['pre_tr_ifmap_rf_wr'] += 1
                self.ifmap_out_chn.push(self.V[self.push_ctr // 4][self.push_ctr % 4]) # push v11
                self.raw_stats['pre_tr_ifmap_rf_wr'] += 1 # read v11 from rf
                #print ("pre transform ifmap - locx, locy, iteration, transformed ifmap: ", \
                #       self.locx, self.locy, self.iteration, self.V[self.push_ctr // 4][self.push_ctr % 4])
                self.push_ctr += 1
                self.iteration += 1
        elif self.iteration == 16 and self.ifmap_out_chn.vacancy(): # done computing transform, push remaining V's sequentially
            self.ifmap_out_chn.push(self.V[self.push_ctr // 4][self.push_ctr % 4])
            self.raw_stats['pre_tr_ifmap_rf_rd'] += 1 # read vXX from rf
                #print ("pre transform ifmap - locx, locy, iteration, transformed ifmap: ", \
                #       self.locx, self.locy, self.iteration, self.V[self.push_ctr // 4][self.push_ctr % 4])
            self.push_ctr += 1
            if self.push_ctr == 16: # all 16 transformed ifmap values have been pushed
                self.transform_done.wr(True)
