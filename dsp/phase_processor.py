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
from collections import defaultdict


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


def pipelined_timeline(trigger, events):
    '''
    the `trigger` Signal gets fed into a tapped delay line
    `events` is a list of tuples like (tap_number, instructions)
    the instructions are executed when the respective tap is asserted
    useful for setting up data paths
    '''

    # Keys = tap_numbers,  Values = lists of instructions
    evt = dict()

    # For compatibility with timeline interface
    if type(events) in (list, tuple):
        for e in events:
            evt[e[0]] = e[1]

    ts = Signal(max(evt.keys()))
    sync = [ts.eq((ts << 1) | trigger)]

    for tap, instrs in evts.items():
        if tap == 0:
            sync.append(If(trigger, *instrs))
        else:
            sync.append(If(ts[tap - 1], *instrs))

    return sync


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

        eventList = defaultdict(list)
        cycle = W_CORDIC + 2

        ref_phase = Signal.like(self.phases[0])

        # Latch the reference phase
        eventList[cycle] += [ref_phase.eq(phase_in)]

        # Latch the magnitudes
        for i, m in enumerate(self.mags):
            eventList[cycle + 2 * i] += [m.eq(mag_in)]

        self.comb += self.phases[0].eq(ref_phase)

        # Feed the multiplier
        B = Signal.like(ref_phase)
        self.submodules.mult = Multiplier5(ref_phase, B)
        for i, b in enumerate(self.mult_factors):
            eventList[cycle + 5 + 2 * i] += [B.eq(b)]

        # Delay phase_in a bit to match up with multiplier result
        temp = phase_in
        for i in range(1):
            phase_in_ = Signal.like(phase_in)
            self.sync += phase_in_.eq(temp)
            temp = phase_in_

        # The multiplier needs 5 + 1 to spit out the first result
        # store the multiplier result - previously latched phase from cordic
        for i, p_out in enumerate(self.phases[1:]):
            eventList[cycle + 11 + 2 * i] += [p_out.eq(self.mult.OUT - p)]

        eventList[20] += [self.strobe_out.eq(1)]

        self.sync += [
            self.strobe_out.eq(0),
            pipelined_timeline(self.strobe_in, t)
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
