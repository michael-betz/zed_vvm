#!/usr/bin/python3
'''
display phase / magnitude on the OLED screen
'''
import logging
import sys
import signal
from time import sleep
from numpy import log10
from os import putenv, environ
from socket import gethostname
from random import randint, choice, random
import pygame as pg
from pygame.draw import line
from evdev import InputDevice
import argparse
import paho.mqtt.client as mqtt

log = logging.getLogger('vvm_oled')


class VvmApp:
    def __init__(self, args):
        self.mags = [-120] * 4
        self.phases = [0] * 3
        self.f_ref = 0
        self.nyquist_band = 0

        self.args = args

        self.mq = mqtt.Client('vvm_oled', True)
        self.mq.enable_logger(log)
        self.mq.on_connect = self.on_connect
        self.mq.connect_async(args.mqtt_server, args.mqtt_port, 60)
        self.mq.loop_start()

        for k in ('mags', 'phases', 'f_ref'):
            self.mq.message_callback_add('vvm/results/' + k, self.on_result)
        self.mq.message_callback_add('vvm/settings/#', self.on_result)

        putenv('SDL_NOMOUSE', '')
        putenv('SDL_FBDEV', '/dev/fb1')
        putenv('SDL_FBACCEL', '0')
        putenv('SDL_VIDEODRIVER', 'fbcon')
        pg.display.init()
        pg.font.init()
        pg.mouse.set_visible(False)
        self.d = pg.display.set_mode((256, 64))  # returns the display surface

        fntNames = ('UbuntuMono-Regular', 'UbuntuMono-Bold')
        fntSizes = (16, 26)
        self.fnts = [
            pg.font.Font('oled/fonts/{}.ttf'.format(n), s)
            for n, s in zip(fntNames, fntSizes)
        ]

        self.dev_rot = InputDevice('/dev/input/event0')
        self.dev_push = InputDevice('/dev/input/event1')

    def on_connect(self, client, userdata, flags, rc):
        log.info('MQTT connected %s %s', flags, rc)
        client.subscribe('vvm/#')

    def on_result(self, client, user, m):
        ''' convert payload to float and shove it into self '''
        k = m.topic.split('/')[-1]
        if b',' in m.payload:
            setattr(self, k, [float(v) for v in m.payload.split(b',')])
        else:
            setattr(self, k, float(m.payload))

    def loop_forever(self):
        frm = 0

        while True:
            self.d.fill((0x00, ) * 3)
            # ----------------------
            #  Draw numbers on OLED
            # ----------------------
            # Reference frequency / power
            f0 = self.fnts[0]
            s_ = 'REF: {:8.4f} MHz, {:5.1f} dBm'.format(
                self.mags[0], self.f_ref
            )
            sur = f0.render(s_, True, (0xAA,) * 3)
            self.d.blit(sur, (0, -2))

            # 3 x phase
            for i in range(3):
                if self.mags[i + 1] > -60:
                    s_ = '{:>6.1f}'.format(self.phases[i])
                else:
                    s_ = '{:>6s}'.format(' .... ')
                sur = self.fnts[1].render(s_, True, (0xFF,) * 3)
                self.d.blit(sur, (i * 86 + 1, 18))

            # 3 x power
            for i in range(3):
                s_ = '{:>5.1f} dBm'.format(self.mags[i + 1])
                sur = f0.render(s_, True, (0xAA,) * 3)
                self.d.blit(sur, (4 + i * 87, 46))

            # horizontal lines
            line(self.d, (0x44,) * 3, (0, 16), (255, 16), 2)
            line(self.d, (0x44,) * 3, (0, 44), (255, 44), 2)

            pg.display.update()

            # ------------------
            #  Handle user input
            # ------------------
            self.handle_input()

            sleep(1 / self.args.fps)
            frm += 1

    def handle_input(self):
        ''' returns encoder steps and button pushes '''
        rot = 0
        btn = False

        while True:
            # unfortunately using read() and try / except:
            # causes a huge memory leak
            evt = self.dev_rot.read_one()
            if evt is None:
                break
            if evt.type == 2:
                rot += evt.value

        while True:
            evt = self.dev_push.read_one()
            if evt is None:
                break
            btn |= evt.value

        n = self.nyquist_band + rot
        n = 0 if n < 0 else 13 if n > 13 else n
        self.mq.publish('vvm/settings/nyquist_band', n, 0, True)

        if btn:
            self.mq.publish('vvm/settings/tune', 'void', 0, True)

        return rot, btn


def main():
    # systemd sends a SIGHUP at startup :p ignore it
    signal.signal(signal.SIGHUP, lambda x, y: print('SIGHUP'))

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--mqtt_server', default='localhost',
        help='Hostname / IP of the mqtt broker to connect to'
    )
    parser.add_argument(
        '--mqtt_port', default=1883,
        help='Port of the mqtt broker'
    )
    parser.add_argument(
        '--fps', default=30.0, type=float,
        help='Default frames per second'
    )
    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help='increase output verbosity'
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    app = VvmApp(args)
    app.loop_forever()


if __name__ == '__main__':
    main()
