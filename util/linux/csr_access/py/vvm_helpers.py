'''
Helper functions specific to the VVM hardware
'''
import sys
from time import sleep
sys.path.append("./csr_access_test/py")
from bitbang import SPI, I2C
from Si570 import calcFreq, writeSi570
from numpy import int32, load, atleast_2d, argmin, zeros_like, zeros, log10
from struct import pack, unpack


class LTC_SPI(SPI):
    ''' SPI register read / write specific to LTC2175 '''
    def set_ltc_reg(self, adr, val):
        word = (0 << 15) | ((adr & 0x7F) << 8) | (val & 0xFF)
        self.rxtx(word, 16)

    def get_ltc_reg(self, adr):
        word = (1 << 15) | ((adr & 0x7F) << 8)
        return self.rxtx(word, 16) & 0xFF

    def setTp(self, tpValue):
        # Test pattern on + value MSB
        self.set_ltc_reg(3, (1 << 7) | tpValue >> 8)
        # Test pattern value LSB
        self.set_ltc_reg(4, tpValue & 0xFF)


def meas_f_ref(c, f_s):
    ''' measure REF input frequency with zero crossing coutner '''
    return c.read_reg('vvm_zc0_f_meas') * f_s / 100e6


def print_frm(c):
    idel = c.read_reg('lvds_idelay_value')
    v = c.read_reg('lvds_frame_peek')
    print("ID: {:}  F: {:08b}".format(idel, v))
    for i in range(4):
        v = c.read_reg('lvds_data_peek{:}'.format(i))
        print("CH{:}: {:016b}".format(i, v))


def autoBitslip(c):
    '''
    resets IDELAY to the middle,
    fires bitslips until the frame signal reads 0xF0
    '''
    setIdelay(c, 16)
    for i in range(8):
        val = c.read_reg('lvds_frame_peek')
        if val == 0xF0:
            print("autoBitslip(): aligned after", i)
            return
        c.write_reg('lvds_bitslip_csr', 1)
    raise RuntimeError("autoBitslip(): failed alignment :(")


def setIdelay(c, target_val):
    '''
    increments / decrements IDELAY to reach target_val
    '''
    val = c.read_reg('lvds_idelay_value')
    val -= target_val
    if val > 0:
        for i in range(val):
            c.write_reg('lvds_idelay_dec', 1)
    else:
        for i in range(-val):
            c.write_reg('lvds_idelay_inc', 1)


