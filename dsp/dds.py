'''
Simple DDS
try:
    python3 dds.py build
'''
from sys import argv
from os.path import join, dirname, abspath
from litex.soc.interconnect.csr import AutoCSR, CSRStorage
from migen import *


class DDS(Module, AutoCSR):
    @staticmethod
    def add_sources(platform):
        vdir = abspath(dirname(__file__))
        platform.add_source(join(vdir, "cordicg_b22.v"))

    def __init__(self, N_BITS=18, N_STG=20):
        '''
        DDS with 32 bit accumulator
        and `N` output bits (max = 32)
        Use ClockDomainRenamer to specify the DDS clock
        '''
        # sin, cos outputs
        self.o_sin = Signal((N_BITS, True))
        self.o_cos = Signal((N_BITS, True))

        # Frequency tuning word, f_out = f_clk * ftw / 2**32
        self.ftw = Signal(32, reset=1)

        # Output amplitude
        self.amp = Signal(N_BITS, reset=int((1 << (N_BITS - 1)) / 1.65))
        # a CORDIC engine has an intrinsic gain of about 1.64676
        # (asymptotic value for a large number of stages)

        ###

        self.phase = Signal(32)
        self.sync += self.phase.eq(self.phase + self.ftw)

        self.specials += Instance(
            "cordicg_b22",
            p_nstg=N_STG,
            p_width=N_BITS,
            p_def_op=0,

            i_clk=ClockSignal(),
            i_opin=Constant(0, 2),
            i_xin=self.amp,
            i_yin=Constant(0, N_BITS),
            i_phasein=self.phase[-N_BITS - 1:],

            o_xout=self.o_cos,
            o_yout=self.o_sin
        )

    def add_csr(self):
        self.ftw_csr = CSRStorage(len(self.ftw), reset=0x40059350, name='ftw')
        self.comb += self.ftw.eq(self.ftw_csr.storage)


def main():
    tName = argv[0].replace('.py', '')
    d = DDS()
    if 'build' in argv:
        ''' generate a .v file for simulation with Icarus / general usage '''
        from migen.fhdl.verilog import convert
        convert(
            d,
            ios={
                d.o_sin,
                d.o_cos,
                d.ftw,
                d.amp
            },
            display_run=True
        ).write(tName + '.v')


if __name__ == '__main__':
    if len(argv) <= 1:
        print(__doc__)
        exit(-1)
    main()
