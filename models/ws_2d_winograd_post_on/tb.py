from nnsim.module import Module
from nnsim.channel import Channel
from .ws import WSArch
from .stimulus import Stimulus
from nnsim.reg import Reg

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
        self.num_tiles = 4

        self.arr_x = self.out_chn
        self.arr_y = self.in_chn

        self.input_chn = Channel()
        self.output_chn = Channel()
        
        self.finish_signal_chn = Channel()
        
        self.stat_type = 'show'
        self.raw_stats = {}

        ifmap_glb_depth = self.image_size[0]*self.image_size[1]*self.num_tiles*self.in_chn//self.chn_per_word
        # psum_glb_depth = self.image_size[0]*self.image_size[1]*self.out_chn//self.chn_per_word

        self.stimulus = Stimulus(self.arr_x, self.arr_y, self.chn_per_word,
            self.input_chn, self.output_chn, self.finish_signal_chn)
        self.dut = WSArch(self.arr_x, self.arr_y, self.input_chn,
                self.output_chn, self.chn_per_word, ifmap_glb_depth)

        self.configuration_done = False

    def tick(self):
        if not self.configuration_done:
            self.stimulus.configure(self.image_size, self.filter_size, self.in_chn, self.out_chn)
            self.dut.configure(self.image_size, self.filter_size, self.in_chn, self.out_chn)
            self.configuration_done = True
                
        noc_multicast_list = [] # list of (sub_module, key) tuples for NoC multicasts
        memory_access_list = [] # list of (sub_module, key) tuples for memory access stats
        pe_mac_comp_list = [] # list of (sub_module, key) tuples for PE MAC stats
        tr_alu_comp_list = [] # list of (sub_module, key) tuples for ALU computation stats
        
        ###  collect (sub_module, key) for the comp/memory stats we wish to aggregate
        
        for sub_module in (self.dut.sub_modules + self.stimulus.sub_modules):
            sub_module_stats = sub_module.raw_stats
            for key in sub_module_stats:
                if (key.find('pe_mac') != -1):
                    pe_mac_comp_list.append((sub_module, key))
                if (key.find('alu_comp') != -1):
                    tr_alu_comp_list.append((sub_module, key))
                if (key.find('rd') != -1) or (key.find('wr') != -1):
                    memory_access_list.append((sub_module, key))
                if (key.find('noc') != -1):
                    noc_multicast_list.append((sub_module, key))
                    
        ### aggregate PE MAC comp stats; find PE computation energy
                    
        total_pe_mac_comp = 0
        for tup in pe_mac_comp_list:
            sub_module, key = tup[0], tup[1]
            total_pe_mac_comp += sub_module.raw_stats[key]
            
        self.raw_stats['pe_comp_energy'] = total_pe_mac_comp * 2 * ALU_ENERGY_FACTOR
        
        ### aggregate transform ALU comp stats; find transform ALU computation rf_energy

        total_tr_alu_comp = 0
        for tup in tr_alu_comp_list:
            sub_module, key = tup[0], tup[1]
            total_tr_alu_comp += sub_module.raw_stats[key]

        self.raw_stats['tr_alu_comp_energy'] = total_tr_alu_comp * 1 * ALU_ENERGY_FACTOR
        
        ### aggregate memory access stats for each type of memory access
                
        dram_mem_acc = 0
        glb_mem_acc = 0
        rf_mem_acc = 0

        for tup in memory_access_list:
            sub_module, key = tup[0], tup[1]
            if (key.find('dram') != -1):
                dram_mem_acc += sub_module.raw_stats[key]
            if (key.find('glb') != -1):
                glb_mem_acc += sub_module.raw_stats[key]
            if (key.find('rf') != -1):
                rf_mem_acc += sub_module.raw_stats[key]

        self.raw_stats['dram_mem_acc'] = dram_mem_acc
        self.raw_stats['glb_mem_acc'] = glb_mem_acc
        self.raw_stats['rf_mem_acc'] = rf_mem_acc

        self.raw_stats['total_mem_acc'] = self.raw_stats['dram_mem_acc'] + \
                self.raw_stats['glb_mem_acc'] + self.raw_stats['rf_mem_acc']
            
        ### aggregate channel usage stats for NoC multicasts

        noc_multicasts = 0
        for tup in noc_multicast_list:
            sub_module, key = tup[0], tup[1]
            noc_multicasts += sub_module.raw_stats[key]

        self.raw_stats['total_noc_multicasts'] = noc_multicasts
                
        ### scale memory access stats by energy factors to determine the energy stats
        
        self.raw_stats['dram_energy'] = self.raw_stats['dram_mem_acc'] * DRAM_ENERGY_FACTOR
        self.raw_stats['glb_energy'] = self.raw_stats['glb_mem_acc'] * GLB_ENERGY_FACTOR
        self.raw_stats['rf_energy'] = self.raw_stats['rf_mem_acc'] * RF_ENERGY_FACTOR

        self.raw_stats['data_energy'] = self.raw_stats['dram_energy'] + \
                self.raw_stats['glb_energy'] + self.raw_stats['rf_energy']

        self.raw_stats['comp_energy'] = self.raw_stats['pe_comp_energy'] + self.raw_stats['tr_alu_comp_energy']

        
        ### total energy = data energy + comp energy
        self.raw_stats['total_energy'] = self.raw_stats['data_energy'] + self.raw_stats['comp_energy']
        

if __name__ == "__main__":
    from nnsim.simulator import run_tb
    ws_tb = WSArchTB()
    run_tb(ws_tb, verbose=False)
