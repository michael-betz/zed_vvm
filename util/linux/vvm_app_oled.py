import sys
sys.path.append("./csr_access/py")
from csr_lib import hd, CsrLib
from bitbang import I2C
from vvm_helpers import initLTC, initSi570


def main():
    f_s = 117.6e6

    with CsrLib(0x40000000, "csr.json") as c:
        print(c.get_ident())

        initSi570(c, f_s)
        initLTC(c, check_align=True)


if __name__ == '__main__':
    main()
