
# PS7 peripherals configuration
The Zynq Processing System (PS) is the CPU part of the FPGA. It has several peripherals like SPI, CAN, I2C, UART, GPIO, etc. These are connected to dedicated IO pins on the chip (MIO) or to the FPGA Programmable Logic (EMIO), from where they can be routed to any other IO pin of the chip through the FPGA fabric. Configuration happens in Vivado through the `ZYNQ7 Processing system` IP block.

If the PS7 block is not included in the PL design, the CPU will freeze as soon as the the resulting bitfile is loaded. The PL part of the design will work as intended, even without the PS7 block.

Configuration of the PS7 block is stored in the Xilinx IP file `ip/processing_system7_0.xci`, which is required by the Litex `SoCZynq()` class.

To manually generate this file, follow these steps:

  1. open Vivado, new RTL project, `zedboard` hardware platform, don't add source files, next, next next ..
  2. IP Integrator --> Create Block Design
  3. Add `ZYNQ7 Processing system` IP
  4. Run vivado design automation to get default values for Zedboard
  5. Configure the PS7 block in GUI
       * Bank0 / 1 voltage = 2.5 V
       * Clock Configuration, PL Fabric Clocks: clock0 100 MHz. The litex `sysclk` domain is driven by clock0
  6. Peripheral I/O Pins
       * The PS_MIOX pins are connected to the PS and can be configured here for special function operation (like CAN, I2C, SPI, UART, GPIO)
       * PMOD JE1 is exclusively connected to MIOs (see table below). This might be useful to drive a small graphical LCD from linux trough an SPI interface
  7. Save and close, this generates the file `<name>.srcs/sources_1/ip/processing_system7_0/processing_system7_0.xci` in the project directory, which needs to be copied to `./ip`

__All these steps have now been automated by `ip/gen_ip.tcl`.__

This .tcl script is automatically run by the Makefile. If you want to change the PS configuration, change only this file.

## Peripherals connected to PS

These are accessible from linux when configured in step 6 above (most are already configured by default) and once the right driver has been loaded, which requires an entry into the linux device tree.

| Net      |PS_EMIO<x> |              |
| -------- | --------- | ------------ |
|__PMOD-A__|           | __FP PCB__   |
|  JA1     | 54        | ENCODER: B   |
|  JA2     | 55        | ENCODER: SW  |
|  JA3     | 56        | ENCODER: A   |
|  JA4     | 57        | STATUS_LED   |
| JA10     |           | OLED: MOSI   |
|  JA9     |           | OLED: SCLK   |
|  JA8     |           | OLED: /CS    |
|  JA7     | 58        | OLED: D/C    |
|__PMOD-B__|           |__Si570 PCB__ |
|  JB1     |           |              |
|  JB2     |           |              |
|  JB3     |           |              |
|  JB4     |           |              |
| JB10     |           | SDA          |
|  JB9     |           | SCL          |
|  JB8     |           | OE           |
|  JB7     |           | NC           |

### PMOD-E is dedicated to the PS-wired MIO pins
Will be used with the front panel PCB for the user interface.

| Net      | PS_MIO<x> | PS7, SPI1  |              |
| -------- | --------- | ---------- | ------------ |
|__PMOD-E__|           |            | __FP PCB__   |
|  JE1     | 13        | SS[0]      | OLED: /CS    |
|  JE2     | 10        | MOSI       | OLED: MOSI   |
|  JE3     | 11        | MISO       | ENCODER: SW  |
|  JE4     | 12        | SCLK       | OLED: SCLK   |
| JE10     | 15        | SS[2]      | OLED: D/C    |
|  JE9     | 14        | SS[1]      | STATUS_LED   |
|  JE8     | 9         |            | ENCODER: B   |
|  JE7     | 0         |            | ENCODER: A   |
|__Button__|           |            |              |
|  PB1     | 50        |            |              |
|  PB2     | 51        |            |              |
| __LED__  |           |            |              |
|  LD9     |7 (USB rst)|            |              |

Note on PS7:
  * MIO0 - MIO53
  * EMIO54 - EMIO117

Change MIO11 from MISO to GPIO with pullup in `ps7_init_gpl.c`.
The Vivado GUI does not allow this configuration, that's why we have
to hack it.

```
    from: EMIT_MASKWRITE(0XF800072C, 0x00003FFFU ,0x000007A0U),
    to:   EMIT_MASKWRITE(0XF800072C, 0x00003FFFU ,0x00001600U)
```
this has been automated in the Makefile

# Zedboard OLED
TODO: add guide to get FBTFT running
