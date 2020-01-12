#!/usr/bin/python3
'''
MQTT client to expose VVM measurements and controls
'''
import logging
import sys
import signal
from time import sleep
from numpy import log10, zeros
from socket import gethostname
from datetime import datetime
import argparse
from mqtt_pvs import MqttPvs

from lib.csr_lib import hd, CsrLib
from lib.bitbang import I2C
from lib.vvm_helpers import initLTC, initSi570, twos_comps, meas_f_ref, \
    CalHelper, getNyquist, getRealFreq

log = logging.getLogger('vvm_daemon')


class VvmApp:
    def __init__(self, args, c):
        self.args = args
        self.c = c
        self.M = (1, 1, 1)  # Measurement harmonic

        prefix = 'vvm/settings/'
        self.pvs = MqttPvs(args, prefix, {
            # DEFAULT, MIN, MAX, WRITE_TO_HW
            # DEFAULT = None: take it from args
            'fps':          [None, 0.01, 120],
            'nyquist_band': [None, 0, 13],
            'vvm_iir':      [None, 0, 13, True],
            'vvm_ddc_shift':[None, 1, 64, True],
            'vvm_ddc_deci': [None, 10, 500, True]
        }, c)
        self.mq = self.pvs.mq

        # Trigger auto tuner
        self.mq.message_callback_add(prefix + 'tune', self.tune)

        # Reset DDS phase accumulators of down-converter
        pr = lambda *args: c.write_reg('vvm_ddc_dds_ctrl', 0x01)
        self.mq.message_callback_add(prefix + 'phase_reset', pr)
        pr()

        # Print some CSRs for debugging
        log.info('ddc_ftw %s', hex(c.read_reg('vvm_ddc_dds_ftw0')))
        log.info('f_sample %s', args.fs)
        deci = c.read_reg('vvm_ddc_deci')
        log.info('ddc_deci %s', deci)
        log.info('ddc_shift %s', c.read_reg('vvm_ddc_shift'))
        log.info('BW %.3f MHz', args.fs / deci / 1e6)
        log.info('iir_shift %s', c.read_reg('vvm_iir'))

        # ----------------------------------------------
        #  Load calibration
        # ----------------------------------------------
        self.cal = CalHelper(args.cal_file, args.vvm_ddc_shift, c, args.fs)

    def loop_forever(self):
        sleep(1)
        frm = 0
        while True:
            self.f_ref_bb = 1
            self.f_ref_bb = meas_f_ref(self.c, self.args.fs)
            f_ref = getRealFreq(
                self.pvs.nyquist_band, self.f_ref_bb, self.args.fs
            )

            mags = self.cal.get_mags(f_ref, self.pvs.vvm_ddc_shift)
            phases = self.cal.get_phases(f_ref)

            # Publish as one topic for each value
            # for i in range(4):
            #     self.mq.publish('vvm/results/mag' + str(i), mags[i])
            #     if i > 0:
            #         self.mq.publish(
            #             'vvm/results/phase' + str(i), phases[i - 1]
            #         )

            # Publish multiple values per topic (separated by ,)
            temp = ','.join([str(v) for v in mags])
            self.mq.publish('vvm/results/mags', temp)
            temp = ','.join([str(v) for v in phases])
            self.mq.publish('vvm/results/phases', temp)

            self.mq.publish('vvm/results/f_ref', f_ref)

            sleep(1 / self.pvs.fps)
            frm += 1

    def tune(self, *args):
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
        log.info('tuned f_ref to {:6f} MHz'.format(self.f_ref_bb / 1e6))
        c.write_reg('vvm_ddc_dds_ctrl', 0x02)  # FTW update


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
        '--fps', default=10.0, type=float,
        help='Default measurements per second'
    )
    parser.add_argument(
        '--vvm_ddc_deci', default=100, type=int,
        help='Digital down-conversion decimation factor'
    )
    parser.add_argument(
        '--vvm_ddc_shift', default=2, type=int,
        help='Bits to discard after down conversion to prevent overflow'
    )
    parser.add_argument(
        '--vvm_iir', default=10, type=int,
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
    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help='increase output verbosity'
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    with CsrLib(0x40000000, 'csr.json') as c:
        log.info('FPGA ident: %s', c.get_ident())

        initSi570(c, args.fs)
        initLTC(c, check_align=True)

        # Frequency / bandwidth setting
        log.info('fs = {:6f} MHz, should be {:6f} MHz'.format(
            c.read_reg('lvds_f_sample_value') / 1e6, args.fs / 1e6
        ))

        app = VvmApp(args, c)
        app.loop_forever()


if __name__ == '__main__':
    main()
