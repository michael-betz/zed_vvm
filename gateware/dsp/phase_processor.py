'''
  Latches the serial phase / magnitude streams into parallel output registers

  Then calculates

  P_OUT_N = (P_IN0 * MULT) - P_IN_N,

  where

  P_OUT_N = output phase difference of channel N = 1 .. 3 to reference channel
  P_IN0 = reference phase input
  MULT = fixed multiplication factor (measurement harmonic)
  P_IN_N = input absolute phase of channel N = 1 .. 3

  try:  python3 phase_processor.py build
'''
from sys import argv
from os.path import join, dirname, abspath
from collections import defaultdict

from migen import *
from migen.genlib.misc import timeline
from litex.soc.interconnect.csr import AutoCSR, CSRStorage, CSRStatus


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


def pipelined_timeline(trigger, events):
    '''
    the `trigger` Signal gets fed into a tapped delay line
    `events` is a list of tuples like (tap_number, instructions)
    or
    `events` is a dict with key = tap_number and value = list of instructions
    the instructions are executed when the respective tap is asserted
    useful for setting up pipelined data-paths
    '''

    # Keys = tap_numbers,  Values = lists of instructions

    # For compatibility with timeline interface
    if type(events) in (list, tuple):
        evts = dict()
        for e in events:
            evts[e[0]] = e[1]
    else:
        evts = events

    ts = Signal(max(evts.keys()))
    sync = [ts.eq((ts << 1) | trigger)]

    for tap in sorted(evts.keys()):
        if tap == 0:
            sync.append(If(trigger, *evts[tap]))
        else:
            sync.append(If(ts[tap - 1], *evts[tap]))

    return sync


class PhaseProcessor(Module, AutoCSR):
    '''
    Implements the phase measurement data-path, dealing with the phase &
    magnitude output stream from the cordic. See doc/phase_processor.png

    W_CORDIC = width of cordic (to calculate its latency)
    strobe_in = pulse when first sample of IQ stream is valid at cordic input
    latency with W_CORDIC = 21 (strobe_in to strobe_out): 34 cycles
    dead-time: at least 11 cycles between strobe_in pulses
    '''
    def __init__(
        self, mag_in=None, phase_in=None, strobe_in=None, N_CH=4, W_CORDIC=21
    ):
        #---------
        # inputs
        #---------
        # Magnitude / phase streams from cordic
        if mag_in is None:
            mag_in = Signal(W_CORDIC)
        self.mag_in = mag_in

        if phase_in is None:
            phase_in = Signal((W_CORDIC + 1, True))
        self.phase_in = phase_in

        if strobe_in is None:
            strobe_in = Signal()
        self.strobe_in = strobe_in

        # 3 multiplication factors for the reference phase (0 - 15)
        self.mult_factors = [Signal(4) for i in range(N_CH - 1)]

        #---------
        # outputs
        #---------
        # 4 x absolute magnitude value
        self.mags = [Signal(W_CORDIC) for i in range(N_CH)]

        # 1 x absolute phase (rotating) of reference channel
        # 3 x phase difference (static) to reference
        self.phases = [Signal((W_CORDIC + 1, True)) for i in range(N_CH)]

        # pulses when all the above outputs are valid
        self.strobe_out = Signal()

        ###

        # Which instructions to run at which cycle of the pipeline
        eventList = defaultdict(list)

        # Latency of the cordic upstream of this block
        lat_cordic = W_CORDIC + 2

        # Latch the reference phase from cordic output stream
        eventList[lat_cordic] += [self.phases[0].eq(phase_in)]

        # Latch 4 x magnitude from cordic output stream
        for i, m in enumerate(self.mags):
            eventList[lat_cordic + 2 * i] += [m.eq(mag_in)]

        # Feed reference phase and 3 x constants (B) into the multiplier
        B = Signal.like(self.phases[0])
        self.submodules.mult = Multiplier5(self.phases[0], B)
        for i, b in enumerate(self.mult_factors):
            eventList[lat_cordic + 2 * i] += [B.eq(b)]

        # Delay phase_in stream to match up with multiplier result stream
        temp = phase_in
        for i in range(4):
            phase_in_ = Signal.like(phase_in)
            self.sync += phase_in_.eq(temp)
            temp = phase_in_

        # The multiplier needs 5 + 1 cycles to spit out the first result
        # store `multiplier result - delayed phase` from cordic
        for i, p_out in enumerate(self.phases[1:]):
            eventList[lat_cordic + 6 + 2 * i] += [
                p_out.eq(self.mult.OUT - phase_in_)
            ]

        # We're done, all results have been calculated, assert strobe_out.
        eventList[lat_cordic + 6 + 2 * i] += [self.strobe_out.eq(1)]

        self.sync += [
            self.strobe_out.eq(0),
            pipelined_timeline(self.strobe_in, eventList)
        ]

    def add_csr(self):
        # Reference phase multiplication factors
        for i, multf in enumerate(self.mult_factors):
            n = 'mult{}'.format(i + 1)
            csr = CSRStorage(len(multf), reset=1, name=n)
            setattr(self, n, csr)
            self.comb += multf.eq(csr.storage)


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
