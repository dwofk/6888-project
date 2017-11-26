import pytest
from nnsim.costs import CostModel

def test_default_cost():
    cm = CostModel()
    cm.init()
    cm.count("ALU", 200)
    cm.count("RF", 50)
    cm.count("LN", 20)
    cm.count("GB", 30)
    cm.count("DRAM", 10)
    assert cm.energy(True) == 2470
