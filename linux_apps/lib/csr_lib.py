import mmap
from numpy import frombuffer, uint32, array
import json


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
        self.write(reg['addr'], value)

    def read_mem(self, name, N=None):
        mem = self.j['memories'][name]
        if N is None:
            N = mem['size'] // 4
        return self.read(mem['base'], N)

    def get_ident(self):
        addr = self.j['csr_bases']['identifier_mem']
        s = ""
        for i in range(64):
            c = self.read(addr + i * 4)
            if c == 0:
                break
            s += chr(c & 0xFF)
        return s


class CsrLibLegacyAdapter:
    '''
    to use libraries written for CsrLib
    with litex remote_server
    '''
    def __init__(self, remote_client):
        self.rc = remote_client

    def read_reg(self, name):
        return getattr(self.rc.regs, name).read()

    def write_reg(self, name, value):
        getattr(self.rc.regs, name).write(value)

    def read_mem(self, name, N=None):
        mem = getattr(self.rc.mems, name)
        if N is None:
            N = mem.size // 4
        return array(self.rc.big_read(mem.base, N), dtype=uint32)


def hd(dat, pad_width=1, word_width=None):
    ''' print a hex-dump, word_width in bytes '''
    if word_width is None:
        word_width = pad_width
    for i, d in enumerate(dat):
        if i % 8 == 0 and len(dat) > 8:
            print('\n{:04x}: '.format(i * word_width), end='')
        print('{:0{ww}x} '.format(d, ww=pad_width * 2), end='')
    print()
