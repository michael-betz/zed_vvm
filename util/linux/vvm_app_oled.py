#!/usr/bin/python3
'''
display phase / magnitude on the OLED screen
'''
import sys
import signal
from time import sleep
from numpy import log10
from os import putenv
from socket import gethostname
from datetime import datetime
from random import randint, choice
import pygame as pg
from pygame.draw import ellipse, rect
from evdev import InputDevice
import argparse

sys.path.append('./csr_access/py')
from csr_lib import hd, CsrLib
from bitbang import I2C
from vvm_helpers import initLTC, initSi570, twos_comps, meas_f_ref, \
    CalHelper, getNyquist, getRealFreq


class VvmApp:
    def __init__(self, args, c):
        self.args = args
        self.c = c
        self.nyquist_band = args.nyquist_band
        self.M = (1, 1, 1)  # Measurement harmonic

        # ----------------------------------------------
        #  Load calibration
        # ----------------------------------------------
        self.cal = CalHelper(args.cal_file, args.ddcshift, c, args.fs)

        putenv('SDL_NOMOUSE', '')
        putenv('SDL_FBDEV', '/dev/fb1')
        putenv('SDL_FBACCEL', '0')
        putenv('SDL_VIDEODRIVER', 'fbcon')

        pg.display.init()
        pg.font.init()
        pg.mouse.set_visible(False)
        self.d = pg.display.set_mode()  # returns the display surface

        fntNames = ('Ubuntu-Regular', 'UbuntuMono-Bold')
        fntSizes = (17, 28)
        self.fnts = [pg.font.Font('oled/fonts/{}.ttf'.format(n), s) for n, s in zip(fntNames, fntSizes)]

        self.dev_rot = InputDevice('/dev/input/event0')
        self.dev_push = InputDevice('/dev/input/event1')

    def draw(self, frm=0):
        self.d.fill((0x00, ) * 3)
        self.f_ref_bb = meas_f_ref(self.c, self.args.fs)
        f_ref = getRealFreq(self.nyquist_band, self.f_ref_bb, self.args.fs)

        mags = self.cal.get_mags(f_ref)
        phases = self.cal.get_phases(f_ref)

        # ----------------------
        #  Draw numbers on OLED
        # ----------------------
        # Reference frequency / power
        f0 = self.fnts[0]
        s_ = 'REF: {:8.4f} MHz,  {:5.1f} dBm'.format(f_ref / 1e6, mags[0])
        sur = f0.render(s_, True, (0x88,) * 3)
        self.d.blit(sur, (0, 0))

        # 3 x phase
        for i in range(3):
            if mags[i + 1] > -60:
                _s = '{:>6.1f}'.format(phases[i])
            else:
                _s = '{:>6s}'.format('.....')
            sur = self.fnts[1].render(_s, True, (0xFF,) * 3)
            self.d.blit(sur, (-3 + i * 80, 20))

        # 3 x power
        for i in range(3):
            s_ = '{:>5.1f} dBm'.format(mags[i + 1])
            sur = f0.render(s_, True, (0x88,) * 3)
            self.d.blit(sur, (i * 82, 48))

        # ------------------
        #  Handle user input
        # ------------------
        rot, btn = self.handle_input()

        n = self.nyquist_band + rot
        n = 0 if n < 0 else 13 if n > 13 else n
        self.nyquist_band = n

        if ((frm % 1000) == 0) or btn:
            self.tune()

    def tune(self):
        '''
        set down-converter center frequency to value measured by the
        frequency counter on the REF channel
        '''
        fs = self.args.fs
        ftw = int((self.f_ref_bb / fs) * 2**32)
        c = self.c
        for i, mult in enumerate((1, ) + self.M):
            ftw_ = int(ftw * mult)
            c.write_reg('vvm_ddc_dds_ftw' + str(i), ftw_)
            if i > 0:
                c.write_reg('vvm_pp_mult' + str(i), mult)
        print("f_ref at {:6f} MHz".format(self.f_ref_bb / 1e6))
        c.write_reg('vvm_ddc_dds_ctrl', 0x02)  # FTW update

    def handle_input(self):
        ''' returns encoder steps and button pushes '''
        rot = 0
        btn = False
        try:
            for evt in self.dev_rot.read():
                if evt.type == 2:
                    rot += evt.value
        except BlockingIOError:
            pass
        try:
            for evt in self.dev_push.read():
                btn |= evt.value
        except BlockingIOError:
            pass
        return rot, btn


def handler(signum, frame):
    """Why is systemd sending sighups? I DON'T KNOW."""
    print("Got a {} signal. Doing nothing".format(signum))


def main():
    signal.signal(signal.SIGHUP, handler)
    # signal.signal(signal.SIGTERM, handler)
    # signal.signal(signal.SIGCONT, handler)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--deci', default=100, type=int,
        help='Digital down-conversion decimation factor'
    )
    parser.add_argument(
        '--ddcshift', default=2, type=int,
        help='Bits to discard after down conversion to prevent overflow'
    )
    parser.add_argument(
        '--iir', default=10, type=int,
        help='IIR filter for result averaging. Smoothing factor from 0 - 15.'
    )
    parser.add_argument(
        '--fs', default=117.6e6, type=float,
        help='ADC sample rate [MHz]. Must match hello_LTC.py setting.'
    )
    parser.add_argument(
        '--cal_file', default='cal2_att.npz',
        help='Amplitude / Phase calibration file'
    )
    parser.add_argument(
        '--nyquist_band', default=8, type=int,
        help='Initial nyquist band (N * fs / 2)'
    )
    args = parser.parse_args()


    with CsrLib(0x40000000, 'csr.json') as c:
        print(c.get_ident())

        initSi570(c, args.fs)
        initLTC(c, check_align=True)

        # Frequency / bandwidth setting
        print('fs = {:6f} MHz, should be {:6f} MHz'.format(
            c.read_reg('lvds_f_sample_value') / 1e6, args.fs / 1e6
        ))

        c.write_reg('vvm_ddc_deci', args.deci)

        # Throw away N bits after CIC
        # to avoid saturation with large deci factors
        # This will change the scaling!
        c.write_reg('vvm_ddc_shift', args.ddcshift)

        # IIR result averaging filter smoothing factor (0 - 15)
        c.write_reg('vvm_iir', args.iir)

        # Reset DDS phase accumulators of down-converter
        c.write_reg('vvm_ddc_dds_ctrl', 0x01)

        print('ddc_ftw', hex(c.read_reg('vvm_ddc_dds_ftw0')))
        print('f_sample', args.fs)
        print('ddc_deci', c.read_reg('vvm_ddc_deci'))
        print('ddc_shift', c.read_reg('vvm_ddc_shift'))
        print('BW', args.fs / args.deci / 1e6, 'MHz')
        print('iir_shift', c.read_reg('vvm_iir'))

        app = VvmApp(args, c)
        sleep(1)

        i = 0
        while True:
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    pg.quit()

            app.draw(i)
            pg.display.update()

            i += 1
            pg.time.delay(50)


if __name__ == '__main__':
    main()
