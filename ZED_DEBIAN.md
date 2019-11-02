# Steps to get debian running on zedboard
It's like having a raspberry pi in your FPGA :)

This guide is mostly based on these two:
  * https://github.com/PyHDI/zynq-linux
  * https://blog.n621.de/2016/05/running-linux-on-a-zynq-without-vivado-madness/

## Bootloader
```bash
# Cross compiler
    sudo apt install libc6-armel-cross libc6-dev-armel-cross binutils-arm-linux-gnueabi libncurses-dev
    sudo apt-get install gcc-arm-linux-gnueabi g++-arm-linux-gnueabi libssl-dev
    export CROSS_COMPILE=arm-linux-gnueabi-
    export ARCH=arm

# compile U-Boot
    git clone https://github.com/Xilinx/u-boot-xlnx.git --recursive
    cd u-boot-xlnx/
    make zynq_zed_defconfig
    make menuconfig
    # under ARM architecture --> Zynq/ZynqMP PS init file(s) location
    # enter: <path to zed_vvm>/ip/ps7_init_gpl.c
    # This will apply the customized Zynq PS configuration on startup
    make
    export PATH=$PATH:/<..>/u-boot-xlnx/tools/

# Create a ~ 32 MB FAT16 partition on the SD card,
# follow the guide below or use gparted
# in this example it's mounted as /media/sdcard

# Copy first stage bootloader and u-boot image to SD card
    cp u-boot-xlnx/spl/boot.bin /media/sdcard
    cp u-boot-xlnx/u-boot.img /media/sdcard

# Now try it on the Zedboard, you should see u-boot starting on the UART
```
## Linux kernel
```bash
# compile Kernel
    git clone https://github.com/Xilinx/linux-xlnx.git --recursive
    cd linux-xlnx/
    make xilinx_zynq_defconfig
    make menuconfig
```
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

Then build the kernel ...

```bash
    make -j4 uImage LOADADDR=0x00008000
    make zynq-zed.dtb
```

copy kernel image and device-tree to SD card
```bash
    cp arch/arm/boot/uImage /media/sdcard/
    cp arch/arm/boot/dts/zynq-zed.dtb /media/sdcard
```
to configure u-boot, create a `uEnv.txt` as shown below and copy it to SD card.

Now is a good time to give it a test-run on the Zedboard,
the linux kernel should boot and panic because of the missing root filesystem


## Debian `rootfs`
setup your initial bare-bones debian environment using chroot on the host.
```bash
# debian rootfs (on host)
    sudo apt install debootstrap qemu-user-static
    mkdir rootfs
    sudo debootstrap --arch=armhf --foreign buster rootfs
    sudo cp /usr/bin/qemu-arm-static rootfs/usr/bin/
    sudo chroot rootfs/

# debian rootfs (chroot)
    distro=buster
    export LANG=C
    debootstrap/debootstrap --second-stage
    vim /etc/apt/sources.list

deb http://deb.debian.org/debian buster main
deb http://deb.debian.org/debian-security/ buster/updates main
deb http://deb.debian.org/debian buster-updates main

    apt update
    apt upgrade
    apt install openssh-server ntp sudo
    passwd
    adduser <user_name>
    visudo

root        ALL=(ALL:ALL) ALL
<user_name> ALL=(ALL:ALL) ALL

    vim /etc/network/interfaces

allow-hotplug eth0
iface eth0 inet dhcp

    vim /etc/hostname

<hostname>

    vim /etc/hosts

127.0.0.1   localhost <hostname>
::1     localhost ip6-localhost ip6-loopback
ff02::1     ip6-allnodes
ff02::2     ip6-allrouters

# Mount fat16 boot partition for kernel updates / uboot config
    mkdir /boot  # only if it does not exist already
    vim /etc/fstab

/dev/mmcblk0p1 /boot auto defaults 0 0

# Optional Hack to get cross-compiled binaries to run
    sudo ln -s /lib/arm-linux-gnueabihf/ld-2.24.so /lib/ld-linux.so.3

# Exit the chroot shell

# Create a large ext4 partition on the SD card (see below)
# in this example it is mounted as /media/rootfs
    sudo cp -rp rootfs/* /media/rootfs

# The zedboard should boot into linux
# and there should be a login prompt on the UART
```

## Partitioning the SD card
What we need

  * FAT16 partition of size 32 MB
  * Linux (ext4) over the remaining available space

Using `fdisk` on a 2 GB SD card, it should look like this:
```
Device     Boot Start     End Sectors  Size Id Type
/dev/sdd1        2048   67583   65536   32M  e W95 FAT16
/dev/sdd2       67584 3842047 3774464  1.8G 83 Linux
```

then format the partitions as FAT16 and ext4:

```bash
sudo mkfs.vfat -F16 -v /dev/sdd1 -n boot
sudo mkfs.ext4 -v /dev/sdd2 -L rootfs
```

__make sure to replace `sdd1` and `sdd2` with the actual partition names__

# uEnv.txt
U-Boot startup script to boot and optionally load a bitfile. Make sure `ethaddr` is unique on network.
```bash
# fpga_addr=0x10000000
# fpga_load=load mmc 0 ${fpga_addr} zed_wrapper.bit
# fpga_boot=fpga load 0 ${fpga_addr} $filesize

kernel_addr=0x8000
kernel_load=load mmc 0 ${kernel_addr} uImage

dtr_addr=0x100
dtr_load=load mmc 0 ${dtr_addr} zynq-zed.dtb

kernel_boot=setenv bootargs console=ttyPS0,115200 root=/dev/mmcblk0p2 rw rootwait; bootm ${kernel_addr} - ${dtr_addr}

# to load bitfile before boot, uncomment the above 3 lies
# and add this to beginning: run fpga_load; run fpga_boot;
bootcmd=run kernel_load; run dtr_load; setenv ethaddr 00:0a:35:00:01:87; run kernel_boot
```
