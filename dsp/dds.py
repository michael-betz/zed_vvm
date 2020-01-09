'''
Simple DDS
try:
    python3 dds.py build
'''
from sys import argv
from os.path import join, dirname, abspath
from litex.soc.interconnect.csr import AutoCSR, CSRStorage, CSRStatus, CSRField
from migen.genlib.cdc import PulseSynchronizer
from migen import *


class DDS(Module, AutoCSR):
    @staticmethod
    def add_sources(platform):
        vdir = abspath(dirname(__file__))
        platform.add_source(join(vdir, "cordicg_b22.v"))

    def __init__(self, N_CH=1, N_BITS=18, N_STG=20):
        '''
        DDS with 32 bit accumulator
        and `N` output bits (max = 32)
        Use ClockDomainRenamer to specify the DDS clock
        '''
        # sin, cos outputs
        self.o_sins = [Signal((N_BITS, True)) for i in range(N_CH)]
        self.o_coss = [Signal((N_BITS, True)) for i in range(N_CH)]

        # Frequency tuning words, f_out = f_clk * ftw / 2**32
        self.ftws = [Signal(32, reset=1) for i in range(N_CH)]

        # Output amplitudes
        self.AMP_VAL = int((1 << (N_BITS - 1)) / 1.65)
        self.amps = [Signal(N_BITS, reset=self.AMP_VAL) for i in range(N_CH)]
        # a CORDIC engine has an intrinsic gain of about 1.64676
        # (asymptotic value for a large number of stages)

        self.reset_phase = Signal()
        self.update_ftw = Signal()

        ###

        for o_sin, o_cos, ftw, amp in zip(
            self.o_sins, self.o_coss, self.ftws, self.amps
        ):
            phase = Signal(32)
            ftw_ = Signal.like(ftw)

            self.sync += [
                If(self.update_ftw, ftw_.eq(ftw)),
                If(self.reset_phase,
                    phase.eq(0)
                ).Else(
                    phase.eq(phase + ftw_)
                )
            ]

            self.specials += Instance(
                "cordicg_b22",
                p_nstg=N_STG,
                p_width=N_BITS,
                p_def_op=0,

                i_clk=ClockSignal(),
                i_opin=Constant(0, 2),
                i_xin=amp,
                i_yin=Constant(0, N_BITS),
                i_phasein=phase[-N_BITS - 1:],

                o_xout=o_cos,
                o_yout=o_sin
            )

        self.ftw_ = ftw_

    def _csr_helper(self, name, regs, cdc=False, pulsed=False, **kwargs):
        '''
        handle csr + optional clock domain crossing (cdc) from sys to sample

        cdc:    add a pulse synchronizer to move the csr write strobe to the
                sample domain, then use the strobe to latch csr.storage

        pulsed: instead of latching csr.storage in the sample clock domain,
                make its value valid only for one cycle and zero otherwise
        '''
        for i, reg in enumerate(regs):
            n = name
            if len(regs) > 1:
                n += str(i)
            csr = CSRStorage(len(reg), name=n, **kwargs)
            setattr(self, n, csr)
            if cdc:
                # csr.storage is fully latched and stable when csr.re is pulsed
                # hence we only need to cross the csr.re pulse into the sample
                # clock domain and then latch csr.storage there once more
                ps = PulseSynchronizer('sys', 'sample')
                setattr(self.submodules, name + '_sync', ps)
                self.comb += ps.i.eq(csr.re)
                if pulsed:
                    self.sync.sample += reg.eq(Mux(ps.o, csr.storage, 0))
                else:
                    self.sync.sample += If(ps.o, reg.eq(csr.storage))
            else:
                if pulsed:
                    self.comb += reg.eq(Mux(csr.re, csr.storage, 0))
                else:
                    self.comb += reg.eq(csr.storage)

    def add_csr(self):
        self._csr_helper('amp', self.amps, cdc=True, reset=self.AMP_VAL)
        # Don't need CDC as the FTWs are only latched when update_ftw is pulsed
        self._csr_helper('ftw', self.ftws)
        # DDS_ctrl, action takes place on register write
        # bits:    1 = update_ftw, 0 = reset_phase
        self._csr_helper(
            'ctrl',
            [Cat(self.reset_phase, self.update_ftw)],
            cdc=True,
            pulsed=True
        )


def main():
    tName = argv[0].replace('.py', '')
    d = DDS(2)
    if 'build' in argv:
        ''' generate a .v file for simulation with Icarus / general usage '''
        from migen.fhdl.verilog import convert
        convert(
            d,
            ios={
                *d.o_sins,
                *d.o_coss,
                *d.ftws,
                *d.amps
            },
            display_run=True
        ).write(tName + '.v')


if __name__ == '__main__':
    if len(argv) <= 1:
        print(__doc__)
        exit(-1)
    main()
