from scipy.signal import correlate2d
import numpy as np

from nnsim.module import Module
from .serdes import InputSerializer, OutputDeserializer

def conv(x, W, b):
    print (x.shape, W.shape, b.shape)
    y = np.zeros([x.shape[0], x.shape[1], W.shape[3]]).astype(np.int64)
    for out_channel in range(W.shape[3]):
        for in_channel in range(W.shape[2]):
            W_c = W[:, :, in_channel, out_channel]
            x_c = x[:, :, in_channel]
            y[:, :, out_channel] += correlate2d(x_c, W_c, mode="same")
        y[:, :, out_channel] += b[out_channel]
    return y

def winograd_tile(x, W, b):
    print(x.shape, W.shape, b.shape)
    x = x.astype(np.float64)
    W = W.astype(np.float64)
    b = b.astype(np.float64)
    y = np.zeros([x.shape[0]-W.shape[0]+1, x.shape[1]-W.shape[1]+1, W.shape[3]]).astype(np.float64)
    for k in range(W.shape[3]):
        y[:, :, k] += b[k] # apply biases
        
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
    
    # Perform Winograd transforms
    K = W.shape[3]
    C = W.shape[2]
    U = np.zeros([4,4,C,K]) # 4,4,4,8
    V = np.zeros([4,4,C]) # 4,4,4
    M = np.zeros([4,4,K])
    for k in range(K): # filter
        for c in range(C): # channel
            g = W[:, :, c, k]# 3x3 filter
            U[:,:,c,k] = np.dot(G,np.dot(g,G_T)) # 4x4
    for c in range(C): # channel
        d = x[:,:,c] # 4x4 ifmap tile
        V[:,:,c] = np.dot(B_T,np.dot(d,B)) 
    # Convert to integers for on chip processing, LOSE ACCURACY
    U = 128*U; # left shift by 7 bits to avoid precision loss when convert float to int
    V = 128*V;
    U = U.astype(np.int64)
    V = V.astype(np.int64)
            
    # Perform element wise matrix multiplication w/ summation over input channels
    for k in range(K):
        for c in range(C): # sum over input channels C
            M[:,:,k] += np.multiply(U[:,:,c,k],V[:,:,c])
    print ("M type? :", M)
    M = M//(128*128) # right shift by 14 bits to "undo" bit shifts in preprocessing
    
                
    # Revert Winograd transforms
    for k in range(K):
        y[:,:,k] += np.dot(A_T,np.dot(M[:,:,k],A))
    return [y.astype(np.int64),U,V,M]

def conv_winograd(x_nopadding,W,b): # x: 4x4x4, W: 3x3x4x8, b: 8x1: 
    K = W.shape[3]
    C = W.shape[2]
    tiles = 4
    U = np.zeros([4,4,C,K]).astype(np.int64) # 4,4,4,8
    V = np.zeros([4,4,C,tiles]).astype(np.int64) # 4,4,4,4 ... ifmaps are tiled
    M = np.zeros([4,4,8,tiles]).astype(np.int64)
    x = np.pad(x_nopadding,1,'constant') # x padded: 6x6x4
    x = x[:,:,1:5] # remove accidental padding that added extra channels
    y = np.zeros([x.shape[0]-W.shape[0]+1, x.shape[1]-W.shape[1]+1, W.shape[3]]).astype(np.int64)# y: 4x4x8
    print ("x original: ", x_nopadding)
    print ("x padded:", x)
    print ("x padded shape:", x.shape)
    for i in range(2):
        for j in range(2):
            [y[2*i:2*i+2,2*j:2*j+2,:],u,v,m] = winograd_tile(x[2*i:2*i+4,2*j:2*j+4,:],W,b)
            #print ("U:",u)
            #print ("V:",v)
            U = u
            V[:,:,:,2*i+j] = v
            M[:,:,:,2*i+j] = m
    print ("U stimulus: ", U)
    print ("V stimulus: ", V)
    return y,U,V,M


class Stimulus(Module):
    def instantiate(self, arr_x, arr_y, chn_per_word, input_chn, output_chn, finish_signal_chn):
        # PE static configuration (immutable)
        self.arr_x = arr_x
        self.arr_y = arr_y
        self.chn_per_word = chn_per_word

        self.input_chn = input_chn
        self.output_chn = output_chn
        
        self.finish_signal_chn = finish_signal_chn

        self.serializer = InputSerializer(self.input_chn, self.arr_x,
            self.arr_y, self.chn_per_word)
        self.deserializer = OutputDeserializer(self.output_chn, self.arr_x,
            self.arr_y, self.chn_per_word, self.finish_signal_chn)

    def configure(self, image_size, filter_size, in_chn, out_chn):
        # Test data
        np.random.seed(0)
        #ifmap = np.zeros((image_size[0], image_size[1],
         #   in_chn)).astype(np.int64)
        ifmap = np.random.normal(0, 10, (image_size[0], image_size[1],
             in_chn)).astype(np.int64)
        weights = np.random.normal(0, 10, (filter_size[0], filter_size[1], in_chn,
            out_chn)).astype(np.int64)
        bias = np.random.normal(0, 10, out_chn).astype(np.int64)
        ofmap = np.zeros((image_size[0], image_size[1],
            out_chn)).astype(np.int64)

        # Reference Output
        reference = conv(ifmap, weights, bias)
        reference_winograd, weights_winograd, ifmaps_winograd, ofmap_winograd = conv_winograd(ifmap, weights, bias)
        print ("ofmap winograd ref: ", ofmap_winograd)
        
        print ("reference: ", reference)
        print ("reference winograd: ", reference_winograd)
        print ("ifmaps winograd: ", ifmaps_winograd)
        print ("weights winograd: ", weights_winograd)

        self.serializer.configure(ifmap, weights, image_size, filter_size)
        #self.serializer.configure(ifmaps_winograd, weights_winograd, image_size, filter_size)
        self.deserializer.configure(ofmap, reference_winograd, image_size, bias)
        #self.deserializer.configure(ofmap, ofmap_winograd.astype(np.int64), image_size, bias)
        
        #self.serializer.configure(ifmap, weights, bias, image_size, filter_size)
        #self.deserializer.configure(ofmap, reference_winograd, image_size)
