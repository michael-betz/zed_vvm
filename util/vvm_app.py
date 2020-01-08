"""
Plots a live magnitude / phase trace over time

FPGA reads ADC data,
down-converts,
calculates MG / phase,
filters it
and provides it to python as CSR

This script reads the CSRs at regular intervals and plots them.
"""
from numpy import *
from matplotlib.pyplot import *
from matplotlib.animation import FuncAnimation
import argparse
from common import conLitexServer, unique_filename

import sys
sys.path.append("linux/csr_access/py/")
from csr_lib import CsrLibLegacyAdapter
from vvm_helpers import initLTC, initSi570, meas_f_ref, twos_comps, MagCal,\
    getMags, getPhases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--N", default=1024, type=int,
        help="Number of points to plot"
    )
    parser.add_argument(
        "--deci", default=100, type=int,
        help="Digital down-conversion decimation factor"
    )
    parser.add_argument(
        "--ddcshift", default=2, type=int,
        help="Bits to discard after down conversion to prevent overflow"
    )
    parser.add_argument(
        "--iir", default=10, type=int,
        help="IIR filter for result averaging. Smoothing factor from 0 - 15."
    )
    parser.add_argument(
        "--fs", default=117.6e6, type=float,
        help="ADC sample rate [MHz]. Must match hello_LTC.py setting."
    )
    parser.add_argument(
        "--noinit", action='store_true',
        help="Do not initialize the hardware."
    )
    parser.add_argument(
        "--f_meas", default=499.6e6, type=float,
        help="Frequency of signal under test [Hz]."
    )
    args = parser.parse_args()

    # ----------------------------------------------
    #  Load calibration
    # ----------------------------------------------
    cal = MagCal('cal/cal1.npz')

    # ----------------------------------------------
    #  Init hardware
    # ----------------------------------------------
    r = conLitexServer('../build/csr.csv')
    c = CsrLibLegacyAdapter(r)

    if not args.noinit:
        initLTC(c, False)

    # Frequency / bandwidth setting
    print("fs = {:6f} MHz, should be {:6f} MHz".format(
        r.regs.lvds_f_sample_value.read() / 1e6, args.fs / 1e6
    ))

    r.regs.vvm_ddc_deci.write(args.deci)

    # Throw away N bits after CIC to avoid saturation with large deci factors
    # This will change the scaling!
    r.regs.vvm_ddc_shift.write(args.ddcshift)

    # IIR result averaging filter smoothing factor (0 - 15)
    r.regs.vvm_iir.write(args.iir)

    print('ddc_ftw', hex(r.regs.vvm_ddc_dds_ftw0.read()))
    print('ddc_deci', r.regs.vvm_ddc_deci.read())
    print('ddc_shift', r.regs.vvm_ddc_shift.read())
    print('bw', args.fs / args.deci)
    print('iir_shift', r.regs.vvm_iir.read())

    # ----------------------------------------------
    #  Setup Matplotlib
    # ----------------------------------------------
    fig, axs = subplots(2, sharex=True, figsize=(9, 7))
    datms = ones((args.N, 4)) * NaN
    datps = ones((args.N, 3)) * NaN
    lms = []
    lps = []
    for i in range(datms.shape[1]):
        l, = axs[0].plot([], [], label="MAG{}".format(i))
        lms.append(l)

    next(axs[1]._get_lines.prop_cycler)
    for i in range(datps.shape[1]):
        l, = axs[1].plot([], [], label="PHS{}".format(i + 1))
        lps.append(l)

    axs[0].set_ylim(-80, 0)
    axs[0].set_ylabel("Power [dBm]")
    for ax in axs:
        ax.set_xlim(0, args.N)
        ax.set_xlabel("Sample #")
        ax.legend(loc="upper left")
    ax.set_ylim(-180, 180)
    ax.set_ylabel("Phase [deg]")
    fig.tight_layout()

    def upd(frm):
        datms[:] = roll(datms, -1, 0)
        datps[:] = roll(datps, -1, 0)

        mags = getMags(r, args.ddcshift)
        datms[-1, :] = mags  # + cal.get_mag_cal(args.f_meas)
        for i in range(4):
            lms[i].set_data(arange(datms.shape[0]), datms[:, i])

        datps[-1, :] = getPhases(r)
        for i, p in enumerate(datps[-1, :]):
            if mags[i + 1] < -80:
                datps[-1, i] = NaN
            lps[i].set_data(arange(datps.shape[0]), datps[:, i])

        # if (frm % 500) == 0:
        if frm == 0:
            # f_ref = meas_f_ref(c, args.fs)
            f_ref = args.f_meas
            ftw = int(((f_ref / args.fs) % 1) * 2**32)
            for i, mult in enumerate((1, 1, 1, 1)):
                ftw_ = int(ftw * mult)
                print("f_center_{} at {:6f} MHz".format(
                    i, ftw_ / 2**32 * args.fs / 1e6
                ))
                getattr(r.regs, 'vvm_ddc_dds_ftw{}'.format(i)).write(ftw_)
                if i > 0:
                    getattr(r.regs, 'vvm_pp_mult{}'.format(i)).write(mult)
            r.regs.vvm_ddc_dds_ctrl.write(0x2 | (frm == 0))  # FTW_UPDATE, RST


    def dumpNpz(x):
        fName = unique_filename("measurements/vvm_dump.npz")
        savez_compressed(fName, datms=datms, datps=datps)
        print("wrote {:} measurements to {:}".format(datms.shape[0], fName))

    # Buffer dump button
    bDump = Button(axes([0.005, 0.005, 0.1, 0.04]), 'Dump .npz')
    bDump.on_clicked(dumpNpz)

    ani = FuncAnimation(fig, upd, interval=50)
    show()

if __name__ == '__main__':
    main()
