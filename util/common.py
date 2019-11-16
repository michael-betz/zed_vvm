from sys import argv, exit
from litex.soc.integration.builder import Builder
from litex import RemoteClient
from os import system
from os.path import isfile, splitext
from struct import pack, unpack
# from numpy import *
# from matplotlib.pyplot import *
# from scipy.signal import *
from migen import *


class LedBlinker(Module):
    def __init__(self, f_clk=100e6, outs=None):
        """
        for debugging clocks
        toggles outputs at 1 Hz
        use ClockDomainsRenamer()!
        """
        self.outs = outs
        if outs is None:
            self.outs = Signal(8)

        ###

        max_cnt = int(f_clk / 2)
        cntr = Signal(max=max_cnt + 1)
        self.sync += [
            cntr.eq(cntr + 1),
            If(cntr == max_cnt,
                cntr.eq(0),
                self.outs.eq(Cat(~self.outs[-1], self.outs[:-1]))
            )
        ]


def main(soc, doc='', **kwargs):
    """ generic main function for litex modules """
    print(argv, kwargs)
    if len(argv) < 2:
        print(doc)
        exit(-1)
    tName = argv[0].replace(".py", "")
    vns = None
    if 'sim' in argv:
        run_simulation(
            soc,
            vcd_name=tName + '.vcd',
            **kwargs
        )
    if "build" in argv:
        builder = Builder(
            soc, output_dir="build", csr_csv="build/csr.csv",
            csr_json="build/csr.json",
            compile_gateware=False, compile_software=False
        )
        vns = builder.build(
            build_name=tName, regular_comb=False, blocking_assign=True
        )
        # Ugly workaround as I couldn't get vpath to work :(
        system('cp ./build/gateware/mem*.init .')
    if "synth" in argv:
        builder = Builder(
            soc, output_dir="build", csr_csv="build/csr.csv",
            csr_json="build/csr.json",
            compile_gateware=True, compile_software=True
        )
        vns = builder.build(build_name=tName)
    if "config" in argv:
        prog = soc.platform.create_programmer()
        prog.load_bitstream("build/gateware/{:}.bit".format(tName))
    print(vns)
    try:
        soc.do_exit(vns)
    except:
        pass
    return vns


#-----------------------
# litex_server stuff
#-----------------------
def getId(r):
    s = ""
    for i in range(64):
        temp = r.read(r.bases.identifier_mem + i * 4)
        if temp == 0:
            break
        s += chr(temp & 0xFF)
    return s


def conLitexServer(csr_csv="build/csr.csv", port=1234):
    for i in range(32):
        try:
            r = RemoteClient(csr_csv=csr_csv, debug=False, port=port + i)
            r.open()
            print("Connected to Port", 1234 + i)
            break
        except ConnectionRefusedError:
            r = None
    if r:
        print(getId(r))
    else:
        print("Could not connect to RemoteClient")
    return r


class LTC_SPI:
    # config bits
    OFFLINE = 0  # all pins high-z (reset=1)
    CS_POLARITY = 3  # active level of chip select (reset=0)
    CLK_POLARITY = 4  # idle level of clk (reset=0)
    CLK_PHASE = 5  # first edge after cs assertion to sample data on (reset=0)
    LSB_FIRST = 6  # LSB is the first bit on the wire (reset=0)
    HALF_DUPLEX = 7  # 3-wire SPI, in/out on mosi (reset=0)
    DIV_READ = 16  # SPI read clk divider (reset=0)
    DIV_WRITE = 24  # f_clk / f_spi_write == div_write + 2
    # xfer bits
    CS_MASK = 0  # Active high bit mask of chip selects to assert (reset=0)
    WRITE_LENGTH = 16  # How many bits to write and ...
    READ_LENGTH = 24  # when to switch over in half duplex mode

    def __init__(self, r):
        self.r = r
        r.regs.spi_config.write(
            (0xFF << LTC_SPI.DIV_WRITE) |
            (0xFF << LTC_SPI.DIV_READ)
        )
        # 16 bit write transfer (includes read as is 4 wire)
        r.regs.spi_xfer.write(
            (0 << LTC_SPI.READ_LENGTH) |
            (0x10 << LTC_SPI.WRITE_LENGTH) |
            (0xFFFF << LTC_SPI.CS_MASK)
        )

    def set_ltc_reg(self, adr, val):
        word = (0 << 15) | ((adr & 0x7F) << 8) | (val & 0xFF)
        word <<= 16
        self.r.regs.spi_mosi_data.write(word)
        self.r.regs.spi_start.write(1)

    def get_ltc_reg(self, adr):
        word = (1 << 15) | ((adr & 0x7F) << 8)
        word <<= 16
        self.r.regs.spi_mosi_data.write(word)
        self.r.regs.spi_start.write(1)
        return self.r.regs.spi_miso_data.read() & 0xFF

    def setTp(self, tpValue):
        # Test pattern on + value MSB
        self.set_ltc_reg(3, (1 << 7) | tpValue >> 8)
        # Test pattern value LSB
        self.set_ltc_reg(4, tpValue & 0xFF)


