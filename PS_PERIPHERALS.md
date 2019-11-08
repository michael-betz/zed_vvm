# SPI interface
We need SPI support to use the OLED from within linux.

Enable `Device Drivers --> SPI support --> User mode SPI device driver support`

Then add the following to the device tree at
`arch/arm/boot/dts/zynq-zed.dts`

```
&spi0 {
  is-decoded-cs = <0>;
  num-cs = <1>;
  status = "okay";
  spidev@0x00 {
    compatible = "spidev";
    spi-max-frequency = <5000000>;
    reg = <0>;
  };
};

&spi1 {
  is-decoded-cs = <0>;
  num-cs = <1>;
  status = "okay";
  spidev@0x01 {
    compatible = "spidev";
    spi-max-frequency = <5000000>;
    reg = <0>;
  };
};
```

# Zedboard OLED
TODO: add guide to get FBTFT running
