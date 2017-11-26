from scipy.signal import correlate2d
import numpy as np

from nnsim.module import Module
from .serdes import InputSerializer, OutputDeserializer

def conv(x, W, b):
    # print (x.shape, W.shape, b.shape)
    y = np.zeros([x.shape[0], x.shape[1], W.shape[3]]).astype(np.int64)
    for out_channel in range(W.shape[3]):
        for in_channel in range(W.shape[2]):
            W_c = W[:, :, in_channel, out_channel]
            x_c = x[:, :, in_channel]
            y[:, :, out_channel] += correlate2d(x_c, W_c, mode="same")
        y[:, :, out_channel] += b[out_channel]
    return y

class Stimulus(Module):
    def instantiate(self, arr_x, arr_y, chn_per_word, input_chn, output_chn, psum_chn):
        # PE static configuration (immutable)
        self.arr_x = arr_x
        self.arr_y = arr_y
        self.chn_per_word = chn_per_word

        self.input_chn = input_chn
        self.output_chn = output_chn
        self.psum_chn = psum_chn

        self.ifmap = None
        self.weights = None
        self.bias = None
        self.ofmap = None

        self.serializer = InputSerializer(self.input_chn, self.psum_chn, self.arr_x,
            self.arr_y, self.chn_per_word)
        self.deserializer = OutputDeserializer(self.output_chn, self.psum_chn, self.arr_x,
            self.arr_y, self.chn_per_word)

    def configure(self, image_size, filter_size, in_chn, out_chn, curr_pass):
        #print ("Reconfiguring stimulus...")

        # Test data
        #ifmap = np.zeros((image_size[0], image_size[1],
        #    in_chn)).astype(np.int64)

        if (curr_pass == 0):
            self.ifmap = np.random.normal(0, 10, (image_size[0], image_size[1], in_chn)).astype(np.int64)
            self.weights = np.random.normal(0, 10, (filter_size[0], filter_size[1], in_chn,
                out_chn)).astype(np.int64)
            self.bias = np.random.normal(0, 10, out_chn).astype(np.int64)
            self.ofmap = np.zeros((image_size[0], image_size[1], out_chn)).astype(np.int64)

        #### For debugging: same matrices every time (can debug using Q3)

        #np.random.seed(0)
        #fake_ifmap = np.random.normal(0, 10, (image_size[0], image_size[1],in_chn//2)).astype(np.int64)
        #fake_weights = np.random.normal(0, 10, (filter_size[0], filter_size[1], in_chn//2, out_chn//2)).astype(np.int64)
        #fake_bias = np.random.normal(0, 10, out_chn//2).astype(np.int64)
        #self.ifmap = np.dstack((fake_ifmap,fake_ifmap))
        #weights = np.dstack((fake_weights,fake_weights))
        #self.weights = np.concatenate((weights,weights),axis=3)
        #self.bias = np.concatenate((fake_bias,fake_bias),axis=0)
        #self.ofmap = np.zeros((image_size[0], image_size[1], out_chn)).astype(np.int64)


        # Reference Output
        reference = conv(self.ifmap, self.weights, self.bias)
        print ("ifmap: ", self.ifmap)
        print ("weights: ", self.weights)
        print ("bias: ", self.bias)

        self.serializer.configure(self.ifmap, self.weights, self.bias, image_size, filter_size, curr_pass)
        self.deserializer.configure(self.ofmap, reference, image_size, curr_pass)
