"""
Runs on a Zedboard (Zynq)

The Programmable Logic (PL) interfaces to an LTC2175 through 8 LVDS lanes.
It uses the Zynq AXI interface (GP0) to make its litex
CSR's accessible.

The Processing System (PS) runs debian and can re-program the PL with a
.bit.bin file

They do speak to each other through litex CSRs and `comm_devmem.py`.

try:
 python3 hello_LTC.py <build / synth / config>
"""
from migen import *
from litex.build.generic_platform import *
from litex.soc.interconnect.csr import *
from litex.soc.integration.soc_zynq import *
from litex.soc.integration.builder import *
from migen.genlib.cdc import MultiReg
from migen.genlib.resetsync import AsyncResetSynchronizer
from litex.soc.cores import dna, spi_old
from litex.boards.platforms import zedboard
from litex.soc.cores.clock import S7MMCM, S7IDELAYCTRL
from litex.soc.interconnect import wishbone
from iserdes.ltc_phy import LTCPhy, ltc_pads
from util.common import main, LedBlinker
from dsp.acquisition import Acquisition
from dsp.vvm_dsp import VVM_DSP


class _CRG(Module):
    def __init__(self, platform, sys_clk_freq, add_rst=None):
        '''
        The `cursor UP` button resets the sys clock domain!

        add_rst = additional reset signals for sys_clk
          must be active high and will be synchronized with sys_clk
        '''
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_clk200 = ClockDomain()

        # # #

        self.cd_sys.clk.attr.add('keep')

        self.submodules.pll = pll = S7MMCM(speedgrade=-1)
        pll.register_clkin(ClockSignal('sys'), 100e6)
        self.comb += [
            pll.reset.eq(ResetSignal('sys'))
        ]

        pll.create_clkout(self.cd_clk200, 200e6)
        self.submodules.idelayctrl = S7IDELAYCTRL(self.cd_clk200)

        rst_sum = Signal()
        if add_rst is not None:
            self.comb += rst_sum.eq(platform.request('user_btn_u') | add_rst)
        else:
            self.comb += rst_sum.eq(platform.request('user_btn_u'))
        self.specials += AsyncResetSynchronizer(self.cd_sys, rst_sum)

        # !!! sys_clk is provided by FCLK_CLK0 from PS7 !!!
        # pll.create_clkout(self.cd_sys, sys_clk_freq)

        # Flashy Led blinker for sample_clk
        bl = LedBlinker(
            125e6 / 8,
            Cat([platform.request('user_led', i) for i in range(8)])
        )
        self.submodules.sample_blink = ClockDomainsRenamer("sample")(bl)


# create our soc (no soft-cpu, wishbone <--> AXI <--> Zynq PS)
class HelloLtc(SoCZynq, AutoCSR):
    csr_peripherals = [
        "dna",
        "spi",
        "lvds",
        "acq",
        "analyzer",
        "f_clk100",
        "vvm"
    ]

    def __init__(self, f_sys, f_sample, **kwargs):
        '''
            f_sys: system clock frequency (wishbone)
            f_sample: ADC sampling clock frequency (provided by )
        '''
        SoCZynq.__init__(
            self,
            clk_freq=f_sys,
            ps7_name="processing_system7_0",
            # cpu_type=None,
            csr_data_width=32,
            # csr_address_width=16,
            with_uart=False,
            with_timer=False,
            integrated_rom_size=0,
            integrated_main_ram_size=0,
            integrated_sram_size=0,
            ident="Zedboard RF vector volt-meter",
            ident_version=True,
            add_reset=False,
            **kwargs
        )
        p = self.platform
        for c in HelloLtc.csr_peripherals:
            self.add_csr(c)

        # FPGA identification
        self.submodules.dna = dna.DNA()

        # AXI interface to zynq PS
        self.add_gp0()
        self.add_axi_to_wishbone(self.axi_gp0, base_address=0x40000000)

        # ----------------------------
        # FPGA clock and reset generation
        # ----------------------------
        self.submodules.crg = _CRG(
            p,
            f_sys,
            ~self.fclk_reset0_n
        )

        # ----------------------------
        #  LTC LVDS driver on FMC-LPC
        # ----------------------------
        p.add_extension(ltc_pads)
        # LTCPhy will recover ADC clock and drive `sample` clock domain
        self.submodules.lvds = LTCPhy(p, f_sys, f_sample)
        # tell vivado that sys_clk and sampl_clk are asynchronous
        p.add_false_path_constraints(
            self.crg.cd_sys.clk,
            self.lvds.pads_dco
        )

        # ----------------------------
        #  SPI bit-bang master
        # ----------------------------
        spi_pads = p.request("LTC_SPI")
        self.submodules.spi = spi_old.SPIMaster(spi_pads)

        # ----------------------------
        #  4 x Acquisition memory for ADC data
        # ----------------------------
        mems = []
        for i, sample_out in enumerate(self.lvds.sample_outs):
            mem = Memory(14, 4096)
            mems.append(mem)
            self.specials += mem
            self.submodules.sample_ram = wishbone.SRAM(mem, read_only=True)
            self.register_mem(
                "sample{}".format(i),
                0x10000000 + i * 0x01000000,  # [bytes]
                self.sample_ram.bus,
                mem.depth * 4  # [bytes]
            )

        # ----------------------------
        #  DSO Trigger logic
        # ----------------------------
        self.submodules.acq = Acquisition(
            mems,
            self.lvds.sample_outs,
            N_BITS=14
        )
        self.specials += MultiReg(
            p.request("user_btn_c"), self.acq.trigger
        )

        # ----------------------------
        #  Vector volt-meter
        # ----------------------------
        VVM_DSP.add_sources(p)
        self.submodules.vvm = VVM_DSP(self.lvds.sample_outs)
        self.vvm.add_csrs(f_sys)

        # -------------------------------------------------------
        #  Forward some PS EMIO to actual pads in the real world
        # -------------------------------------------------------
        p.add_extension([
            (
                "PMODA_SPI",
                0,
                Subsignal("cs_n", Pins("pmoda:5")),
                Subsignal("mosi", Pins("pmoda:7")),
                Subsignal("clk", Pins("pmoda:6")),
                # OLED does not have a MISO pin :(
                IOStandard("LVCMOS25")
            ), (
                "PMODA_GPIO",
                0,
                Subsignal("gpio", Pins("pmoda:0 pmoda:1 pmoda:2 pmoda:3 pmoda:4")),
                IOStandard("LVCMOS25")
            )
        ])
        # SPI0 from PS through EMIO to PMODA
        self.add_emio_spi(p.request("PMODA_SPI"), n=0)
        # GPIO
        self.add_emio_gpio(p.request("PMODA_GPIO").gpio)


if __name__ == '__main__':
    soc = HelloLtc(
        platform=zedboard.Platform(),
        # Needs to match Vivado IP,
        # Clock Configuration --> PL Fabric Clocks --> FCLK_CLK0
        f_sys=int(100e6),
        f_sample=int(117.6e6)
    )
    vns = main(soc, doc=__doc__)
