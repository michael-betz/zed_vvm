"""
Digital signal processing to implement a Vector voltmeter.

try:
    python3 vvm_dsp.py build
"""

from sys import argv
from migen import *
from migen.genlib.misc import timeline
from migen.genlib.cdc import BlindTransfer
from litex.soc.interconnect.csr import AutoCSR, CSRStorage, CSRStatus
from litex.soc.cores.freqmeter import FreqMeter
from os.path import join, dirname, abspath
from dsp.dds import DDS
from dsp.ddc import VVM_DDC
from dsp.tiny_iir import TinyIIR


class VVM_DSP(Module, AutoCSR):
    @staticmethod
    def add_sources(platform):
        vdir = abspath(dirname(__file__))
        DDS.add_sources(platform)

        platform.add_source(join(vdir, "cordicg_b22.v"))
        srcs = [
            "mixer.v",
            "multi_sampler.v", "cic_multichannel.v",
            "serializer_multichannel.v", "reg_delay.v", "ccfilt.v",
            "double_inte_smp.v", "doublediff.v", "serialize.v"
        ]
        for src in srcs:
            platform.add_source(join(vdir, "../../bedrock/dsp", src))

        srcs = [
            "cstageg.v", "addsubg.v"
        ]
        for src in srcs:
            platform.add_source(join(vdir, "../../bedrock/cordic", src))

    def __init__(self, adcs=None):
        """
        adc_*:
            * 14 bit signed inputs
            * twos complement format
            * matched to LTC2175-14

        dsp:
            * complex multiply with 18 bit LO
            *
        """
        self.W_CORDIC = 21
        self.W_PHASE = self.W_CORDIC + 1
        self.W_MAG = self.W_CORDIC

        if adcs is None:
            # Mock input for simulation
            adcs = [Signal((14, True)) for i in range(4)]
        self.adcs = adcs
        n_ch = len(adcs)

        self.mags_iir = [
            Signal((self.W_MAG, False), name='mag') for i in range(n_ch)
        ]
        self.phases_iir = [
            Signal((self.W_PHASE, True), name='phase') for i in range(n_ch)
        ]

        self.iir_shift = Signal(6)

        ###

        # -----------------------------------------------
        #  Digital down-conversion
        # -----------------------------------------------
        self.submodules.ddc = ClockDomainsRenamer('sample')(VVM_DDC(
            adcs=adcs,
            DAVR=4,    # Mixer guard bits
            OSCW=18,   # LO width
            OUT_W=self.W_CORDIC,  # sample stream output width
            DI_W=37,   # CIC integrator width
            PCW=13     # decimation factor width
        ))
        self.ddc.add_csr()
        result_iq_d = Signal.like(self.ddc.result_iq)
        self.sync.sample += result_iq_d.eq(self.ddc.result_iq)

        # -----------------------------------------------
        #  Rectangular to Polar conversion
        # -----------------------------------------------
        mag_out = Signal(self.W_CORDIC)
        phase_out = Signal(self.W_CORDIC + 1)
        self.specials += Instance(
            'cordicg_b22',
            p_nstg=self.W_CORDIC,
            p_width=self.W_CORDIC,
            p_def_op=1,

            i_clk=ClockSignal('sample'),
            i_opin=Constant(1, 2),
            i_xin=result_iq_d,  # I
            i_yin=self.ddc.result_iq,    # Q
            i_phasein=Constant(0, self.W_CORDIC + 1),

            o_xout=mag_out,
            o_phaseout=phase_out
        )
        CORDIC_DEL = self.W_CORDIC + 2

        # -----------------------------------------------
        #  Latch the stream
        # -----------------------------------------------
        # from cordic output at the right time into the right place
        self.strobe = Signal()
        self.strobe_ = Signal()
        self.strobe__ = Signal()
        mags = [Signal.like(self.mags_iir[0]) for i in range(n_ch)]
        phases = [Signal.like(self.phases_iir[0]) for i in range(n_ch)]
        t = []
        # For each mag / phase result
        for i, (m, p) in enumerate(zip(mags, phases)):
            instrs = [m.eq(mag_out)]
            if i == 0:
                instrs.append(p.eq(phase_out))
            else:
                instrs.append(p.eq(phases[0] - phase_out))
            t.append((
                CORDIC_DEL + 2 * i,  # N cycles after self.ddc.result_strobe
                instrs               # ... carry out these instructions
            ))
        t[-1][1].append(self.strobe.eq(1))
        self.sync.sample += [
            self.strobe.eq(0),
            timeline(self.ddc.result_strobe, t),
            self.strobe_.eq(self.strobe),
            self.strobe__.eq(self.strobe_)
        ]

        # -----------------------------------------------
        #  IIR lowpass filter for result averaging
        # -----------------------------------------------
        for i, (m, mi) in enumerate(zip(
            mags + phases,
            self.mags_iir + self.phases_iir
        )):
            # No filter for the reference phase output
            if i == n_ch:
                self.comb += mi.eq(m)
                continue

            w = self.W_MAG if i < n_ch else self.W_PHASE
            # DC error for shift > 31
            iir = ClockDomainsRenamer('sample')(TinyIIR(w))
            self.comb += [
                iir.x.eq(m),
                mi.eq(iir.y),
                iir.shifts.eq(self.iir_shift),
                iir.strobe.eq(self.strobe),
            ]
            self.submodules += iir

    def add_csrs(self, f_sys, p):
        ''' Wire up the config-registers to litex CSRs '''
        # sys clock domain
        n_ch = len(self.adcs)
        self.mags_sys = [
            Signal.like(self.mags_iir[0]) for i in range(n_ch)
        ]
        self.phases_sys = [
            Signal.like(self.phases_iir[0]) for i in range(n_ch)
        ]

        # Clock domain crossing on self.strobe_
        self.submodules.cdc = BlindTransfer(
            "sample",
            "sys",
            n_ch * (self.W_MAG + self.W_PHASE)
        )

        # IIR controls
        self.iir = CSRStorage(len(self.iir_shift))

        self.comb += [
            self.iir_shift.eq(self.iir.storage),
            self.cdc.data_i.eq(Cat(self.mags_iir + self.phases_iir)),
            self.cdc.i.eq(self.strobe__),
            Cat(self.mags_sys + self.phases_sys).eq(self.cdc.data_o)
        ]

        # CSRs for peeking at phase / magnitude values
        for i, sig in enumerate(self.mags_sys + self.phases_sys):
            if i <= 3:
                n = 'mag{:d}'.format(i)
            else:
                n = 'phase{:d}'.format(i - 4)
            csr = CSRStatus(32, name=n)
            setattr(self, n, csr)
            self.comb += csr.status.eq(sig)

        self.submodules.zc = ZeroCrosser(int(100e6))
        self.f_ref_csr = CSRStatus(32)
        self.comb += [
            self.zc.sig_in.eq(self.adcs[0] > 0),
            self.f_ref_csr.status.eq(self.zc.n_zc)
        ]