def myzip(*vals):
    """
    interleave elements in a flattened list

    >>> myzip([1,2,3], ['a', 'b', 'c'])
    [1, 'a', 2, 'b', 3, 'c']
    """
    return [i for t in zip(*vals) for i in t]


def getInt32(I):
    """
    recover sign from twos complement integer
    same as `twos_comp(I, 32)`

    >>> getInt32(0xFFFFFFFF)
    -1
    """
    return unpack("i", pack("I", I))[0]

def twos_comp(val, bits):
    """compute the 2's complement of int value val"""
    if (val & (1 << (bits - 1))) != 0: # if sign bit is set e.g., 8bit: 128-255
        val = val - (1 << bits)        # compute negative value
    return val                         # return positive value as is

def twos_comps(val, bits):
    """compute the 2's complement of an array of int"""
    isNeg = (val >> (bits - 1)) != 0
    val[isNeg] = val[isNeg] - (1 << bits)
    return val

def getNyquist(f, fs):
    """ where does a undersampled tone end up? """
    f_n = f / fs
    f_fract = f_n % 1
    if f_fract <= 0.5:
        return f_fract * fs
    else:
        return (1 - f_fract) * fs


def hd(dat, pad_width=1, word_width=None):
    ''' print a hex-dump, word_width in bytes '''
    if word_width is None:
        word_width = pad_width
    for i, d in enumerate(dat):
        if i % 8 == 0 and len(dat) > 8:
            print('\n{:04x}: '.format(i * word_width), end='')
        print('{:0{ww}x} '.format(d, ww=pad_width * 2), end='')
    print()


def autoBitslip(r):
    '''
    resets IDELAY to the middle,
    fires bitslips until the frame signal reads 0xF0
    '''
    setIdelay(r, 16)
    for i in range(8):
        val = r.regs.lvds_frame_peek.read()
        if val == 0xF0:
            print("autoBitslip(): aligned after", i)
            return
        r.regs.lvds_bitslip_csr.write(1)
    raise RuntimeError("autoBitslip(): failed alignment :(")


def setIdelay(r, target_val):
    '''
    increments / decrements IDELAY to reach target_val
    '''
    val = r.regs.lvds_idelay_value.read()
    val -= target_val
    if val > 0:
        for i in range(val):
            r.regs.lvds_idelay_dec.write(1)
    else:
        for i in range(-val):
            r.regs.lvds_idelay_inc.write(1)


def autoIdelay(r):
    '''
    testpattern must be 0x01
    bitslips must have been carried out already such that
    data_peek reads 0x01
    '''
    # approximately center the idelay first
    setIdelay(r, 16)

    # decrement until the channels break
    for i in range(32):
        val0 = r.regs.lvds_data_peek0.read()
        val1 = r.regs.lvds_data_peek2.read()
        if val0 != 1 or val1 != 1:
            break
        r.regs.lvds_idelay_dec.write(1)
    minValue = r.regs.lvds_idelay_value.read()

    # step back up a little
    for i in range(5):
        r.regs.lvds_idelay_inc.write(1)

    # increment until the channels break
    for i in range(32):
        val0 = r.regs.lvds_data_peek0.read()
        val1 = r.regs.lvds_data_peek2.read()
        if val0 != 1 or val1 != 1:
            break
        r.regs.lvds_idelay_inc.write(1)
    maxValue = r.regs.lvds_idelay_value.read()

    # set idelay to the sweet spot in the middle
    setIdelay(r, (minValue + maxValue) // 2)

    print('autoIdelay(): min = {:}, mean = {:}, max = {:} idelays'.format(
        minValue,
        r.regs.lvds_idelay_value.read(),
        maxValue
    ))

def initLTC(r, check_align=False):
    print("Resetting LTC")
    ltc_spi = LTC_SPI(r)
    ltc_spi.set_ltc_reg(0, 0x80)   # reset the chip
    ltc_spi.setTp(1)
    autoBitslip(r)
    autoIdelay(r)

    if check_align:
        print("ADC word bits:")
        for i in range(14):
            tp = 1 << i
            ltc_spi.setTp(tp)
            tp_read = r.regs.lvds_data_peek0.read()
            print("{:014b} {:014b}".format(tp, tp_read))
            if tp != tp_read:
                raise RuntimeError("LVDS alignment error")

    ltc_spi.set_ltc_reg(3, 0)  # Test pattern off
    ltc_spi.set_ltc_reg(1, (1 << 5))  # Randomizer off, twos complement output


def unique_filename(file_name):
    """ thank you stack overflow """
    counter = 1
    ps = splitext(file_name)  # returns ('/path/file', '.ext')
    while isfile(file_name):
        file_name = ps[0] + '_' + str(counter) + ps[1]
        counter += 1
    return file_name
