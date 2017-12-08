pre_tr_ifmap_chns # x idx ranges from 0 to 4, y idx ranges from 0 to 4

elem0_push_chns = [pre_tr_ifmap_chns[0]]
elem1_push_chns = [pre_tr_ifmap_chns[0]]

for tile_chn in elem0_push_chns:
    # data 4 in size
    for x in range(4):
        tile_chn[x].push(data[x])