'''
Tiny first order IIR filter without multipliers
  * there's a DC error when shifts > ACC_GUARD
  * TODO find way to get rid of guard bits
https://zipcpu.com/dsp/2017/08/19/simple-filter.html
'''
from numpy import *
from sys import argv

from migen import *
from matplotlib.pyplot import *


class TinyIIR(Module):
    def __init__(self, IO_W=8):
        N_SHIFTS = 4
        self.strobe = Signal()
        self.strobe_out = Signal()
        self.x = Signal((IO_W, True))
        self.y = Signal.like(self.x)
        # averaging factor: 0 = no averaging, 15 = maximum averaging
        self.shifts = Signal(N_SHIFTS)

        ###

        ACC_GUARD = (1 << N_SHIFTS) - 1  # Number of accumulator guard bits
        acc = Signal((IO_W + ACC_GUARD, True))
        acc_ = Signal.like(acc)
        x_hr = Signal.like(acc)
        delta = Signal((IO_W + ACC_GUARD + 1, True))
        strobe_ = Signal()
        strobe__ = Signal()

        self.comb += [
            # Pad input to match accumulator width
            x_hr.eq(self.x << ACC_GUARD),
            # Remove LSBs from accumulator to match output width
            self.y.eq(acc_ >> ACC_GUARD),
        ]

        self.sync += [
            strobe_.eq(self.strobe),
            strobe__.eq(strobe_),
            self.strobe_out.eq(strobe__),
            acc_.eq(acc),
            If(self.strobe,
                # First cycle, compute error signal and latch
                delta.eq(x_hr - acc_)
            ),
            If(strobe_,
                # Second cycle, scale error and accumulate
                acc.eq(acc_ + (delta >> self.shifts))
            )
        ]


from random import random


def fir_tb(dut):
    maxValue = (1 << (len(dut.x) - 1))
    yield dut.x.eq(maxValue - 1)
    for i in range(30000):
        if i == 1:
            yield dut.shifts.eq(2)
        if i == 4000:
            yield dut.x.eq(-maxValue)
        if i == 8000:
            yield dut.x.eq(maxValue - 1)
        # yield dut.x.eq(int((2 * random() - 1) * maxValue))
        yield dut.strobe.eq(i % 3 == 0)
        yield
        yield dut.strobe.eq(0)
        yield
        yield


if __name__ == "__main__":
    tName = argv[0].replace('.py', '')
    dut = TinyIIR(21)
    tb = fir_tb(dut)
    run_simulation(dut, tb, vcd_name=tName + '.vcd')