class ZeroCrosser(Module, AutoCSR):
    def __init__(self, N_CLOCKS):
        '''
        a simple frequency counter, detecting zero crossings
        N_CLOCKS = integration time
        '''
        self.n_zc = Signal(32)  # Number of zero crossings
        self.sig_in = Signal()  # Input signal under test

        # ADC zero crossing frequency counter
        sig_in_ = Signal()
        f_accu = Signal.like(self.n_zc)
        _n_zc_sample = Signal.like(self.n_zc)
        strobe = Signal()
        meas_time = Signal.like(self.n_zc, reset=N_CLOCKS)
        self.sync.sample += [
            strobe.eq(0),
            sig_in_.eq(self.sig_in),
            If(meas_time == 0,
                meas_time.eq(N_CLOCKS),
                _n_zc_sample.eq(f_accu),
                f_accu.eq(0),
                strobe.eq(1)
            ).Else(
                # On positive wavefrom zero crossing
                If(~sig_in_ & self.sig_in,
                    f_accu.eq(f_accu + 1)
                ),
                meas_time.eq(meas_time - 1)
            )
        ]
        self.submodules.cdc = BlindTransfer(
            "sample",
            "sys",
            len(self.n_zc)
        )
        self.comb += [
            self.cdc.data_i.eq(_n_zc_sample),
            self.n_zc.eq(self.cdc.data_o),
            self.cdc.i.eq(strobe)
        ]


def main():
    ''' generate a .v file for simulation with Icarus / general usage '''
    tName = argv[0].replace('.py', '')
    d = VVM_DSP()
    if 'build' in argv:
        from migen.fhdl.verilog import convert
        convert(
            d,
            name=tName,
            ios={
                *d.adcs,
                *d.mags_iir,
                *d.phases_iir,
                d.ddc.cic_period,
                d.ddc.cic_shift,
                d.iir_shift
            },
            display_run=True
        ).write(tName + '.v')


if __name__ == '__main__':
    if len(argv) <= 1:
        print(__doc__)
        exit(-1)
    main()
