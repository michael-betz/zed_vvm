'''
  Latches the serial phase / magnitude streams into parallel output registers

  Then calculates

  P_OUT_N = (P_IN0 * MULT) - P_IN_N,

  where

  P_OUT_N = output phase difference of channel N = 1 .. 3 to reference channel
  P_IN0 = reference phase input
  MULT = fixed multiplication factor (measurement harmonic)
  P_IN_N = input absolute phase of channel N = 1 .. 3

  This is implemented as a timeline = a serial string of 40 instructions

  try:  python3 phase_processor.py build
'''
from sys import argv
from migen import *
from migen.genlib.misc import timeline
from litex.soc.interconnect.csr import AutoCSR, CSRStorage, CSRStatus
from os.path import join, dirname, abspath


class Multiplier5(Module):
    '''
    5 cycle latency multiply.
    To give the synthesizer some degrees of freedom
    '''
    def __init__(self, A, B):
        A_ = Signal.like(A)
        B_ = Signal.like(B)
        A__ = Signal.like(A)
        B__ = Signal.like(B)
        R = Signal(len(A) + len(B))
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
        self.mag_in = mag_in

        if phase_in is None:
            phase_in = Signal(W_CORDIC + 1)
        self.phase_in = phase_in

        self.strobe_in = Signal()
        self.mult_factors = [Signal(4) for i in range(N_CH - 1)]

        # outputs
        self.mags = [Signal(W_CORDIC) for i in range(N_CH)]
        self.phases = [Signal(W_CORDIC + 1) for i in range(N_CH)]
        self.strobe_out = Signal()

        ###

        ps = []  # temporary variables to latch cordic phase output
        t = []
        cycle = W_CORDIC + 2

        for m in self.mags:
            p = Signal.like(self.phases[0])
            t.append((
                cycle,          # N cycles after self.ddc.result_strobe ...
                [               # ... latch phase and magnitude
                    m.eq(mag_in),
                    p.eq(phase_in)
                ]
            ))
            cycle += 2
            ps.append(p)
        self.comb += self.phases[0].eq(ps[0])

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
        # it needs 5 + 1 to spit out the first result
        # store the multiplier result - previously latched phase from cordic
        cycle += 3
        for phase, p in zip(self.phases[1:], ps[1:]):
            t.append((
                cycle,
                [phase.eq(self.mult.OUT - p)]
            ))
            cycle += 1
        t.append((
            cycle,
            [self.strobe_out.eq(1)]
        ))
        self.sync += [
            self.strobe_out.eq(0),
            timeline(self.strobe_in, t)
        ]

def main():
    ''' generate a .v file for simulation with Icarus / general usage '''
    tName = argv[0].replace('.py', '')
    dut = PhaseProcessor()
    if 'build' in argv:
        from migen.fhdl.verilog import convert
        convert(
            dut,
            name=tName,
            ios={
                # in
                dut.mag_in,
                dut.phase_in,
                dut.strobe_in,
                *dut.mult_factors,

                # out
                *dut.mags,
                *dut.phases,
                dut.strobe_out
            },
            display_run=True
        ).write(tName + '.v')


if __name__ == '__main__':
    if len(argv) <= 1:
        print(__doc__)
        exit(-1)
    main()
