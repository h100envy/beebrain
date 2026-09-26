"""
a tiny seeded generator that gives the same numbers in python and in the browser.

field mode runs the same brain in two places: this package and web/trade/bee.js.
random.Random cannot be reproduced in javascript, so field brains are wired with
mulberry32 instead. the synthetic sim keeps random.Random, so the article table
does not move.
"""
import math

M32 = 0xFFFFFFFF


class FieldRng:
    def __init__(self, seed):
        self.a = seed & M32

    def random(self):
        # mulberry32, written to match the javascript version bit for bit
        self.a = (self.a + 0x6D2B79F5) & M32
        a = self.a
        t = ((a ^ (a >> 15)) * (1 | a)) & M32
        t = ((t + (((t ^ (t >> 7)) * (61 | t)) & M32)) & M32) ^ t
        return ((t ^ (t >> 14)) & M32) / 4294967296

    def sample(self, population, k):
        pool = list(population)
        out = []
        for i in range(k):
            j = i + int(self.random() * (len(pool) - i))
            pool[i], pool[j] = pool[j], pool[i]
            out.append(pool[i])
        return out

    def gauss(self, mu=0.0, sigma=1.0):
        u1 = 1.0 - self.random()
        u2 = self.random()
        return mu + sigma * math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

    def state(self):
        return self.a

    @classmethod
    def from_state(cls, a):
        r = cls(0)
        r.a = a & M32
        return r
