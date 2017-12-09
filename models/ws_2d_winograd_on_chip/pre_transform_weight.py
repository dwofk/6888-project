import numpy as np

from nnsim.module import Module, HWError
from nnsim.reg import Reg
from nnsim.channel import Channel


class PreTransformWeights(Module):
    def instantiate(self, locx, locy, weight_in_chn, weight_out_chn): 
        self.locx = locx
        self.locy = locy
        self.weight_in_chn = weight_in_chn
        self.weight_out_chn = weight_out_chn
        self.transform_done = Reg(False)
        
        self.stat_type = 'aggregate'
        self.raw_stats = {'alu_comp' : 0, 'rf_rd' : 0, 'rf_wr' : 0}
        
    def configure(self):
        self.iteration = 0
        self.push_ctr = 0
        self.U = np.zeros([4,4]).astype(np.int64)
        self.transform_done.wr(False)
        
# Explanation of algorithm: transform filter weights G into U, performing Winograd transform U = H*G*H_T
#    G = [G00 G01 G02
#         G10 G11 G12
#         G20 G21 G22]
#
#    H = [1    0    0
#         0.5  0.5  0.5
#         0.5 -0.5  0.5
#         0    0    1  ]
#
#    H_T = [1  0.5  0.5  0
#           0  0.5 -0.5  0
#           0  0.5  0.5  1]
#
# Performing this transform yields a 4x4 output for a given 4x4 input:
#
#    U = [u00 u01 u02 u03
#         u10 u11 u12 u13
#         u20 u21 u22 u23
#         u30 u31 u32 u33]
#    ... such that:
#   u00 = (G00)<<7;
#   u01 = (G00 + G01 + G02)<<6;
#   u02 = (G00 - G01 + G02)<<6;
#   u03 = (G02)<<7;
#   u10 = (G00 + G10 + G20)<<6;
#   u11 = (G00 + G01 + G02 + G10 + G11 + G12 + G20 + G21 + G22)<<5;
#   u12 = (G00 - G01 + G02 + G10 - G11 + G12 + G20 - G21 + G22)<<5;
#   u13 = (G02 + G12 + G22)<<6;
#   u20 = (G00 - G10 + G20)<<6;
#   u21 = (G00 + G01 + G02 - G10 - G11 - G12 + G20 + G21 + G22)<<5;
#   u22 = (G00 - G01 + G02 - G10 + G11 - G12 + G20 - G21 + G22)<<5;
#   u23 = (G02 - G12 + G22)<<6;
#   u30 = (G20)<<7;
#   u31 = (G20 + G21 + G22)<<6;
#   u32 = (G20 - G21 + G22)<<6;
#   u33 = (G22)<<7;

    def tick(self):
        if self.transform_done.rd():
            return
        if self.weight_in_chn.valid() and self.weight_out_chn.vacancy():
            g = (self.weight_in_chn.pop())
            #print("pre tr weight: locx, locy, receive weight: ", self.locx, self.locy, g)
            if (self.iteration == 0):    # get G_00
                self.U[0][0] += g
                self.U[0][1] += g
                self.U[0][2] += g
                self.U[1][0] += g
                self.U[1][1] += g
                self.U[1][2] += g
                self.U[2][0] += g
                self.U[2][1] += g
                self.U[2][2] += g
                self.U[0][0] = self.U[0][0]*128 # left shift by 7
                self.raw_stats['alu_comp'] += 10 #9 adds, 1 shift
                self.raw_stats['rf_rd'] += 9
                self.raw_stats['rf_wr'] += 9
                self.weight_out_chn.push(self.U[self.push_ctr // 4][self.push_ctr % 4]) # send U00
                self.raw_stats['rf_wr'] -= 1 # u00 sent immediately, not written back to rf
                #print ("pre transform weights - locx, locy, iteration, transformed weight: ", \
                #       self.locx, self.locy, self.iteration, self.U[self.push_ctr // 4][self.push_ctr % 4])
                self.push_ctr += 1
                self.iteration += 1
            elif (self.iteration == 1):  # get G_01
                self.U[0][1] += g
                self.U[0][2] -= g
                self.U[1][1] += g
                self.U[1][2] -= g
                self.U[2][1] += g
                self.U[2][2] -= g
                self.raw_stats['alu_comp'] += 6 
                self.raw_stats['rf_rd'] += 6
                self.raw_stats['rf_wr'] += 6
                self.iteration += 1
            elif (self.iteration == 2):  # get G_02     
                self.U[0][1] += g
                self.U[0][2] += g
                self.U[0][3] += g
                self.U[1][1] += g
                self.U[1][2] += g
                self.U[1][3] += g
                self.U[2][1] += g
                self.U[2][2] += g
                self.U[2][3] += g
                self.U[0][1] = self.U[0][1]*64 # left shift by 6
                self.U[0][2] = self.U[0][2]*64 # left shift by 6
                self.U[0][3] = self.U[0][3]*128 # left shift by 7
                self.raw_stats['alu_comp'] += 12 #9 adds/subt, 3 shift
                self.raw_stats['rf_rd'] += 9
                self.raw_stats['rf_wr'] += 9
                self.weight_out_chn.push(self.U[self.push_ctr // 4][self.push_ctr % 4]) # send U01
                self.raw_stats['rf_wr'] -= 1 # u01 sent immediately, not written back to rf
                #print ("pre transform weights - locx, locy, iteration, transformed weight: ", \
                #       self.locx, self.locy, self.iteration, self.U[self.push_ctr // 4][self.push_ctr % 4])
                self.push_ctr += 1
                self.iteration += 1
            elif (self.iteration == 3):  # get G_10
                self.U[1][0] += g
                self.U[1][1] += g
                self.U[1][2] += g
                self.U[2][0] -= g
                self.U[2][1] -= g
                self.U[2][2] -= g
                self.raw_stats['alu_comp'] += 6 
                self.raw_stats['rf_rd'] += 6
                self.raw_stats['rf_wr'] += 6
                self.weight_out_chn.push(self.U[self.push_ctr // 4][self.push_ctr % 4]) # send U02
                self.raw_stats['rf_rd'] += 1 # read u02 from rf
                #print ("pre transform weights - locx, locy, iteration, transformed weight: ", \
                #       self.locx, self.locy, self.iteration, self.U[self.push_ctr // 4][self.push_ctr % 4])
                self.push_ctr += 1
                self.iteration += 1
            elif (self.iteration == 4):  # get G_11    
                self.U[1][1] += g
                self.U[1][2] -= g
                self.U[2][1] -= g
                self.U[2][2] += g
                self.raw_stats['alu_comp'] += 4
                self.raw_stats['rf_rd'] += 4
                self.raw_stats['rf_wr'] += 4
                self.weight_out_chn.push(self.U[self.push_ctr // 4][self.push_ctr % 4]) # send U03
                self.raw_stats['rf_rd'] += 1 # read u03 from rf
                #print ("pre transform weights - locx, locy, iteration, transformed weight: ", \
                #       self.locx, self.locy, self.iteration, self.U[self.push_ctr // 4][self.push_ctr % 4])
                self.push_ctr += 1
                self.iteration += 1
            elif (self.iteration == 5):  # get G_12     
                self.U[1][1] += g
                self.U[1][2] += g
                self.U[1][3] += g
                self.U[2][1] -= g
                self.U[2][2] -= g
                self.U[2][3] -= g
                self.raw_stats['alu_comp'] += 6 
                self.raw_stats['rf_rd'] += 6
                self.raw_stats['rf_wr'] += 6
                # no new completed weights this round
                self.iteration += 1
            elif (self.iteration == 6):  # get G_20
                self.U[1][0] += g
                self.U[1][1] += g
                self.U[1][2] += g
                self.U[2][0] += g
                self.U[2][1] += g
                self.U[2][2] += g
                self.U[3][0] += g
                self.U[3][1] += g
                self.U[3][2] += g
                self.U[1][0] = self.U[1][0]*64 # left shift 6
                self.U[2][0] = self.U[2][0]*64 # left shift 6
                self.U[3][0] = self.U[3][0]*128 # left shift 7
                self.raw_stats['alu_comp'] += 12 # 9 add, 3 shift ops 
                self.raw_stats['rf_rd'] += 9
                self.raw_stats['rf_wr'] += 9
                self.weight_out_chn.push(self.U[self.push_ctr // 4][self.push_ctr % 4]) # send U10
                self.raw_stats['rf_wr'] -= 1 # send u10 immediately, w/o writing to rf
                #print ("pre transform weights - locx, locy, iteration, transformed weight: ", \
                #       self.locx, self.locy, self.iteration, self.U[self.push_ctr // 4][self.push_ctr % 4])
                self.push_ctr += 1
                self.iteration += 1
            elif (self.iteration == 7):  # get G_21
                self.U[1][1] += g
                self.U[1][2] -= g
                self.U[2][1] += g
                self.U[2][2] -= g
                self.U[3][1] += g
                self.U[3][2] -= g
                self.raw_stats['alu_comp'] += 6 # 9 add, 3 shift ops 
                self.raw_stats['rf_rd'] += 6
                self.raw_stats['rf_wr'] += 6
                # no new completed weights this round
                self.iteration += 1
            elif (self.iteration == 8):  # get G_22
                self.U[1][1] += g
                self.U[1][2] += g
                self.U[1][3] += g
                self.U[2][1] += g
                self.U[2][2] += g
                self.U[2][3] += g
                self.U[3][1] += g
                self.U[3][2] += g
                self.U[3][3] += g
                self.U[1][1] = self.U[1][1]*32 # left shift by 5
                self.U[1][2] = self.U[1][2]*32 # left shift by 5
                self.U[1][3] = self.U[1][3]*64
                self.U[2][1] = self.U[2][1]*32
                self.U[2][2] = self.U[2][2]*32
                self.U[2][3] = self.U[2][3]*64
                self.U[3][1] = self.U[3][1]*64
                self.U[3][2] = self.U[3][2]*64
                self.U[3][3] = self.U[3][3]*128
                self.raw_stats['alu_comp'] += 18 # 9 add, 9 shift ops 
                self.raw_stats['rf_rd'] += 9
                self.raw_stats['rf_wr'] += 9
                self.weight_out_chn.push(self.U[self.push_ctr // 4][self.push_ctr % 4]) # send U11
                self.raw_stats['rf_wr'] -= 1 # send u11 immediately w/o writing to rf
                #print ("pre transform weights - locx, locy, iteration, transformed weight: ", \
                #       self.locx, self.locy, self.iteration, self.U[self.push_ctr // 4][self.push_ctr % 4])
                self.push_ctr += 1
                self.iteration += 1
        elif self.iteration == 9 and self.weight_out_chn.vacancy(): # finish pushing transformed weights
            self.weight_out_chn.push(self.U[self.push_ctr // 4][self.push_ctr % 4])
            self.raw_stats['rf_rd'] += 1 # read uXX from rf
            #print ("pre transform weights - locx, locy, iteration, transformed weight: ", \
            #       self.locx, self.locy, self.iteration, self.U[self.push_ctr // 4][self.push_ctr % 4])
            self.push_ctr += 1
            if self.push_ctr == 16: # all 16 transformed weight values have been pushed
                self.transform_done.wr(True)
