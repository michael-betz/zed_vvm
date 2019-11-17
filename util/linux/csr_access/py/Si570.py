class Si570(object):
    """
    helper class to convert from numbers used in the datasheet
    to register values
    """
    HS_DIVS_LOOKUP = (4, 5, 6, 7, None, 9, None, 11)

    def __init__(self, ll=None):
        """
        ll can be a string like 'r 01 C2 BC 81 83 02 \n'
        or a bytearray
        """
        if ll is None:
            self._regs = bytearray(6)
        else:
            if type(ll) is str:
                ls = ll.strip().split()[1:]
                # ['01', 'C2', 'BC', '81', '83', '02']
                self._regs = bytearray([int(x, 16) for x in ls])
            else:
                self._regs = ll

    @property
    def HS_DIV(self):
        """ DCO High Speed Divider """
        return Si570.HS_DIVS_LOOKUP[self._regs[0] >> 5]

    @HS_DIV.setter
    def HS_DIV(self, value):
        ind = Si570.HS_DIVS_LOOKUP.index(value)
        self._regs[0] &= 0x1F
        self._regs[0] |= (ind << 5) & 0xE0

    @property
    def N1(self):
        """ CLKOUT Output Divider """
        N1 = (self._regs[0] & 0x1F) << 2 | self._regs[1] >> 6
        N1 += 1
        # Illegal odd divider values will be rounded
        # up to the nearest even value.
        if((N1 > 1) and (N1 & 0x01)):
            print("Illegal N1: {0}, rounding up to {1}", N1, N1 + 1)
            N1 += 1
        return N1

    @N1.setter
    def N1(self, value):
        value -= 1
        self._regs[0] &= 0xE0
        self._regs[0] |= (value >> 2) & 0x1F
        self._regs[1] &= 0x3F
        self._regs[1] |= (value << 6) & 0xC0

    @property
    def RFFREQ(self):
        """ Reference Frequency control input to DCO. [float] """
        RFFREQ = (self._regs[1] & 0x3F) << 32 | \
            self._regs[2] << 24 | \
            self._regs[3] << 16 | \
            self._regs[4] << 8 | \
            self._regs[5]
        return RFFREQ / 2.0**28

    @RFFREQ.setter
    def RFFREQ(self, value):
        value = int(value * 2**28)
        self._regs[1] &= 0xC0
        self._regs[1] |= (value >> 32) & 0x3F
        self._regs[2] = (value >> 24) & 0xFF
        self._regs[3] = (value >> 16) & 0xFF
        self._regs[4] = (value >> 8) & 0xFF
        self._regs[5] = value & 0xFF

    def fxtal(self, f0):
        """
        calculate internal crystal frequency.
        f0 = startup frequency
        (see http://www.silabs.com/products/timing/lookup-customize)
        """
        return (f0 * self.HS_DIV * self.N1) / self.RFFREQ

    def __repr__(self):
        """ register values as hex string like `w E0 03 02 B5 EA 58` """
        s = 'w '
        s += ' '.join('{:02X}'.format(x) for x in self._regs)
        return s

    def __str__(self):
        """ decoded register values """
        s = "HS_DIV:{0:2d}, N1:{1:2d}, RFFREQ:{2:13.9f}".format(
            self.HS_DIV, self.N1, self.RFFREQ
        )
        return s


def getDividers(f1):
    """ returns a valid combination of clock dividers for target freq. `f1` """
    HS_DIVS = (4, 5, 6, 7, 9, 11)
    NS = [1]
    NS.extend(range(2, 130, 2))
    for h in HS_DIVS[::-1]:
        for n in NS:
            fDco = f1 * h * n
            # print( h, n, fDco/1e9 )
            if fDco > 5.67e9:
                break
            if fDco >= 4.85e9:
                return h, n, fDco
    raise ValueError("Could not find a good combination of clock dividers")


def calcFreq(iRegs='i 01 C2 BB FB FC AB', f0=156.25e6, f1=123e6):
    # parse current settings
    sil = Si570(iRegs)
    fxtal = sil.fxtal(f0)
    print(
        "{!r:>24} --> {!s:<40} f_xtal: {:.6f} MHz".format(
            sil, sil, fxtal / 1.0e6
        )
    )

    # Calculate new settings
    hs_div, n1, fDco = getDividers(f1)
    rffreq = fDco / fxtal

    # Un-parse new settings
    silNew = Si570()
    silNew.HS_DIV = hs_div
    silNew.N1 = n1
    silNew.RFFREQ = rffreq

    return silNew


def writeSi570(i2c, regs, offs=0x0D):
    CTRL_REG = 135
    FREEZE_DCO_REG = 137
    SI570_FREEZE_DCO = (1 << 4)
    SI570_NEW_FREQ = (1 << 6)
    i2c.write_regs(0x55, FREEZE_DCO_REG, [SI570_FREEZE_DCO])
    i2c.write_regs(0x55, offs, regs)
    i2c.write_regs(0x55, FREEZE_DCO_REG, [0])
    i2c.write_regs(0x55, CTRL_REG, [SI570_NEW_FREQ])
