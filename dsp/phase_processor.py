'''
  Latch the stream
  from cordic output at the right time into the right place
'''
from sys import argv
from migen import *
from migen.genlib.misc import timeline
from litex.soc.interconnect.csr import AutoCSR, CSRStorage, CSRStatus
from os.path import join, dirname, abspath


class Multiplier5(Module):
    ''' 5 cycle latency multiply '''
    def __init__(self, A, B):
        A_ = Signal.like((A, True))
        B_ = Signal.like((B, True))
        A__ = Signal.like((A, True))
        B__ = Signal.like((B, True))
        R = Signal((len(A) + len(B), True))
        R_ = Signal.like(R)
        self.OUT = Signal.like(R)

        ###

        self.sync += [
            A_.eq(A),
            A__.eq(A_),
            B_.eq(B),
            B__.eq(B_),
            R.eq(A__ * B__),
            R_.eq(R),
            self.OUT.eq(R_)
        ]

class PhaseProcessor(Module, AutoCSR):
    def __init__(self, mag_in=None, phase_in=None, N_CH=4, W_CORDIC=21):

        # From cordic
        if mag_in is None:
            mag_in = Signal(W_CORDIC)
        if phase_in is None:
            phase_in = Signal(W_CORDIC + 1)
        self.strobe_in = Signal()
        self.mult_factors = [Signal(4) for i in range(N_CH - 1)]

        # outputs
        self.mags = [Signal(W_CORDIC) for i in range(N_CH)]
        self.phases = [Signal((W_CORDIC + 1, True)) for i in range(N_CH)]
        self.strobe_out = Signal()

        ###

        ps = []  # temporary variables to latch cordic phase output
        t = []
        cycle = W_CORDIC + 2

        for m in self.mags:
            p = Signal.like(self.phases[0])
            t.append((
                cycle,          # N cycles after self.ddc.result_strobe
                [               # ... carry out these instructions
                    m.eq(mag_out),
                    p.eq(phase_out)
                ]
            ))
            cycle += 2
            ps.append(p)
        self.comb += phases[0].eq(ps[0])

        # Feed the multiplier after all 8 cordic outputs have been latched
        B = Signal.like(ps[0])
        self.submodules.mult = Multiplier5(ps[0], B)
        for b in self.mult_factors:
            t.append((
                cycle,
                [B.eq(b)]
            ))
            cycle += 1

        # We gave the multiplier 3 cycles by now already,
        # it needs 5 to spit out the first result
        # store the multiplier result - previously latched phase from cordic
        cycle += 2
        for phase, m in zip(phases[1:], ms[1:]):
            t.append((
                cycle,
                [phase.eq(self.mult.OUT - m)]
            ))
            cycle += 1
