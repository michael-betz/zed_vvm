'''
Software drivers which work together
with the litex bitbang hardware modules
'''


class I2C:
    I2C_R = 1
    I2C_W = 0

    def __init__(self, csr_lib, r_name, w_name):
        '''
        I2C driver for use with litex
        bitbang.I2CMaster

        csr_lib: reference to CsrLib object for CSR read / write
        r_name: name of the i2c read register, reading sda
        w_name: name of the i2c write register controlling scl, oe, sda
        '''
        self.r = r_name
        self.w = w_name
        self.c = csr_lib
        self._x = 0
        self._pin(1, 0, 0)

    def _pin(self, scl=None, oe=None, sda=None):
        ''' set state of one or more pins '''
        for i, v in zip((0, 1, 2), (scl, oe, sda)):
            if v is not None:
                if v:
                    self._x |= (1 << i)
                else:
                    self._x &= ~(1 << i)
        self.c.write_reg(self.w, self._x)

    def start(self):
        ''' send i2c START condition '''
        self._pin(scl=1)
        self._pin(oe=1)
        self._pin(scl=0)

    def stop(self):
        ''' send i2c STOP condition '''
        self._pin(oe=1)
        self._pin(scl=1)
        self._pin(oe=0)

    def tx(self, dat):
        '''
        transmit a byte
        returns True if ACK has been received
        '''
        for i in range(8):
            self._pin(oe=(dat & 0x80) == 0)
            self._pin(scl=1)
            dat <<= 1
            self._pin(scl=0)
        # Receive ack from slave
        self._pin(oe=0)
        self._pin(scl=1)
        ack = self.c.read_reg(self.r) == 0
        self._pin(scl=0)
        return ack

    def rx(self, ack):
        '''
        receive a byte
        if ack is True, sends ACK to slave
        '''
        dat = 0
        for i in range(8):
            dat <<= 1
            self._pin(scl=1)
            dat |= self.c.read_reg(self.r) & 0x01
            self._pin(scl=0)
        self._pin(scl=0)
        # Send ACK to slave
        self._pin(oe=ack)
        self._pin(scl=1)
        self._pin(scl=0)
        self._pin(oe=0)
        return dat

    def write_regs(self, addr_7, addr_reg, data):
        '''
        i2c multiple register write
        returns True on success
        '''
        ret = 1
        self.start()
        ret &= self.tx((addr_7 << 1) | I2C.I2C_W)
        ret &= self.tx(addr_reg)
        for d in data:
            ret &= self.tx(d)
        self.stop()
        return ret

    def read_regs(self, addr_7, addr_reg, N, ackFail=True):
        '''
        i2c multiple register read
        ackFail: when True, raise Exception on ACK error
        returns received data
        '''
        ret = 1
        self.start()
        ret &= self.tx((addr_7 << 1) | I2C.I2C_W)
        ret &= self.tx(addr_reg)
        self.start()
        ret &= self.tx((addr_7 << 1) | I2C.I2C_R)
        if ret == 0 and ackFail:
            raise RuntimeError("No ACK")
        dat = []
        for i in range(N):
            dat.append(self.rx(i < (N - 1)))
        self.stop()
        return dat

    def scan(self):
        ''' prints 7 bit I2C addresses which replied with ACK'''
        print("I2C scan: [", end='')
        for i in range(128):
            self.start()
            ret = self.tx((i << 1) | I2C.I2C_W)
            if ret:
                print("{:02x} ".format(i), end='')
            self.stop()
        print("]")


class SPI:
    def __init__(self, csr_lib, r_name, w_name):
        '''
        I2C driver for use with litex
        bitbang.SPIMaster

        csr_lib: reference to CsrLib object for CSR read / write
        r_name: CSR, reading MISO, MOSI
        w_name: CSR controlling CLK, MOSI, OE, CS
        '''
        self.c = csr_lib
        self.r = r_name
        self.w = w_name
        self._x = 0
        self._pin(0, 0, 0, 0)

    def _pin(self, clk=None, mosi=None, oe=None, cs=None):
        ''' set state of one or more pins '''
        for i, v in zip((0, 1, 2, 4), (clk, mosi, oe, cs)):
            if v is not None:
                if v:
                    self._x |= (1 << i)
                else:
                    self._x &= ~(1 << i)
        self.c.write_reg(self.w, self._x)

    def rxtx(self, tx_val, nBits):
        rx_val = 0
        self._pin(cs=1, oe=1)
        for i in range(nBits):
            self._pin(clk=0)
            self._pin(mosi=(tx_val >> (nBits - i - 1)) & 1)
            self._pin(clk=1)
            rx_val |= self.c.read_reg(self.r) & 1
            rx_val <<= 1
        self._pin(cs=0)
        self._pin(clk=0, oe=0)
        return rx_val
