"""
 7-series ISERDES receiver for LVDS ADCs

 DCO is a DDR clock signal, doing one transition for every bit.
 This transition happens when data is stable (90 deg phase shift)

 try `python3 s7_iserdes.py build`
"""

from sys import argv
from collections import Counter, defaultdict

from migen import *
from migen.build.xilinx.common import xilinx_special_overrides
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.cdc import MultiReg, ElasticBuffer, PulseSynchronizer
from litex.build.io import DifferentialInput
from migen.genlib.misc import timeline


class S7_iserdes(Module):
    def __init__(self, S=8, D=2, INITIAL_IDELAY=15, clock_regions=[0, 1]):
        """
        S = serialization factor (bits per frame)
        D = number of parallel lanes
        clock_regions:
            list of D integers specifying how to assign the lvds_data input
            pins to specific clock regions.
            Each clock_region will be treated as a separate clock domain,
            having its own BUFR, BUFIO, FIFO and reset sync. logic
            Example for 3 signals, where the last one is in a separate region:
            clock_regions = [0, 0, 1]
        """
        self.CLOCK_REGIONS = Counter(clock_regions)  # = {0: 2, 1: 1}

        # LVDS DDR bit clock
        self.dco_p = Signal()
        self.dco_n = Signal()

        # data (+frame) lanes
        self.lvds_data_p = Signal(D)
        self.lvds_data_n = Signal(D)

        # Pulse to rotate bits (sys clock domain)
        # Will be synchronized to all clock regions and applied to all ISERDES
        self.bitslip = Signal()

        # IDELAY control for DCO clock input
        # on sys clock domain
        self.id_inc = Signal()
        self.id_dec = Signal()
        self.id_value = Signal(5)

        # parallel data out, S-bit serdes on D-lanes
        # on `sample` clock domain
        self.data_outs = [Signal(S) for i in range(D)]

        ###

        # recovered ADC sampling clock
        self.clock_domains.cd_sample = ClockDomain("sample")
        self.init_running = Signal(reset=1)

        self.iserdes_default = {
            "p_DATA_WIDTH": S,
            "p_DATA_RATE": "DDR",
            "p_SERDES_MODE": "MASTER",
            "p_INTERFACE_TYPE": "NETWORKING",
            "p_NUM_CE": 1,
            "p_IOBDELAY": "NONE",

            "i_DDLY": 0,
            "i_CE1": 1,
            "i_CE2": 1,
            "i_DYNCLKDIVSEL": 0,
            "i_DYNCLKSEL": 0
        }

        # -------------------------------------------------
        #  DCO input clock --> IDELAYE2 --> BUFMRCE
        # -------------------------------------------------
        dco = Signal()
        dco_delay = Signal()
        dco_delay_2 = Signal()
        id_CE = Signal()
        self.comb += id_CE.eq(self.id_inc ^ self.id_dec)
        self.specials += DifferentialInput(self.dco_p, self.dco_n, dco)
        self.specials += Instance("IDELAYE2",
            p_DELAY_SRC="IDATAIN",
            p_HIGH_PERFORMANCE_MODE="TRUE",
            p_REFCLK_FREQUENCY=200.0,
            p_IDELAY_TYPE="VARIABLE",
            p_IDELAY_VALUE=INITIAL_IDELAY,

            i_C=ClockSignal("sys"),
            i_LD=ResetSignal("sys"),
            i_INC=self.id_inc,
            i_CE=id_CE,
            i_LDPIPEEN=0,
            i_CINVCTRL=0,
            i_CNTVALUEIN=Constant(0, 5),
            i_DATAIN=0,
            i_REGRST=0,
            i_IDATAIN=dco,

            o_DATAOUT=dco_delay,
            o_CNTVALUEOUT=self.id_value
        )

        bufmr_ce = Signal()
        bufr_clr = Signal(reset=1)
        self.specials += Instance(
            "BUFMRCE",
            i_CE=bufmr_ce,
            i_I=dco_delay,
            o_O=dco_delay_2
        )

        # -------------------------------------------------
        #  Reset sequence
        # -------------------------------------------------
        # Sample clock domain will reset on sys clock reset.
        # ... which will also trigger the init sequence below
        #
        # synchronize BUFR dividers on sys_clk reset
        # a symptom of screwing this up is:
        #   * different number of bitslips are required
        #     for ISERDES in different clock regions
        #
        # __Note:__
        # The sequence suggested in [1] releases `bufr_clr` last,
        # which for me did not align the BUFR dividers reliably.
        # However releasing `bufmr_ce` last did the tick.
        # Error in the Xilinx documentation?
        #
        # [1] UG472 p. 110 `BUFR Alignment`
        self.sync.sys += timeline(
            self.init_running,
            [
                # Shut down sample_clk at BUFMRCE, clear regional dividers ...
                (0, [bufr_clr.eq(1), bufmr_ce.eq(0)]),
                (4, [bufr_clr.eq(0)]),
                # Re-enable regional clocks
                (8, [bufmr_ce.eq(1)]),
                # Regional clocks are running and synced,
                # release `cd_sample` reset
                (16, [self.init_running.eq(0)])
            ]
        )
        # Only release all resets on sample_clk domain after step 16
        self.specials += AsyncResetSynchronizer(
            self.cd_sample,
            self.init_running
        )

        # -------------------------------------------------
        #  generate a separate CD for each clock region
        # -------------------------------------------------
        # each one having its own BUFR, BUFIO and reset sync.
        r_ioclks = {}  # Regional IO clocks driven by BUFIO
        r_clks = {}   # Regional fabric clocks driven by BUFR
        r_bitslips = {}  # Regional bitslip pulses

        for cr_i, cr_n in self.CLOCK_REGIONS.items():
            print(f"Clock region: {cr_i}, inputs: {cr_n}")

            # regional buffer for the fast IO clock
            ioclk = Signal()
            self.specials += Instance(
                "BUFIO",
                i_I=dco_delay_2,
                o_O=ioclk
            )

            # regional clock domain for ISERDES output + interface fabric
            cd_name = f'bufr_{cr_i}'
            cd = ClockDomain(cd_name)
            self.clock_domains += cd
            self.specials += Instance(
                "BUFR",
                p_BUFR_DIVIDE=str(S // 2),  # div by 2 due to DDR
                i_I=dco_delay_2,
                i_CE=1,
                i_CLR=bufr_clr,
                o_O=cd.clk
            )

            # Releasing global `sample` reset releases local `bufr_N` reset
            AsyncResetSynchronizer(cd, ResetSignal('sample'))

            # Move bitslip pulse into regional CD
            ps = PulseSynchronizer('sys', cd_name)
            self.submodules += ps
            self.comb += ps.i.eq(self.bitslip)

            # Collect all region specific items in dicts
            r_ioclks[cr_i] = ioclk
            r_clks[cr_i] = cd.clk
            r_bitslips[cr_i] = ps.o

        # Make last regional clock available to rest of the design
        # Note that the output of the BUFG is not phase matched with the
        # output of the BUFR. I'll use elastic buffers to move over the data
        # TODO get sample clock from IBUFDS --> MMCM --> BUFG ???
        # The BUFG cell BUFG_1 I pin is driven by a BUFR cell BUFR_1. For 7-Series devices, this is not a recommended clock topology. Please analyze your clock network and remove the BUFR to BUFG cascade.
        self.specials += Instance(
            "BUFG",
            i_I=cd.clk,
            o_O=ClockSignal("sample")
        )

        # -------------------------------------------------
        #  Generate an IDERDES for each data lane
        # -------------------------------------------------
        r_dos = defaultdict(list)  # Regional data-outs, key = clock region
        for d_p, d_n, c_reg in zip(
            self.lvds_data_p,
            self.lvds_data_n,
            clock_regions
        ):
            d_i = Signal()
            self.specials += DifferentialInput(d_p, d_n, d_i)

            # Collect parallel output data
            do = Signal(S)

            self.specials += Instance(
                "ISERDESE2",
                **self.iserdes_default,
                i_CLK=r_ioclks[c_reg],
                i_CLKB=~r_ioclks[c_reg],
                i_CLKDIV=r_clks[c_reg],
                i_D=d_i,
                i_BITSLIP=r_bitslips[c_reg],
                i_RST=ResetSignal(cd_name),
                o_Q1=do[0],
                o_Q2=do[1],
                o_Q3=do[2],
                o_Q4=do[3],
                o_Q5=do[4],
                o_Q6=do[5],
                o_Q7=do[6],
                o_Q8=do[7]
            )

            r_dos[c_reg].append(do)

        # -------------------------------------------------
        #  Generate elastic-buffer for each clock region
        # -------------------------------------------------
        fifo_outs = []
        for cr_i, r_dos in r_dos.items():
            dos = Cat(r_dos)

            cd_name = f'bufr_{cr_i}'
            ebuf_name = f'ebuf_{cr_i}'

            # Regional FIFO
            ebuf = ElasticBuffer(len(dos), 2, cd_name, 'sample')
            setattr(self.submodules, ebuf_name, ebuf)
            self.comb += ebuf.din.eq(dos)
            fifo_outs.append(ebuf.dout)

        self.comb += Cat(self.data_outs).eq(Cat(fifo_outs))


    def getIOs(self):
        """ for easier interfacing to testbench """
        return {
            self.dco_p,
            self.dco_n,
            self.lvds_data_p,
            self.lvds_data_n,
            self.bitslip,
            self.id_inc,
            self.id_dec,
            self.id_value,
            *self.data_outs
        }


if __name__ == "__main__":
    """
    generate a .v file for simulation with xsim using
    the encrypted UNISIM model of ISERDESE2

    to run the simulation, try:
        $ make s7_iserdes.vcd
        $ gtkwave s7_iserdes.vcd
    """
    if "build" not in argv:
        print(__doc__)
        exit(-1)
    from migen.fhdl.verilog import convert
    tName = argv[0].replace(".py", "")
    d = S7_iserdes(S=8, D=1, clock_regions=[0])
    convert(
        d,
        ios=d.getIOs(),
        special_overrides=xilinx_special_overrides,
        # create_clock_domains=False,
        name=tName
    ).write(tName + ".v")
