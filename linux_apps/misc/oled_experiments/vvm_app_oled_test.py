#!/usr/bin/python3
'''
display phase / magnitude on the OLED screen
'''
import sys
import signal
from time import sleep
from numpy import log10
from os import putenv, environ
from socket import gethostname
from datetime import datetime
from random import randint, choice, random
import pygame as pg
from pygame.draw import ellipse, rect
import argparse
import gc


class VvmApp:
    def __init__(self, args, c):
        self.args = args
        self.c = c
        self.nyquist_band = args.nyquist_band
        self.M = (1, 1, 1)  # Measurement harmonic

        pg.display.init()
        pg.font.init()
        pg.mouse.set_visible(False)
        self.d = pg.display.set_mode((256, 64))  # returns the display surface

        fntNames = ('UbuntuMono-Regular', 'UbuntuMono-Bold')
        fntSizes = (16, 26)
        self.fnts = [pg.font.Font('fonts/{}.ttf'.format(n), s) for n, s in zip(fntNames, fntSizes)]


    def draw(self, frm=0):
        self.d.fill((0x00, ) * 3)
        # ----------------------
        #  Draw numbers on OLED
        # ----------------------
        # Reference frequency / power
        f0 = self.fnts[0]
        s_ = 'REF: {:8.4f} MHz, {:5.1f} dBm'.format((frm + random()) % 900, (random() - 0.5) * 30)
        sur = f0.render(s_, True, (0xAA,) * 3)
        self.d.blit(sur, (0, -2))

        # 3 x phase
        for i in range(3):
            if random() > 0.1:
                _s = '{:>6.1f}'.format((frm / 300 + random()) % 360 - 180)
            else:
                _s = '{:>6s}'.format(' .... ')
            sur = self.fnts[1].render(_s, True, (0xFF,) * 3)
            self.d.blit(sur, (i * 86 + 1, 18))

        # 3 x power
        for i in range(3):
            s_ = '{:>5.1f} dBm'.format((frm / 200) % 80 - 70 + random())
            sur = f0.render(s_, True, (0xAA,) * 3)
            self.d.blit(sur, (4 + i * 87, 46))

        # horizontal lines
        pg.draw.line(self.d, (0x44,) * 3, (0, 16), (255, 16), 2)
        pg.draw.line(self.d, (0x44,) * 3, (0, 44), (255, 44), 2)

        # ------------------
        #  Handle user input
        # ------------------
        rot, btn = self.handle_input()

        n = self.nyquist_band + rot
        n = 0 if n < 0 else 13 if n > 13 else n
        self.nyquist_band = n

    def handle_input(self):
        ''' returns encoder steps and button pushes '''
        rot = 0
        btn = False
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

    app = VvmApp(args, None)
    sleep(1)

    i = 0
    while True:
        for event in pg.event.get():
            if event.type == pg.QUIT:
                pg.quit()

        app.draw(i)
        pg.display.update()

        i += 1
        sleep(300e-3)


if __name__ == '__main__':
    main()
