"""
For streaming raw ADC data to memory

supports a simple trigger state-machine, as you would find it
on a digital storage oscilloscope

try
python3 acquisition.py build
"""

from sys import argv

from migen import *
from litex.soc.interconnect.csr import AutoCSR, CSR, CSRStorage
from migen.genlib.cdc import PulseSynchronizer
from migen.genlib.cdc import MultiReg


class Acquisition(Module, AutoCSR):
    def __init__(self, mems=None, data_ins=None, N_CHANNELS=1, N_BITS=16):
        """
        mems
            list of memory objects of length N_CHANNELS
        acquisition starts after
          * rising edge on self.trigger
          * data_in of the selected channel crossing trig_level
        """
        # uint16, on `sample` clock domain
        if data_ins:
            self.data_ins = data_ins
            N_CHANNELS = len(data_ins)
        else:
            self.data_ins = [Signal((N_BITS, True)) for i in range(N_CHANNELS)]
        self.trigger = Signal()
        self.busy = Signal()

        ###

        if mems is None:
            mems = [Memory(N_BITS, 12) for i in range(N_CHANNELS)]

        trig = Signal()
        # writing trig_csr triggers a single shot acquisition (value dont matter)
        # reading trig_csr reads the 1 when an acquisiton is in progress
        self.trig_csr = CSR()
        self.specials += MultiReg(
            self.busy, self.trig_csr.w
        )
        self.submodules.trig_sync = PulseSynchronizer("sys", "sample")
        self.comb += [
            self.trig_sync.i.eq(self.trig_csr.re),
            trig.eq(self.trigger | self.trig_sync.o)
        ]
        # select the trigger level
        self.trig_level = CSRStorage(16)
        # Force signedness
        self.trig_level.storage.signed = True
        # force trigger
        self.trig_force = CSRStorage(1)
        # select the channel to trigger on
        self.trig_channel = CSRStorage(8)

        # data stream of the channel to trigger on
        data_trigger = Signal((N_BITS, True))
        data_trigger_d = Signal((N_BITS, True))

        is_trigger = Signal()
        self.comb += [
            # select one of the channels to trigger on,
            Case(
                self.trig_channel.storage,
                {k: data_trigger.eq(v) for k, v in enumerate(self.data_ins)}
            ),
            # Pulse `is_trigger` high when sample passes the trigger threshold
            is_trigger.eq(
                (data_trigger_d < self.trig_level.storage) &
                (data_trigger >= self.trig_level.storage) |
                self.trig_force.storage
            )
        ]
        self.sync.sample += data_trigger_d.eq(data_trigger)

        mem_we = Signal()
        mem_addr = Signal(max=mems[0].depth)
        self.submodules.fsm = ClockDomainsRenamer("sample")(FSM())
        self.fsm.act("WAIT_TRIGGER",
            If(trig, NextState("WAIT_LEVEL"))
        )
        self.fsm.act("WAIT_LEVEL",
            If(is_trigger,
                mem_we.eq(1),
                NextValue(mem_addr, mem_addr + 1),
                NextState("ACQUIRE")
            )
        )
        self.fsm.act("ACQUIRE",
            mem_we.eq(1),
            NextValue(mem_addr, mem_addr + 1),
            If(mem_addr >= mems[0].depth - 1,
                NextState("WAIT_TRIGGER"),
                NextValue(mem_addr, 0)
            )
        )
        self.comb += self.busy.eq(~self.fsm.ongoing('WAIT_TRIGGER'))
        for mem, data_in in zip(mems, self.data_ins):
            self.specials += mem
            p1 = mem.get_port(write_capable=True, clock_domain="sample")
            self.specials += p1
            self.comb += [
                p1.dat_w.eq(data_in),
                p1.adr.eq(mem_addr),
                p1.we.eq(mem_we)
            ]


def sample_generator(dut):
    yield dut.trig_level.storage.eq(30)
    for i in range(101):
        yield dut.trigger.eq(0)
        yield dut.data_ins[0].eq(i)
        if i == 15 or i == 75:
            yield dut.trigger.eq(1)
        yield


def main():
    dut = Acquisition()
    if "build" in argv:
        ''' generate a .v file for simulation with Icarus / general usage '''
        from migen.fhdl.verilog import convert
        convert(
            dut,
            ios={
                *dut.data_ins,
                dut.trigger,
                dut.busy
            },
            display_run=True
        ).write(argv[0].replace(".py", ".v"))
    if "sim" in argv:
        run_simulation(
            dut,
            {"sample": sample_generator(dut)},
            {"sys": 10, "sample": 9},
            vcd_name=argv[0].replace(".py", ".vcd")
        )


if __name__ == '__main__':
    if len(argv) <= 1:
        print(__doc__)
        exit(-1)
    main()
