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
from operator import or_
from functools import reduce

from migen import *
from migen.genlib.cdc import MultiReg
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.misc import WaitTimer
from litex.build.generic_platform import *
from litex.soc.interconnect.csr import *
from litex.soc.integration.soc_zynq import *
from litex.soc.integration.builder import *
from litex.soc.cores import dna
from litex.soc.cores.bitbang import I2CMaster, SPIMaster
from litex.boards.platforms import zedboard
from litex.soc.cores.clock import S7MMCM, S7IDELAYCTRL
from litex.soc.interconnect import wishbone

from common import main, LedBlinker
from iserdes.ltc_phy import LTCPhy, ltc_pads
from dsp.acquisition import Acquisition
from dsp.vvm_dsp import VVM_DSP


class _CRG(Module):
    def __init__(self, platform, f_sys, f_sample, add_rst=[]):
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
        self.comb += rst_sum.eq(reduce(or_, add_rst))
        self.specials += AsyncResetSynchronizer(self.cd_sys, rst_sum)

        # !!! sys_clk is provided by FCLK_CLK0 from PS7 !!!
        # pll.create_clkout(self.cd_sys, f_sys)

        # Flashy Led blinker for sample_clk
        bl = LedBlinker(
            f_sample / 8,
            Cat([platform.request('user_led', i) for i in range(8)])
        )
        self.submodules.sample_blink = ClockDomainsRenamer("sample")(bl)


class Si570(Module, AutoCSR):
    def __init__(self, p, soc):
        # -------------------------------------------------------
        #  Si570 Pmod
        # -------------------------------------------------------
        # Connect Si570 (sample clk) to I2C master
        p.add_extension([(
            "SI570_I2C",
            0,
            Subsignal("oe", Pins("pmodb:5")),
            Subsignal("scl", Pins("pmodb:6")),
            Subsignal("sda", Pins("pmodb:7")),
            IOStandard("LVCMOS33")
        )])
        si570_pads = p.request("SI570_I2C")

        # soc.add_emio_i2c(si570_pads, 0)  # PS I2C0
        self.submodules.i2c = I2CMaster(si570_pads)  # Litex bit-bang

        self.si570_oe = CSRStorage(1, reset=1, name="si570_oe")
        self.comb += si570_pads.oe.eq(self.si570_oe.storage)


# create our soc (no soft-cpu, wishbone <--> AXI <--> Zynq PS)
class ZedVvm(SoCZynq):
    csr_peripherals = [
        "dna",
        "spi",
        "lvds",
        "acq",
        "analyzer",
        "f_clk100",
        "vvm",
        "si570"
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
        for c in ZedVvm.csr_peripherals:
            self.add_csr(c)

        p = self.platform
        p.add_extension([
            (
                "PMODA_SPI",
                0,
                Subsignal("cs_n", Pins("pmoda:5")),
                Subsignal("clk", Pins("pmoda:6")),
                Subsignal("mosi", Pins("pmoda:7")),
                # OLED does not have a MISO pin :(
                IOStandard("LVCMOS33")
            ), (
                "PMODA_GPIO",
                0,
                Subsignal(
                    "gpio",
                    Pins("pmoda:0 pmoda:1 pmoda:2 pmoda:3 pmoda:4")
                ),
                IOStandard("LVCMOS33")
            )
        ])

        # FPGA identification
        self.submodules.dna = dna.DNA()

        # AXI interface to zynq PS
        self.add_gp0()
        self.add_axi_to_wishbone(self.axi_gp0, base_address=0x40000000)

        # ----------------------------
        #  FPGA clock and reset generation
        # ----------------------------
        # Delay the CSR reset signal such that wishbone can send an ACK
        # to the Zynq PS, which would freeze up otherwise
        csr_reset_active = Signal()
        self.sync += If(self.ctrl.reset, csr_reset_active.eq(1))
        self.submodules.rst_delay = WaitTimer(2**16)  # 655 us
        self.comb += self.rst_delay.wait.eq(csr_reset_active)
        self.submodules.crg = _CRG(
            p,
            f_sys,
            f_sample,
            [
                ~self.fclk_reset0_n,  # Zynq PS reset signal (bitfile load)
                p.request('user_btn_u'),  # UP button on zedboard
                self.rst_delay.done  # ctrl_reset csr (delayed by 100 ms)
            ]
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
        self.submodules.spi = SPIMaster(spi_pads)

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
        self.vvm.add_csr(f_sys, p)

        # -------------------------------------------------------
        #  OLED display / PS GPIOs / Si570
        # -------------------------------------------------------
        # Forward the internal PS EMIO to actual pads in the real world
        # SPI0, SS0 from PS through EMIO to PMODA
        self.add_emio_spi(p.request("PMODA_SPI"), n=0)

        # GPIOs to PMODA
        self.add_emio_gpio(p.request("PMODA_GPIO").gpio)

        # On board tiny OLED display
        p.add_oled(self, SPI_N=0, SS_N=1, DC_GPIO=8, RST_GPIO=9)

        # Si570 I2C module
        self.submodules.si570 = Si570(p, self)


if __name__ == '__main__':
    soc = ZedVvm(
        platform=zedboard.Platform(),
        # Needs to match Vivado IP,
        # Clock Configuration --> PL Fabric Clocks --> FCLK_CLK0
        f_sys=int(100e6),
        f_sample=int(117.6e6)
    )
    vns = main(soc, doc=__doc__)
