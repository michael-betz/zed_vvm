"""
hello_LTC.py runs on fpga, reads ADC data, waits for a trigger
and then dumps 4096 samples in a buffer.
Buffer is read out through litex_server (etherbone) periodically,
fft'ed and plotted.
"""
from numpy import *
from matplotlib.pyplot import *
from scipy.signal import periodogram
import threading
import argparse
from common import conLitexServer

import sys
sys.path.append("linux/csr_access/py/")
from csr_lib import CsrLibLegacyAdapter
from vvm_helpers import initLTC, initSi570, getSamples


class ScopeController:
    def __init__(self, r):
        self._trigRequest = True
        self._trigLevelRequest = 0
        self._curTrigLevel = None
        self._autoTrigger = True
        self._forceTrig = False
        self.isRunning = True
        self.r = r
        # last 32 blocks of samples for dumping to .npz file
        self.rollBuffer_t = []
        self.rollBuffer_f = []


    def forceTrig(self, e):
        self._forceTrig = True

    def trigLevel(self, l):
        self._trigLevelRequest = int(l * (1 << 13))

    def trigRequest(self, e):
        self._trigRequest = True

    def handleSettings(self):
        if self._curTrigLevel is None or \
           self._curTrigLevel != self._trigLevelRequest:
            self.r.regs.acq_trig_level.write(self._trigLevelRequest)
            self._curTrigLevel = self._trigLevelRequest
            print('trigLevel:', hex(self.r.regs.acq_trig_level.read()))

        if self._trigRequest:
            # print("t")
            self.r.regs.acq_trig_csr.write(1)
            self._trigRequest = False
            return True

        if self._forceTrig:
            self.r.regs.acq_trig_force.write(1)
            self.r.regs.acq_trig_force.write(0)
            self._forceTrig = False
        return False

    def buf_append(buf, val):
        if len(buf) >= args.AVG:
            buf.pop(0)
        else:
            print("Buf:", len(buf))
        buf.append(val)

    def dumpNpz(self, x):
        fName = unique_filename("measurements/dump.npz")
        savez_compressed(fName, dat=vstack(self.rollBuffer_t))
        print("wrote {:} buffers to {:}".format(len(self.rollBuffer_t), fName))
        self.rollBuffer_t.clear()
        self.rollBuffer_f.clear()

    def ani_thread(self):
        tReq = False
        while self.isRunning:
            tReq |= self.handleSettings()

            # wait while acquisition is running
            if r.regs.acq_trig_csr.read() >= 1:
                # print('y', end='', flush=True)
                time.sleep(0.2)
                continue

            # only read data after a new acquisition
            if not tReq:
                # print('x', end='', flush=True)
                time.sleep(0.2)
                continue

            # print('z', end='', flush=True)
            yVect = getSamples(c, args.CH, args.N)
            ScopeController.buf_append(
                self.rollBuffer_t,
                yVect
            )
            f, Pxx = periodogram(
                yVect,
                args.fs,
                window='hanning',
                scaling='spectrum',
                nfft=args.N * 2
            )
            ScopeController.buf_append(
                self.rollBuffer_f,
                Pxx
            )
            spect = 10 * log10(mean(self.rollBuffer_f, 0)) + 3
            lt.set_ydata(yVect)
            lf.set_ydata(spect)
            fig.canvas.draw_idle()

            tReq = False

            # Start next acquisition
            if self._autoTrigger:
                self.trigRequest(None)


def plotNpz(fNames, labels=None, ax=None, fs=120e6, *args, **kwargs):
    """
    plot a .npz dump from scope_app.py
    args, kwargs are passed to plot()
    """
    if ax is None:
        fig, ax = subplots(figsize=(9, 5))
    else:
        fig = gcf()
    if labels is None:
        labels = fNames
    for fName, label in zip(fNames, labels):
        if fName == "fullscale":
            d = sin(arange(4095))
            dat = vstack([d, d])
        else:
            dat = load(fName)["dat"]
        f, Pxx = periodogram(dat, fs, window='hanning', scaling='spectrum', nfft=2**15)
        plot(f / 1e6, 10*log10(mean(Pxx, 0)) + 3, label=label, *args, **kwargs)
    ax.legend()
    ax.set_xlabel("Frequency [MHz]")
    ax.set_ylabel("[db_fs]")
    fig.tight_layout()


def main():
    global fig, lt, lf, r, c, args, rollBuffer_t
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--N", default=1024, type=int, help="Number of samples per acquisition"
    )
    parser.add_argument(
        "--AVG", default=8, type=int, help="How many buffers to average the spectrum"
    )
    parser.add_argument(
        "--CH", default=0, choices=[0, 1, 2, 3], type=int, help="Which channel to plot"
    )
    parser.add_argument(
        "--fs", default=117.6e6, type=float, help="ADC sample rate [MHz]. Must match hello_LTC.py setting."
    )
    parser.add_argument(
        "--noinit", action='store_true', help="Do not initialize the hardware."
    )
    args = parser.parse_args()
    # ----------------------------------------------
    #  Init hardware
    # ----------------------------------------------
    r = conLitexServer('../build/csr.csv')
    c = CsrLibLegacyAdapter(r)
    print("fs = {:6f} MHz, should be {:6f} MHz".format(
        r.regs.lvds_f_sample_value.read() / 1e6, args.fs / 1e6
    ))
    if not args.noinit:
        # initSi570(c, 117.6e6)  # Bitbanging over ethernet is too slow :(
        initLTC(c, False)
    r.regs.acq_trig_channel.write(args.CH)

    # ----------------------------------------------
    #  Setup Matplotlib
    # ----------------------------------------------
    sc = ScopeController(r)
    fig, axs = subplots(2, 1, figsize=(10, 6))
    xVect = linspace(0, args.N / args.fs, args.N, endpoint=False)
    yVect = zeros_like(xVect)
    yVect[:2] = [-1, 1]
    f, Pxx = periodogram(yVect, args.fs, nfft=args.N * 2)
    lt, = axs[0].plot(xVect * 1e9, yVect, drawstyle='steps-post')
    lf, = axs[1].plot(f / 1e6, Pxx)
    axs[0].set_xlabel("Time [ns]")
    axs[1].set_xlabel("Frequency [MHz]")
    axs[0].set_ylabel("ADC value [FS]")
    axs[1].set_ylabel("ADC value [dB_FS]")
    axs[0].axis((-100, 8300, -1, 1))
    axs[1].axis((-0.5, 63, -110, -10))

    # GUI slider for trigger level
    sfreq = Slider(
        axes([0.13, 0.9, 0.72, 0.05]),
        'Trigger level',
        -1, 1, -0.001,
        '%1.3f'
    )
    sfreq.on_changed(sc.trigLevel)

    # Checkboxes
    check = Button(axes([0.05, 0.01, 0.2, 0.05]), "Force trigger")
    check.on_clicked(sc.forceTrig)

    # # Single acquisition button
    # bSingle = Button(axes([0.25, 0.01, 0.2, 0.05]), 'Single trig.')
    # bSingle.on_clicked(sc.trigRequest)

    # Buffer dump button
    bDump = Button(axes([0.25, 0.01, 0.2, 0.05]), 'Dump .npz')
    bDump.on_clicked(sc.dumpNpz)

    threading.Thread(target=sc.ani_thread).start()
    show()
    sc.isRunning = False


if __name__ == '__main__':
    main()
