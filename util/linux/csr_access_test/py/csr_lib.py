import mmap
from numpy import frombuffer, uint32, array
import json


def hd(dat, pad_width=1, word_width=None):
    ''' print a hex-dump, word_width in bytes '''
    if word_width is None:
        word_width = pad_width
    for i, d in enumerate(dat):
        if i % 8 == 0 and len(dat) > 8:
            print('\n{:04x}: '.format(i * word_width), end='')
        print('{:0{ww}x} '.format(d, ww=pad_width * 2), end='')
    print()


class CsrLib:
    def __init__(self, adr_offset=0, fJson=None, quiet=True):
        self.adr_offset = adr_offset
        self.sysfs = None
        self.j = None
        if fJson is not None:
            with open(fJson) as f:
                self.j = json.load(f)
            if not quiet:
                print("\n---------------\n Regs\n---------------")
                print("\n".join(self.j['csr_registers'].keys()))
                print("\n---------------\n Mems\n---------------")
                print("\n".join(self.j['memories'].keys()))

    def __enter__(self):
        if self.sysfs is not None:
            return
        self.sysfs = open("/dev/mem", "r+b")
        self.sysfs.flush()
        self.mmap = mmap.mmap(
            self.sysfs.fileno(), 0x38000000, offset=self.adr_offset
        )
        return self

    def __exit__(self, type, value, traceback):
        if self.sysfs is None:
            return
        self.mmap.close()
        del self.mmap
        self.sysfs.close()
        del self.sysfs

    def read(self, addr, length=1, asBytes=False):
        if addr % 4 > 0:
            raise RuntimeError("Un-aligned memory access", hex(addr))
        self.mmap.seek(addr)
        bs = self.mmap.read(length * 4)
        if asBytes:
            return bs
        if length == 1:
            return int.from_bytes(bs, byteorder="little")
        elif length > 1:
            return frombuffer(bs, uint32)

    def write(self, addr, data):
        if type(data) is bytes:
            bs = data
        elif type(data) is int:
            bs = int.to_bytes(data, 4, byteorder="little")
        else:
            ll = len(data)
            if ll == 1:
                bs = int.to_bytes(data[0], 4, byteorder="little")
            elif ll > 1:
                bs = data.tobytes()
        self.mmap.seek(addr)
        self.mmap.write(bs)

    def read_reg(self, name):
        reg = self.j['csr_registers'][name]
        return self.read(reg['addr'], reg['size'])

    def write_reg(self, name, value):
        reg = self.j['csr_registers'][name]
        return self.write(reg['addr'], value)

    def read_mem(self, name):
        mem = self.j['memories'][name]
        return self.read(mem['base'], mem['size'] // 4)

    def get_ident(self):
        addr = self.j['csr_bases']['identifier_mem']
        s = ""
        for i in range(64):
            c = self.read(addr + i * 4)
            if c == 0:
                break
            s += chr(c & 0xFF)
        return s


class I2C:
    I2C_R = 1
    I2C_W = 0
    I2C_ACK = 1
    I2C_NACK = 0

    def __init__(self, csr_lib, r_name, w_name):
        ''' bit-bang I2C driver '''
        self.r = r_name
        self.w = w_name
        self.c = csr_lib
        self.set_pins(1, 1)

    def set_pins(self, scl=None, sda=None):
        if scl is not None:
            self.SCL = scl
        if sda is not None:
            self.SDA = sda
        val = (0 if self.SDA else 2) | (self.SCL & 1)
        self.c.write_reg(self.w, val)

    def start(self):
        self.set_pins(scl=1, sda=1)
        self.set_pins(scl=1, sda=0)
        self.set_pins(scl=0, sda=0)

    def stop(self):
        self.set_pins(scl=1, sda=0)
        self.set_pins(scl=1, sda=1)

    def tx(self, dat):
        for i in range(8):
            self.set_pins(sda=(dat & 0x80))
            self.set_pins(scl=1)
            dat <<= 1
            self.set_pins(scl=0)
        # Receive ack from slave
        self.set_pins(sda=1)
        self.set_pins(scl=1)
        ack = self.c.read_reg(self.r) == 0
        self.set_pins(scl=0)
        return ack

    def rx(self, ack):
        dat = 0
        for i in range(8):
            dat <<= 1
            self.set_pins(scl=1)
            dat |= self.c.read_reg(self.r)
            self.set_pins(scl=0)
        # Send ACK to slave
        self.set_pins(sda=(ack == 0))
        self.set_pins(scl=1)
        self.set_pins(scl=0, sda=1)
        return dat

    def write_regs(self, addr_7, addr_reg, data):
        ret = 1
        self.start()
        ret &= self.tx((addr_7 << 1))
        ret &= self.tx(addr_reg)
        for d in data:
            ret &= self.tx(d)
        self.stop()
        return ret

    def read_regs(self, addr_7, addr_reg, N):
        ret = 1
        self.start()
        ret &= self.tx((addr_7 << 1))
        ret &= self.tx(addr_reg)
        self.start()
        ret &= self.tx((addr_7 << 1) | 1)
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
