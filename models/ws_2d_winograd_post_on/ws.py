from nnsim.module import Module, ModuleList
from nnsim.reg import Reg
from nnsim.channel import Channel

from .pe import PE
from .post_transform import PostTransform
from .serdes import InputDeserializer, OutputSerializer
from .glb import IFMapGLB, WeightsGLB, BiasGLB
from .noc import IFMapNoC, WeightsNoC, PSumRdNoC, PSumWrNoC, BiasNoC, PostTrWrNoC, PostTrRdNoC

class WSArch(Module):
    def instantiate(self, arr_x, arr_y,
            input_chn, output_chn,
            chn_per_word,
            ifmap_glb_depth):
        # PE static configuration (immutable)
        self.name = 'chip'
        self.arr_x = arr_x
        self.arr_y = arr_y
        self.chn_per_word = chn_per_word
        
        self.post_tr_x = arr_x # num output channels = 8
        self.post_tr_y = 4 # num tiles = 4
        
        self.stat_type = 'show'

        # Instantiate DRAM IO channels
        self.input_chn = input_chn
        self.output_chn = output_chn

        # Instantiate input deserializer and output serializer
        self.ifmap_wr_chn = Channel()
        self.weights_wr_chn = Channel()
        self.bias_wr_chn = Channel()
        self.deserializer = InputDeserializer(self.input_chn, self.ifmap_wr_chn,
                self.weights_wr_chn, self.bias_wr_chn, arr_x, arr_y,
                chn_per_word)

        self.psum_output_chn = Channel()
        self.serializer = OutputSerializer(self.output_chn, self.psum_output_chn)

        # Instantiate GLB and GLB channels
        self.ifmap_rd_chn = Channel(3)
        self.ifmap_glb = IFMapGLB(self.ifmap_wr_chn, self.ifmap_rd_chn,
                ifmap_glb_depth, chn_per_word)

        self.psum_rd_chn = Channel(3)
        self.psum_noc_wr_chn = Channel()
        #  self.psum_glb = PSumGLB(self.psum_wr_chn, self.psum_noc_wr_chn, self.psum_rd_chn,
        #          psum_glb_depth, chn_per_word)

        self.weights_rd_chn = Channel()
        self.weights_glb = WeightsGLB(self.weights_wr_chn, self.weights_rd_chn)
        
        self.bias_rd_chn = Channel()
        self.bias_glb = BiasGLB(self.bias_wr_chn, self.bias_rd_chn)

        # PE Array and local channel declaration
        self.pe_array = ModuleList()
        self.pe_ifmap_chns = ModuleList()
        self.pe_filter_chns = ModuleList()
        self.pe_psum_chns = ModuleList()
        self.pe_psum_chns.append(ModuleList())
        for x in range(self.arr_x):
            self.pe_psum_chns[0].append(Channel(32))

        # Actual PE array instantiation
        for y in range(self.arr_y):
            self.pe_array.append(ModuleList())
            self.pe_ifmap_chns.append(ModuleList())
            self.pe_filter_chns.append(ModuleList())
            self.pe_psum_chns.append(ModuleList())
            for x in range(self.arr_x):
                self.pe_ifmap_chns[y].append(Channel(32))
                self.pe_filter_chns[y].append(Channel(32))
                self.pe_psum_chns[y+1].append(Channel(32))
                self.pe_array[y].append(
                    PE(x, y,
                        self.pe_ifmap_chns[y][x],
                        self.pe_filter_chns[y][x],
                        self.pe_psum_chns[y][x],
                        self.pe_psum_chns[y+1][x]
                    )
                )
                
        # Post Transform Array and local channel declaration
        self.post_tr_array = ModuleList()
        self.post_tr_bias_chns = ModuleList()
        self.post_tr_ofmap_in_chns = ModuleList()
        self.post_tr_ofmap_out_chns = ModuleList()
        
        # Actual post transform array instantiation
        for y in range(self.post_tr_y):
            self.post_tr_array.append(ModuleList())
            self.post_tr_bias_chns.append(ModuleList())
            self.post_tr_ofmap_in_chns.append(ModuleList())
            self.post_tr_ofmap_out_chns.append(ModuleList())
            for x in range(self.post_tr_x):
                self.post_tr_bias_chns[y].append(Channel(32))
                self.post_tr_ofmap_in_chns[y].append(Channel(32))
                self.post_tr_ofmap_out_chns[y].append(Channel(32))
                self.post_tr_array[y].append(
                    PostTransform(x, y,
                        self.post_tr_bias_chns[y][x],
                        self.post_tr_ofmap_in_chns[y][x],
                        self.post_tr_ofmap_out_chns[y][x],
                    )
                )

        # Setup NoC to deliver weights, ifmaps and psums
        self.filter_noc = WeightsNoC(self.weights_rd_chn, self.pe_filter_chns, self.chn_per_word)
        self.ifmap_noc = IFMapNoC(self.ifmap_rd_chn, self.pe_ifmap_chns, self.arr_x, self.chn_per_word)
        self.psum_rd_noc = PSumRdNoC(self.pe_psum_chns[0], self.chn_per_word)
        #self.psum_wr_noc = PSumWrNoC(self.pe_psum_chns[-1], self.psum_output_chn, self.chn_per_word)
        self.bias_noc = BiasNoC(self.bias_rd_chn, self.post_tr_bias_chns, self.chn_per_word)
        self.post_tr_wr_noc = PostTrWrNoC(self.pe_psum_chns[-1], self.post_tr_ofmap_in_chns, self.chn_per_word)
        self.post_tr_rd_noc = PostTrRdNoC(self.post_tr_ofmap_out_chns, self.psum_output_chn, self.chn_per_word)

    def configure(self, image_size, filter_size, in_chn, out_chn):
        in_sets = self.arr_y//self.chn_per_word
        out_sets = self.arr_x//self.chn_per_word
        fmap_per_iteration = image_size[0]*image_size[1]
        num_iteration = image_size[0]*image_size[1]

        self.deserializer.configure(image_size, filter_size)
        self.ifmap_glb.configure(image_size, filter_size, in_sets, fmap_per_iteration)
        #   self.psum_glb.configure(filter_size, out_sets, fmap_per_iteration)
        self.filter_noc.configure(in_sets, self.arr_x)
        self.ifmap_noc.configure(in_sets)
        self.bias_noc.configure(self.post_tr_x, self.post_tr_y)
        self.post_tr_wr_noc.configure(self.post_tr_x, self.post_tr_y)
        self.post_tr_rd_noc.configure()
        self.psum_rd_noc.configure(self.arr_x)
        #self.psum_wr_noc.configure(num_iteration, fmap_per_iteration, out_sets)

        for y in range(self.arr_y):
            for x in range(self.arr_x):
                self.pe_array[y][x].configure(fmap_per_iteration, num_iteration)
                
        for y in range(self.post_tr_y):
            for x in range(self.post_tr_x):
                self.post_tr_array[y][x].configure()
                
        print("Num PEs: ",self.arr_x*self.arr_y)
        print("Num post transform blocks: ", self.post_tr_x*self.post_tr_y)
        
        print("image size: ",image_size)
        print("filter size: ",filter_size)
        print("input channels: ",in_chn)
        print("output channels: ",out_chn)
