from csr_lib import hd, CsrLib, I2C
from time import sleep

CTRL_REG = 135
FREEZE_DCO_REG = 137
SI570_FREEZE_DCO = (1 << 4)
SI570_NEW_FREQ = (1 << 6)

with CsrLib(0x40000000, "csr.json") as c:
    print(c.get_ident())

    print("f_sample:", c.read_reg("lvds_f_sample_value"), "Hz")

    i2c = I2C(c, 'si570_i2c_r', 'si570_i2c_w')
    i2c.scan()

    print("\nSetup Si570 for 150 MHz")
    i2c.write_regs(0x55, FREEZE_DCO_REG, [SI570_FREEZE_DCO])
    i2c.write_regs(0x55, 0x0D, [0xA0, 0xC2, 0xF4, 0x54, 0x6B, 0x22])
    i2c.write_regs(0x55, FREEZE_DCO_REG, [0])
    i2c.write_regs(0x55, CTRL_REG, [SI570_NEW_FREQ])
    hd(i2c.read_regs(0x55, 0x0D, 6))
    sleep(2)
    print("f_sample:", c.read_reg("lvds_f_sample_value"), "Hz\n")

    print("\nSetup Si570 for 10 MHz")
    i2c.write_regs(0x55, FREEZE_DCO_REG, [SI570_FREEZE_DCO])
    i2c.write_regs(0x55, 0x0D, [0xad, 0x42, 0xa8, 0xb2, 0x60, 0x6c])
    i2c.write_regs(0x55, FREEZE_DCO_REG, [0])
    i2c.write_regs(0x55, CTRL_REG, [SI570_NEW_FREQ])
    hd(i2c.read_regs(0x55, 0x0D, 6))
    sleep(2)
    print("f_sample:", c.read_reg("lvds_f_sample_value"), "Hz")
