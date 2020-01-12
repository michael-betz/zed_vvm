from sys import path

from migen import *
from migen.build.xilinx.common import *
from litex.soc.interconnect.csr import *
from litex.soc.cores.freqmeter import FreqMeter
from migen.genlib.cdc import MultiReg, PulseSynchronizer
from litex.build.generic_platform import Subsignal, Pins, IOStandard, Misc

from .s7_iserdes import S7_iserdes
from common import LedBlinker, myzip

ltc_pads = [
    ("LTC_SPI", 0,
        Subsignal("cs_n", Pins("LPC:LA14_P")),
        Subsignal("miso", Pins("LPC:LA14_N"), Misc("PULLUP TRUE")),
        Subsignal("mosi", Pins("LPC:LA27_P")),
        Subsignal("clk",  Pins("LPC:LA27_N")),
        IOStandard("LVCMOS25")
    ),
    ("LTC_OUT", 0,  # Bank 0
        Subsignal("a_p", Pins("LPC:LA03_P")),
        Subsignal("a_n", Pins("LPC:LA03_N")),
        Subsignal("b_p", Pins("LPC:LA08_P")),
        Subsignal("b_n", Pins("LPC:LA08_N")),
        IOStandard("LVDS_25"),
        Misc("DIFF_TERM=TRUE")
    ),
    ("LTC_OUT", 1,  # Bank 0
        Subsignal("a_p", Pins("LPC:LA12_P")),
        Subsignal("a_n", Pins("LPC:LA12_N")),
        Subsignal("b_p", Pins("LPC:LA16_P")),
        Subsignal("b_n", Pins("LPC:LA16_N")),
        IOStandard("LVDS_25"),
        Misc("DIFF_TERM=TRUE")
    ),
    ("LTC_OUT", 2,  # Bank 2
        Subsignal("a_p", Pins("LPC:LA22_P")),
        Subsignal("a_n", Pins("LPC:LA22_N")),
        Subsignal("b_p", Pins("LPC:LA25_P")),
        Subsignal("b_n", Pins("LPC:LA25_N")),
        IOStandard("LVDS_25"),
        Misc("DIFF_TERM=TRUE")
    ),
    ("LTC_OUT", 3,  # Bank 2
        Subsignal("a_p", Pins("LPC:LA29_P")),
        Subsignal("a_n", Pins("LPC:LA29_N")),
        Subsignal("b_p", Pins("LPC:LA31_P")),
        Subsignal("b_n", Pins("LPC:LA31_N")),
        IOStandard("LVDS_25"),
        Misc("DIFF_TERM=TRUE")
    ),
    ("LTC_FR", 0,  # Bank 2
        Subsignal("p", Pins("LPC:LA18_CC_P")),
        Subsignal("n", Pins("LPC:LA18_CC_N")),
        IOStandard("LVDS_25"),
        Misc("DIFF_TERM=TRUE")
    ),
    ("LTC_DCO", 0,  # Bank 2
        Subsignal("p", Pins("LPC:LA17_CC_P")),
        Subsignal("n", Pins("LPC:LA17_CC_N")),
        IOStandard("LVDS_25"),
        Misc("DIFF_TERM=TRUE")
    )
]

class LTCPhy(S7_iserdes, AutoCSR):
    def __init__(self, platform, f_sys, f_sample):
        N_CHANNELS = 4
        S = 8  # S = serdes factor
        D = N_CHANNELS * 2 + 1  # D = number of lanes

        # outputs 4 x 14 bit twos complement samples
        self.sample_outs = [Signal((14, True)) for i in range(N_CHANNELS)]

        ###

        # Note: LTC2175 streams the MSB first and needs bit-mirroring
        S7_iserdes.__init__(
            self,
            S=S,
            D=D,
            # OUT0_A / _B and OUT1_A / _B are in a different clock region!
            clock_regions=[0, 0, 0, 0, 1, 1, 1, 1, 1],
        )

        self.pads_dco = platform.request("LTC_DCO")
        self.comb += [
            self.dco_p.eq(self.pads_dco.p),
            self.dco_n.eq(self.pads_dco.n)
        ]
        f_dco_clk = f_sample * 4
        platform.add_period_constraint(self.pads_dco.p, 1e9 / f_dco_clk)

        dat_p = []
        dat_n = []
        for i, sample_out in enumerate(self.sample_outs):  # For each ADC channel
            pads_out = platform.request("LTC_OUT", i)
            # Wire up the input pads to the serial serdes inputs
            dat_p.append(pads_out.a_p)
            dat_p.append(pads_out.b_p)
            dat_n.append(pads_out.a_n)
            dat_n.append(pads_out.b_n)
            # re-arrange parallel serdes outputs to form samples
            # cut the 2 lowest bits of each channel (always zero)
            self.comb += sample_out.eq(Cat(
                myzip(self.data_outs[2 * i + 1], self.data_outs[2 * i])[2:]
            ))
            # CSRs for peeking at data patterns
            # LVDS_B (data_outs[1]) has the LSB and needs to come first!
            n = 'data_peek{:d}'.format(i)
            data_peek = CSRStatus(14, name=n)
            setattr(self, n, data_peek)
            self.specials += MultiReg(
                sample_out,
                data_peek.status
            )

        # Add frame signal to serial inputs
        pads_frm = platform.request("LTC_FR")
        dat_p.append(pads_frm.p)
        dat_n.append(pads_frm.n)
        self.comb += [
            self.lvds_data_p.eq(Cat(dat_p)),
            self.lvds_data_n.eq(Cat(dat_n))
        ]

        # CSRs for peeking at parallelized frame pattern
        self.frame_peek = CSRStatus(S)
        self.specials += MultiReg(
            self.data_outs[-1],
            self.frame_peek.status
        )

        # Frequency counter for received sample clock
        self.submodules.f_sample = FreqMeter(f_sys)

        # CSR for moving a IDELAY2 up / down
        self.idelay_inc = CSR(1)
        self.idelay_dec = CSR(1)
        self.idelay_value = CSR(5)

        # one bitslip control for all ISERDESE2 in all regions
        self.bitslip_csr = CSR(1)

        # Bitslip pulse needs to cross clock domain cleanly!
        self.submodules.ps_bs = PulseSynchronizer("sys", "sample")
        self.comb += [
            self.ps_bs.i.eq(self.bitslip_csr.re),
            self.bitslip.eq(self.ps_bs.o)
        ]

        self.comb += [
            self.f_sample.clk.eq(ClockSignal("sample")),
            self.id_inc.eq(self.idelay_inc.re),
            self.id_dec.eq(self.idelay_dec.re),
            self.idelay_value.w.eq(self.id_value)
        ]
