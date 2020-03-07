"""
    Trigger for doing pulsed RF measurements
    Gates the strobe signal for the IIR filters downstream

    It goes like this:
      * Power level > Threshold on the selected input channel
      * Wait for wait_pre cycles
      * Acquire for wait_acq cycles
      * Wait for wait_post cycles
      * Repeat

      try:
        python3 pulsed_rf_trigger.py build / sim

"""
import sys
from sys import argv

from migen import *
from litex.soc.interconnect.csr import AutoCSR, CSR, CSRStorage
from migen.genlib.cdc import PulseSynchronizer
from migen.genlib.cdc import MultiReg

sys.path.append('..')
from common import csr_helper


class PulsedRfTrigger(Module, AutoCSR):
    def __init__(self, mags_in=None):
        if mags_in is None:
            mags_in = [Signal((6, True)) for i in range(4)]
        self.mags_in = mags_in

        # Pulses when mags_in are valid
        self.strobe_in = Signal()
        self.strobe_out = Signal()

        # 0 - 3: trigger on this channel, > 3: trigger continuously (CW mode)
        self.channel = Signal(3, reset=4)

        # Power level must raise above this threshold
        self.threshold = Signal.like(mags_in[0], reset=0x10110C)

        # Delay between trigger rising edge and acquisition window [fs cycles]
        self.wait_pre = Signal(32, reset=7)

        # Width of acquisition window [fs cycles]
        self.wait_acq = Signal(32, reset=1024)

        # Hold-off time after the acquisition [fs cycles]
        self.wait_post = Signal(32, reset=8)

        ###

        mag = Signal.like(mags_in[0])
        mag_d = Signal.like(mag)
        mag_edge = Signal()
        self.submodules.fsm = ClockDomainsRenamer("sample")(FSM())

        timer = Signal(32)

        self.sync.sample += [
            # Bypass trigger function if channel > 3
            self.strobe_out.eq(
                self.strobe_in &
                (self.fsm.ongoing('ACQUIRE') | (self.channel > 3))
            ),

            # select one of the channels to trigger on,
            Case(
                self.channel,
                {
                    0: mag.eq(mags_in[0]),
                    1: mag.eq(mags_in[1]),
                    2: mag.eq(mags_in[2]),
                    3: mag.eq(mags_in[3]),
                    'default': mag.eq(0)
                }
            ),

            # Delay timer for the state machine
            timer.eq(timer + 1),

            # Detect mag rising above the trigger threshold
            mag_edge.eq(0),
            If(self.strobe_in,
                mag_d.eq(mag),
                mag_edge.eq(
                    (mag_d < self.threshold) &
                    (mag >= self.threshold)
                )
            )
        ]

        self.fsm.act("WAIT_LEVEL",
            If(mag_edge,
                NextValue(timer, 0),
                NextState("WAIT_PRE"),
            )
        )
        self.fsm.act("WAIT_PRE",
            If(timer >= self.wait_pre,
                NextValue(timer, 0),
                NextState("ACQUIRE")
            )
        )
        self.fsm.act("ACQUIRE",
            If(timer >= self.wait_acq,
                NextValue(timer, 0),
                NextState("WAIT_POST")
            )
        )
        self.fsm.act("WAIT_POST",
            If(timer >= self.wait_post,
                NextValue(timer, 0),
                NextState("WAIT_LEVEL")
            )
        )

    def add_csr(self):
        csr_helper(self, 'channel', self.channel)
        csr_helper(self, 'threshold', self.threshold)
        csr_helper(self, 'wait_pre', self.wait_pre)  # , cdc=True)
        csr_helper(self, 'wait_acq', self.wait_acq)
        csr_helper(self, 'wait_post', self.wait_post)


def sample_generator(dut):
    yield dut.threshold.eq(10)
    yield dut.wait_pre.eq(3)
    yield dut.wait_acq.eq(4)
    yield dut.wait_post.eq(5)
    yield dut.strobe_in.eq(0)

    # Bypass trigger logic
    yield dut.channel.eq(7)
    for i in range(5):
        yield
    yield dut.strobe_in.eq(1)
    for i in range(5):
        yield

    # Enable trigger logic
    yield dut.channel.eq(1)
    for i in range(50):
        yield dut.strobe_in.eq(0)
        yield
        yield
        yield dut.mags_in[1].eq(i)
        yield dut.strobe_in.eq(1)
        yield


def main():
    tName = argv[0].replace('.py', '')
    dut = PulsedRfTrigger()
    if "build" in argv:
        ''' generate a .v file for simulation with Icarus / general usage '''
        from migen.fhdl.verilog import convert
        convert(
            dut,
            ios={
                *dut.mags_in,
                dut.strobe_in,
                dut.strobe_out,
                dut.threshold,
                dut.wait_pre,
                dut.wait_acq,
                dut.wait_post
            },
            display_run=True
        ).write(tName + '.v')
        print('wrote', tName + '.v')
    if "sim" in argv:
        run_simulation(
            dut,
            {"sample": sample_generator(dut)},
            {"sample": 10},
            vcd_name=tName + '.vcd'
        )
        print('wrote', tName + '.vcd')


if __name__ == '__main__':
    if len(argv) <= 1:
        print(__doc__)
        exit(-1)
    main()