def autoIdelay(c):
    '''
    testpattern must be 0x01
    bitslips must have been carried out already such that
    data_peek reads 0x01
    '''
    # approximately center the idelay first
    setIdelay(c, 16)

    # decrement until the channels break
    for i in range(16):
        val0 = c.read_reg('lvds_data_peek0')
        val1 = c.read_reg('lvds_data_peek2')
        if val0 != 1 or val1 != 1:
            break
        c.write_reg('lvds_idelay_dec', 1)
    minValue = c.read_reg('lvds_idelay_value')

    # step back up a little
    for i in range(5):
        c.write_reg('lvds_idelay_inc', 1)
    idel = c.read_reg('lvds_idelay_value')

    # increment until the channels break
    for i in range(31 - idel):
        val0 = c.read_reg('lvds_data_peek0')
        val1 = c.read_reg('lvds_data_peek2')
        if val0 != 1 or val1 != 1:
            break
        c.write_reg('lvds_idelay_inc', 1)
    maxValue = c.read_reg('lvds_idelay_value')

    # set idelay to the sweet spot in the middle
    setIdelay(c, (minValue + maxValue) // 2)

    print('autoIdelay(): min = {:}, mean = {:}, max = {:} idelays'.format(
        minValue,
        c.read_reg('lvds_idelay_value'),
        maxValue
    ))


def initLTC(c, check_align=False):
    print("Resetting LTC")
    ltc_spi = LTC_SPI(c, "spi_r", "spi_w")

    # Reset the ADC chip, this seems to glitch the DCO clock!
    ltc_spi.set_ltc_reg(0, 0x80)
    sleep(2e-3)

    # Reset EVERY register on sys and sample clock domain and re-init ISERDES
    c.write_reg('ctrl_reset', 1)
    sleep(2e-3)

    # Make ADC output 0x00000001 value samples and align ISERDES
    ltc_spi.setTp(1)
    autoBitslip(c)
    print_frm(c)
    autoIdelay(c)

    if check_align:
        print("ADC word bits:")
        for i in range(14):
            tp = 1 << i
            ltc_spi.setTp(tp)
            tp_read = c.read_reg('lvds_data_peek0')
            print("{:014b} {:014b}".format(tp, tp_read))
            if tp != tp_read:
                raise RuntimeError("LVDS alignment error")

    ltc_spi.set_ltc_reg(3, 0)  # Test pattern off
    ltc_spi.set_ltc_reg(1, (1 << 5))  # Randomizer off, twos complement output


def initSi570(c, f_s=117.6e6):
    ''' set f_sample frequency [Hz] '''
    # initial values for 570BCC000112DG
    si570_initial = bytes([0xad, 0x42, 0xa8, 0xb2, 0x60, 0x6c])
    si570_new = calcFreq(si570_initial, 10e6, f_s)._regs
    i2c = I2C(c, 'si570_i2c_r', 'si570_i2c_w')
    writeSi570(i2c, si570_new)


def twos_comps(val, bits):
    """ compute the 2's complement of an array of int """
    if type(val) is int:
        return unpack("i", pack("I", val))[0]
    isNeg = (val >> (bits - 1)) != 0
    val_ = val.astype(int32)
    val_[isNeg] -= (1 << bits)
    return val_


def getSamples(c, CH, N=None):
    samples = c.read_mem('sample{:}'.format(CH), N)
    return twos_comps(samples, 14) / 2**13


def set_led(isOn=True):
    ''' set the front-panel status LED '''
    with open('/sys/class/leds/led_status/brightness', 'w') as f:
        f.write('1' if isOn else '0')


def getNyquist(f, fs):
    """
    where does an under-sampled tone end up?
    returns baseband frequency and `inverted spectrum` flag
    """
    f_n = f / fs
    f_fract = f_n % 1
    if f_fract <= 0.5:
        return f_fract * fs, False
    else:
        return (1 - f_fract) * fs, True


def getRealFreq(N, fbb, fs):
    '''
    inverse of getNyquist()
    N:  nyquist band,
        0: 0 Hz     .. 1 / 2 fs
        1: 1 / 2 fs .. fs (inverted)
        2: fs       .. 3 / 2 fs

    fbb: baseband frequency [Hz]
         fbb < fs / 2

    fs: sampling rate [Hz]

    returns: actual real frequency [Hz]
    '''
    if (N % 2) == 0:
        # regular spectrum
        return N * fs / 2 + fbb
    else:
        # inverted spectrum
        return (N + 1) * fs / 2 - fbb


def get_mags(c, vvm_ddc_shift):
    ''' [dbFs] '''
    mags = zeros(4)
    for i in range(len(mags)):
        val = c.read_reg("vvm_mag" + str(i))
        val = val / (1 << 21) * (1 << (vvm_ddc_shift - 1))
        mags[i] = val
    return 20 * log10(mags)


def get_phases(c):
    ''' [degree] '''
    phs = zeros(3)
    for i in range(3):
        val = c.read_reg("vvm_phase" + str(i + 1))
        val = twos_comps(val, 32)
        val = val / (1 << 21) * 180
        phs[i] = val
    return phs


class CalHelper:
    ''' calibration for magnitude and phase readings '''
    def __init__(self, cal_file, vvm_ddc_shift=None, c=None, fs=None):
        ''' cal_file must be in .npz format '''
        self.c = c
        self.vvm_ddc_shift = vvm_ddc_shift
        self.fs = fs
        self.d = d = load(cal_file)
        self.f_test = d['f_test']
        self.power_cal_db = d['power_cal_db']
        self.phase_cal_deg = d['phase_cal_deg']

    def get_cals(self, f):
        '''
        get 4 channel correction factors closest to f [Hz]
        add them to the raw magnitude [dB] or raw phase [deg]
        to get a calibrated reading

        returns
            (mag0, mag1, mag2, mag3), (ph1, ph2, ph3)
        '''
        ind = argmin(abs(self.f_test - f))
        return self.power_cal_db[ind], self.phase_cal_deg[ind]

    def get_mags(self, f):
        raw = get_mags(self.c, self.vvm_ddc_shift)
        return raw + self.get_cals(f)[0]

    def get_phases(self, f):
        f_bb, isInverted = getNyquist(f, self.fs)
        raw = get_phases(self.c)
        if isInverted:
            raw *= -1
        return raw + self.get_cals(f)[1]
