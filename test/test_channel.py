import pytest, random
from nnsim.module import Module
from nnsim.channel import Channel
import nnsim.simulator as sim

class ChannelTB(Module):
    def instantiate(self):
        self.channel = Channel(4)
        self.push_count = 0
        self.free_count = 0
        self.test_size = 100

    def tick(self):
        # Print current state of the channel
        c, n = [], 0
        while(self.channel.valid(n)):
            d = self.channel.peek(n)
            assert(d == (self.free_count+n))
            c.append(d)
            n += 1
        print("channel: %s" % c)

        # Possibly push a new element
        if random.random() < 0.5 and self.push_count < self.test_size and \
                self.channel.vacancy():
            self.channel.push(self.push_count)
            print("push: %d" % self.push_count)
            self.push_count += 1

        # Possibly free some elements
        if random.random() < 0.5 and self.free_count < self.test_size and \
                n != 0:
            num_free = random.randint(1, n)
            self.channel.free(num_free)
            self.free_count += num_free
            print("free: %d" % num_free)

def test_channel():
    channel_tb = ChannelTB()
    sim.run_tb(channel_tb, 100, True)
