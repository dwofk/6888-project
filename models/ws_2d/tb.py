from nnsim.module import Module
from nnsim.channel import Channel
from .ws import WSArch
from .stimulus import Stimulus

ALU_ENERGY_FACTOR = 1 # reference
RF_ENERGY_FACTOR = 1
PE_ENERGY_FACTOR = 2
GLB_ENERGY_FACTOR = 6
DRAM_ENERGY_FACTOR = 200

class WSArchTB(Module):
    def instantiate(self):
        self.name = 'tb'
        self.image_size = (4, 4)
        self.filter_size = (3, 3)
        self.in_chn = 4
        self.out_chn = 8
        self.chn_per_word = 4

        self.arr_x = self.out_chn
        self.arr_y = self.in_chn

        self.input_chn = Channel()
        self.output_chn = Channel()
        
        self.stat_type = 'show'
        self.raw_stats = {}

        ifmap_glb_depth = self.image_size[0]*self.image_size[1]* \
                self.in_chn//self.chn_per_word
        print("ifmap glb depth:", ifmap_glb_depth)
        psum_glb_depth = self.image_size[0]*self.image_size[1]* \
                self.out_chn//self.chn_per_word
        print("psum glb depth:", psum_glb_depth)

        self.stimulus = Stimulus(self.arr_x, self.arr_y, self.chn_per_word,
            self.input_chn, self.output_chn)
        self.dut = WSArch(self.arr_x, self.arr_y, self.input_chn,
                self.output_chn, self.chn_per_word, ifmap_glb_depth,
                psum_glb_depth)

        self.configuration_done = False

    def tick(self):
        if not self.configuration_done:
            self.stimulus.configure(self.image_size, self.filter_size, self.in_chn, self.out_chn)
            self.dut.configure(self.image_size, self.filter_size, self.in_chn, self.out_chn)
            self.configuration_done = True
            
        memory_accesses_list = [] # list of (sub_module, key) tuples for memory access stats
        pe_mac_comp_list = [] # list of (sub_module, key) tuples for PE MAC stats
        
        ###  collect (sub_module, key) for the comp/memory stats we wish to aggregate
        
        for sub_module in (self.dut.sub_modules + self.stimulus.sub_modules):
            sub_module_stats = sub_module.raw_stats
            for key in sub_module_stats:
                if key == 'pe_mac':
                    pe_mac_comp_list.append((sub_module, key))
                if 'acc' in key:
                    memory_accesses_list.append((sub_module, key))
                    
        ### aggregate PE MAC comp stats; find PE computation energy
                    
        total_pe_mac_comp = 0
        for tup in pe_mac_comp_list:
            sub_module, key = tup[0], tup[1]
            total_pe_mac_comp += sub_module.raw_stats[key]
            
        self.raw_stats['pe_comp_energy'] = total_pe_mac_comp * 2 * ALU_ENERGY_FACTOR
        
        ### aggregate memory access stats for each type of memory access
                
        dram_memory_acc = 0
        glb_memory_acc = 0
        rf_memory_acc = 0
        inter_pe_acc = 0
                
        for tup in memory_accesses_list:
            sub_module, key = tup[0], tup[1]            
            if (key == 'dram_to_glb_acc') or (key == 'dram_to_pe_acc') or (key == 'pe_to_dram_acc'):
                dram_memory_acc += sub_module.raw_stats[key]
            if (key == 'glb_to_pe_acc') or (key == 'pe_to_glb_acc'):
                glb_memory_acc += sub_module.raw_stats[key]
            if key == 'rf_to_pe_acc':
                rf_memory_acc += sub_module.raw_stats[key]
            if key == 'pe_to_pe_acc':
                inter_pe_acc += sub_module.raw_stats[key]   

        self.raw_stats['dram_memory_acc'] = dram_memory_acc
        self.raw_stats['glb_memory_acc'] = glb_memory_acc
        self.raw_stats['rf_memory_acc'] = rf_memory_acc
        self.raw_stats['inter_pe_acc'] = inter_pe_acc
        
        self.raw_stats['total_memory_acc'] = self.raw_stats['dram_memory_acc'] + \
                self.raw_stats['glb_memory_acc'] + \
                self.raw_stats['rf_memory_acc'] + \
                self.raw_stats['inter_pe_acc']
                
        ### scale memory access stats by energy factors to determine the energy stats
        
        self.raw_stats['dram_energy'] = self.raw_stats['dram_memory_acc'] * DRAM_ENERGY_FACTOR
        self.raw_stats['glb_energy'] = self.raw_stats['glb_memory_acc'] * GLB_ENERGY_FACTOR
        self.raw_stats['rf_energy'] = self.raw_stats['rf_memory_acc'] * RF_ENERGY_FACTOR
        self.raw_stats['inter_pe_energy'] = self.raw_stats['inter_pe_acc'] * PE_ENERGY_FACTOR
        
        self.raw_stats['data_energy'] = self.raw_stats['dram_energy'] + \
                self.raw_stats['glb_energy'] + \
                self.raw_stats['rf_energy'] + \
                self.raw_stats['inter_pe_energy']
        
        self.raw_stats['comp_energy'] = self.raw_stats['pe_comp_energy']
        
        ### total energy = data energy + comp energy
        self.raw_stats['total_energy'] = self.raw_stats['data_energy'] + self.raw_stats['comp_energy']


if __name__ == "__main__":
    from nnsim.simulator import run_tb
    ws_tb = WSArchTB()
    run_tb(ws_tb, verbose=False)
