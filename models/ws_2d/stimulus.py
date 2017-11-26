from scipy.signal import correlate2d
import numpy as np

from nnsim.module import Module
from .serdes import InputSerializer, OutputDeserializer

def conv(x, W, b):
    print(x.shape, W.shape, b.shape)
    y = np.zeros([x.shape[0]-W.shape[0]+1, x.shape[1]-W.shape[1]+1, W.shape[3]]).astype(np.int64)
    for out_channel in range(W.shape[3]):
        for in_channel in range(W.shape[2]):
            W_c = W[:, :, in_channel, out_channel]
            x_c = x[:, :, in_channel]
            y[:, :, out_channel] += correlate2d(x_c, W_c, mode="valid")
        y[:, :, out_channel] += b[out_channel]
    return y

def conv_same_padding(x, W, b):
    print(x.shape, W.shape, b.shape)
    y = np.zeros([x.shape[0], x.shape[1], W.shape[3]]).astype(np.int64)
    for out_channel in range(W.shape[3]):
        for in_channel in range(W.shape[2]):
            W_c = W[:, :, in_channel, out_channel]
            x_c = x[:, :, in_channel]
            y[:, :, out_channel] += correlate2d(x_c, W_c, mode="same")
        y[:, :, out_channel] += b[out_channel]
    return y

def conv_winograd(x, W, b):
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
    P = 1 # TODO start with 1 tile for now
    U = np.zeros([4,4,C,K]) # 4,4,4,8
    V = np.zeros([4,4,C,P]) # 4,4,4,1
    M = np.zeros([4,4,K,P])
    for k in range(K): # filter
        for c in range(C): # channel
            g = W[:, :, c, k]# 3x3 filter
            U[:,:,c,k] = np.dot(G,np.dot(g,G_T)) # 4x4
    for p in range(P): # input tile
        for c in range(C): # channel
            d = x[:,:,c] # 4x4 ifmap tile
            V[:,:,c,p] = np.dot(B_T,np.dot(d,B)) 
            
    # Perform element wise matrix multiplication w/ summation over input channels
    for p in range(P):
        for k in range(K):
            for c in range(C): # sum over input channels C
                M[:,:,k,p] += np.multiply(U[:,:,c,k],V[:,:,c,p])
                
    # Revert Winograd transforms
    for k in range(K):
        for p in range(P):
            y[:,:,k] += np.dot(A_T,np.dot(M[:,:,k,p],A))
    return y.astype(np.int64)

class Stimulus(Module):
    def instantiate(self, arr_x, arr_y, chn_per_word, input_chn, output_chn):
        # PE static configuration (immutable)
        self.arr_x = arr_x
        self.arr_y = arr_y
        self.chn_per_word = chn_per_word

        self.input_chn = input_chn
        self.output_chn = output_chn

        self.serializer = InputSerializer(self.input_chn, self.arr_x,
            self.arr_y, self.chn_per_word)
        self.deserializer = OutputDeserializer(self.output_chn, self.arr_x,
            self.arr_y, self.chn_per_word)

    def configure(self, image_size, filter_size, in_chn, out_chn):
        # Test data
        #ifmap = np.zeros((image_size[0], image_size[1],
        #    in_chn)).astype(np.int64)
        np.random.seed(0)
        ifmap = np.random.normal(0, 10, (image_size[0], image_size[1],
            in_chn)).astype(np.int64)
        print("ifmap: ", ifmap)
        #ifmap = np.random.seed(42, 0, 10, (image_size[0], image_size[1],
        #    in_chn)).astype(np.int64)
        weights = np.random.normal(0, 10, (filter_size[0], filter_size[1], in_chn,
            out_chn)).astype(np.int64)
        print("weights: ", weights)
        #weights = np.random.seed(42, 0, 10, (filter_size[0], filter_size[1], in_chn,
        #    out_chn)).astype(np.int64)
        bias = np.random.normal(0, 10, out_chn).astype(np.int64)
        print("bias: ", bias)
        #bias = np.random.seed(42, 0, 10, out_chn).astype(np.int64)
        # ofmap w/ padding
        #ofmap = np.zeros((image_size[0], image_size[1].shape[1]+1,
         #   out_chn)).astype(np.int64)
        # ofmap w/o pading
        ofmap = np.zeros((image_size[0]-filter_size[0]+1, image_size[1]-filter_size[1]+1,
            out_chn)).astype(np.int64)

        # Reference Output
        reference = conv(ifmap, weights, bias)
        reference_winograd = conv_winograd(ifmap, weights, bias)
        print("reference: ", reference)
        print("winograd reference: ", reference_winograd)

        self.serializer.configure(ifmap, weights, bias, image_size, filter_size)
        self.deserializer.configure(ofmap, reference, image_size, filter_size)
