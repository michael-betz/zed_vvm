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
from scope_app import initLTC, unique_filename
from common import *


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--N", default=1024, type=int,
        help="Number of points to plot"
    )
    parser.add_argument(
        "--fcenter", default=500.3e6, type=float,
        help="Digital down-conversion center frequency"
    )
    parser.add_argument(
        "--deci", default=100, type=float,
        help="Digital down-conversion decimation factor"
    )
    parser.add_argument(
        "--iir", default=15, type=int,
        help="IIR filter for result averaging. Smoothing factor from 0 - 15."
    )
    args = parser.parse_args()
    # ----------------------------------------------
    #  Init hardware
    # ----------------------------------------------
    r = conLitexServer('../build/csr.csv')
    initLTC(r, True)

    # Frequency / bandwidth setting
    fSample = r.regs.lvds_f_sample_value.read()
    ftw = int(((args.fcenter / fSample) % 1) * 2**32)
    r.regs.vvm_ddc_ftw.write(ftw)
    r.regs.vvm_ddc_deci.write(args.deci)

    # Throw away N bits after CIC to avoid saturation with large deci factors
    # This will change the scaling!
    r.regs.vvm_ddc_shift.write(0)

    # IIR result averaging filter smoothing factor (0 - 15)
    r.regs.vvm_iir.write(args.iir)

    print('ddc_ftw', hex(r.regs.vvm_ddc_ftw.read()))
    print('f_sample', fSample)
    print('ddc_deci', r.regs.vvm_ddc_deci.read())
    print('bw', fSample / args.deci)
    print('iir_shift', r.regs.vvm_iir.read())

    # ----------------------------------------------
    #  Setup Matplotlib
    # ----------------------------------------------
    fig, axs = subplots(2, sharex=True, figsize=(9,7))
    datms = zeros((args.N, 4))
    datps = zeros((args.N, 3))
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
    axs[0].set_ylabel("Magnitude [dB FS]")
    for ax in axs:
        ax.set_xlim(0, args.N)
        ax.set_xlabel("Sample #")
        ax.legend(loc="upper left")
    ax.set_ylim(-180, 180)
    ax.set_ylabel("Phase [deg]")
    fig.tight_layout()

    def upd(i):
        datms[:] = roll(datms, -1, 0)
        datps[:] = roll(datps, -1, 0)
        for i in range(4):
            val = getattr(r.regs, "vvm_mag{}".format(i)).read() / (1 << 21)
            datms[-1, i] = val
            lms[i].set_data(arange(datms.shape[0]), 20 * log10(datms[:, i]))

        for i in range(3):
            val = getattr(r.regs, "vvm_phase{}".format(i + 1)).read()
            val = getInt32(val) / (1 << 21) * 180
            datps[-1, i] = val
            lps[i].set_data(arange(datps.shape[0]), datps[:, i])

    def dumpNpz(x):
        fName = unique_filename("measurements/vvm_dump.npz")
        savez_compressed(fName, datms=datms, datps=datps)
        print("wrote {:} measurements to {:}".format(datms.shape[0], fName))

    # Buffer dump button
    bDump = Button(axes([0.005, 0.005, 0.1, 0.04]), 'Dump .npz')
    bDump.on_clicked(dumpNpz)

    ani = FuncAnimation(fig, upd, interval=100)
    show()

if __name__ == '__main__':
    main()
