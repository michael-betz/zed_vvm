"""
bitstream_fix for Linux fpga_mgr: strip header and swap bytes.

adapted from:
https://github.com/peteut/migen-axi/blob/master/src/tools/bitstream_fix.py

usage:
bitstream_fix.py bitfile.bit
  > bitfile.bit.bin
"""
from sys import argv
import numpy as np

if __name__ == '__main__':
    if len(argv) != 2:
        print(__doc__)
        exit()
    a = np.fromfile(argv[1], dtype="u1")
    hdr = a.tobytes().split(b"\xba\xfc")[0]
    print("Processing {}".format(
        " ".join(hdr[0x10:].decode("ascii").split())))
    a = a[len(hdr) + 2:]
    aa = a.view(dtype="u4")
    aa.byteswap().tofile(argv[1] + ".bin")
