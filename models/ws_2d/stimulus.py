from scipy.signal import correlate2d
import numpy as np

from nnsim.module import Module
from .serdes import InputSerializer, OutputDeserializer

def conv(x, W, b):
    print(x.shape, W.shape, b.shape)
    y = np.zeros([x.shape[0], x.shape[1], W.shape[3]]).astype(np.int64)
    for out_channel in range(W.shape[3]):
        for in_channel in range(W.shape[2]):
            W_c = W[:, :, in_channel, out_channel]
            x_c = x[:, :, in_channel]
            y[:, :, out_channel] += correlate2d(x_c, W_c, mode="same")
        y[:, :, out_channel] += b[out_channel]
    return y

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
        #np.random.seed(0)
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
        ofmap = np.zeros((image_size[0], image_size[1],
            out_chn)).astype(np.int64)

        # Reference Output
        reference = conv(ifmap, weights, bias)
        print("reference: ", reference)

        self.serializer.configure(ifmap, weights, bias, image_size, filter_size)
        self.deserializer.configure(ofmap, reference, image_size)
