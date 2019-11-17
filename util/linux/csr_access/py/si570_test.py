from csr_lib import hd, CsrLib, I2C
from Si570 import calcFreq, writeSi570
from time import sleep

with CsrLib(0x40000000, "csr.json") as c:
    print(c.get_ident())

    i2c = I2C(c, 'si570_i2c_r', 'si570_i2c_w')
    i2c.scan()

    print("\nRead Si570 initial settings")
    initialRegs = i2c.read_regs(0x55, 0x0D, 6)
    hd(initialRegs)
    print("f_s = {:.6f} MHz".format(c.read_reg("lvds_f_sample_value") / 1e6))

    print("\nSetup Si570 for 117.6 MHz")
    newRegs = calcFreq(initialRegs, 10e6, 117.6e6)._regs
    writeSi570(i2c, newRegs)
    hd(i2c.read_regs(0x55, 0x0D, 6))
    sleep(2)
    print("f_s = {:.6f} MHz".format(c.read_reg("lvds_f_sample_value") / 1e6))

    print("\nBack to 10 MHz initial setting")
    writeSi570(i2c, [0xad, 0x42, 0xa8, 0xb2, 0x60, 0x6c])
    hd(i2c.read_regs(0x55, 0x0D, 6))
    sleep(2)
    print("f_s = {:.6f} MHz".format(c.read_reg("lvds_f_sample_value") / 1e6))
