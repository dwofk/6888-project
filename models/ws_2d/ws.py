from nnsim.module import Module, ModuleList
from nnsim.reg import Reg
from nnsim.channel import Channel

from .pe import PE
from .serdes import InputDeserializer, OutputSerializer
from .glb import IFMapGLB, WeightsGLB, PSumGLB
from .noc import IFMapNoC, WeightsNoC, PSumRdNoC, PSumWrNoC

class WSArch(Module):
    def instantiate(self, arr_x, arr_y,
            input_chn, output_chn,
            chn_per_word,
            ifmap_glb_depth, psum_glb_depth):
        # PE static configuration (immutable)
        self.name = 'chip'
        self.arr_x = arr_x
        self.arr_y = arr_y
        self.chn_per_word = chn_per_word
        
        self.stat_type = 'show'

        # Instantiate DRAM IO channels
        self.input_chn = input_chn
        self.output_chn = output_chn

        # Instantiate input deserializer and output serializer
        self.ifmap_wr_chn = Channel()
        self.psum_wr_chn = Channel()
        self.weights_wr_chn = Channel()
        self.deserializer = InputDeserializer(self.input_chn, self.ifmap_wr_chn,
                self.weights_wr_chn, self.psum_wr_chn, arr_x, arr_y,
                chn_per_word)

        self.psum_output_chn = Channel()
        self.serializer = OutputSerializer(self.output_chn, self.psum_output_chn)

        # Instantiate GLB and GLB channels
        self.ifmap_rd_chn = Channel(3)
        self.ifmap_glb = IFMapGLB(self.ifmap_wr_chn, self.ifmap_rd_chn,
                ifmap_glb_depth, chn_per_word)

        self.psum_rd_chn = Channel(3)
        self.psum_noc_wr_chn = Channel()
        self.psum_glb = PSumGLB(self.psum_wr_chn, self.psum_noc_wr_chn, self.psum_rd_chn,
                psum_glb_depth, chn_per_word)

        self.weights_rd_chn = Channel()
        self.weights_glb = WeightsGLB(self.weights_wr_chn, self.weights_rd_chn)

        # PE Array and local channel declaration
        self.pe_array = ModuleList()
        self.pe_ifmap_chns = ModuleList()
        self.pe_filter_chns = ModuleList()
        self.pe_psum_chns = ModuleList()
        self.pe_psum_chns.append(ModuleList())
        for x in range(self.arr_x):
            self.pe_psum_chns[0].append(Channel(32))

        # Actual array instantiation
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

        # Setup NoC to deliver weights, ifmaps and psums
        self.filter_noc = WeightsNoC(self.weights_rd_chn, self.pe_filter_chns, self.chn_per_word)
        self.ifmap_noc = IFMapNoC(self.ifmap_rd_chn, self.pe_ifmap_chns, self.arr_x, self.chn_per_word)
        self.psum_rd_noc = PSumRdNoC(self.psum_rd_chn, self.pe_psum_chns[0], self.chn_per_word)
        self.psum_wr_noc = PSumWrNoC(self.pe_psum_chns[-1], self.psum_noc_wr_chn, self.psum_output_chn, self.chn_per_word)

    def configure(self, image_size, filter_size, in_chn, out_chn):
        
        # print inputs
        print("image size:", image_size)
        print("filter size:", filter_size)
        print("in chn:", in_chn)
        print("out chn:", out_chn)
        
        in_sets = self.arr_y//self.chn_per_word
        out_sets = self.arr_x//self.chn_per_word
        fmap_per_iteration_in = image_size[0]*image_size[1]
        fmap_per_iteration_out = (input_size[0]-filter_size[0]+1)*(input_size[1]-filter_size[1]+1)
        num_iteration = filter_size[0]*filter_size[1]

        self.deserializer.configure(image_size)
        self.ifmap_glb.configure(image_size, filter_size, in_sets, fmap_per_iteration_in)
        self.psum_glb.configure(filter_size, out_sets, fmap_per_iteration_out)
        self.filter_noc.configure(in_sets, self.arr_x)
        self.ifmap_noc.configure(in_sets)
        self.psum_rd_noc.configure(out_sets)
        self.psum_wr_noc.configure(num_iteration, fmap_per_iteration_out, out_sets)
        
        print("PE array size:", self.arr_y*self.arr_x)

        for y in range(self.arr_y):
            for x in range(self.arr_x):
                self.pe_array[y][x].configure(fmap_per_iteration, num_iteration)
