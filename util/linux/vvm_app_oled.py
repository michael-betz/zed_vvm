#!/usr/bin/python3
import sys
from time import sleep
from numpy import log10
from os import putenv
from socket import gethostname
from datetime import datetime
from random import randint, choice
import pygame as pg
from pygame.draw import ellipse, rect
from evdev import InputDevice

sys.path.append("./csr_access/py")
from csr_lib import hd, CsrLib
from bitbang import I2C
from vvm_helpers import initLTC, initSi570, twos_comps


def meas_f_ref(c):
    return c.read_reg('vvm_f_ref_csr') * f_s / 100e6


def draw(c, d):
    d.fill((0x00, ) * 3)
    s_ = "REF: {:8.4f} MHz,  {:5.1f} dBm".format(
        meas_f_ref(c) / 1e6,
        20 * log10(c.read_reg("vvm_mag0") / (1 << 21)) + 12
    )
    sur = fnts[0].render(s_, True, (0xFF,) * 3)
    d.blit(sur, (0, 0))

    for i in range(3):
        mag_val = c.read_reg("vvm_mag{}".format(i + 1))
        val = c.read_reg("vvm_phase{}".format(i + 1))
        val = twos_comps(val, 32) / (1 << 21) * 180
        if 20 * log10(mag_val / (1 << 21)) > -70:
            _s = "{:>6.1f}".format(val)
        else:
            _s = "{:>6s}".format('----')
        sur = fnts[1].render(_s, True, (0xFF,) * 3)
        d.blit(sur, (i * 80, 24))


def getEncoderDelta():
    ''' returns encoder steps and button pushes '''
    rot = 0
    btn = False
    try:
        for evt in dev_rot.read():
            if evt.type == 2:
                rot += evt.value
    except BlockingIOError:
        pass
    try:
        for evt in dev_push.read():
            btn |= evt.value
    except BlockingIOError:
        pass
    return rot, btn


def main():
    global dev_rot, dev_push, fnts, f_s

    f_s = 117.6e6
    f_dut = 22.43e6

    putenv('SDL_NOMOUSE', '')
    putenv('SDL_FBDEV', '/dev/fb1')
    putenv('SDL_FBACCEL', '0')
    putenv('SDL_VIDEODRIVER', 'fbcon')

    pg.display.init()
    pg.font.init()
    pg.mouse.set_visible(False)
    d = pg.display.set_mode()  # returns the display surface

    fntNames = ("Ubuntu-Regular", "UbuntuMono-Bold")
    fntSizes = (17, 28)
    fnts = [pg.font.Font('oled/fonts/{}.ttf'.format(n), s) for n, s in zip(fntNames, fntSizes)]

    dev_rot = InputDevice('/dev/input/event0')
    dev_push = InputDevice('/dev/input/event1')

    with CsrLib(0x40000000, "csr.json") as c:
        print(c.get_ident())

        initSi570(c, f_s)
        initLTC(c, check_align=True)

        # Frequency / bandwidth setting
        print("Measured f_s: {:.6f} MHz".format(
            c.read_reg('lvds_f_sample_value') / 1e6
        ))
        ftw = int(((f_dut / f_s) % 1) * 2**32)
        c.write_reg('vvm_ddc_ftw', ftw)
        deci = 100
        c.write_reg('vvm_ddc_deci', deci)

        # Throw away N bits after CIC
        # to avoid saturation with large deci factors
        # This will change the scaling!
        c.write_reg('vvm_ddc_shift', 0)

        # IIR result averaging filter smoothing factor (0 - 15)
        c.write_reg('vvm_iir', 15)

        print('ddc_ftw', hex(c.read_reg('vvm_ddc_ftw')))
        print('f_sample', f_s)
        print('ddc_deci', c.read_reg('vvm_ddc_deci'))
        print('bw', f_s / deci)
        print('iir_shift', c.read_reg('vvm_iir'))

        i = 0
        while True:
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    pg.quit()

            draw(c, d)
            pg.display.update()

            rot, btn = getEncoderDelta()
            if btn or i == 100:
                f_meas = meas_f_ref(c)
                print("Reset f_center to {:.3f} MHz".format(f_meas / 1e6))
                ftw = int(((f_meas / f_s) % 1) * 2**32)
                c.write_reg('vvm_ddc_ftw', ftw)

            i += 1
            pg.time.delay(30)


if __name__ == '__main__':
    main()
