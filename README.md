# zed_vvm
A RF vector volt-meter intended as an instrument to troubleshoot legacy
accelerator RF systems and general purpose usage.

Made from a Digilent Zedboard running Debian with a DC1525A FMC daughter board on top.

  * 4 channel, 14 bit, 125 MSps, 800 MHz bandwidth (3 dB) analog to digital converter with LVDS interface: __LTC2175-14__
  * Sampling clock provided by a `Si5xx-PROG_EVB` evaluation board running [custom firmware](https://github.com/yetifrisstlama/Si5xx-5x7-EVV_autoloader)
  * 4 x 4096 sample buffer with trigger for adc waveform storage for debugging (`scope_app.py` makes use of that)
  * FPGA implements
    * digital down-conversion and decimation to get a complex baseband (IQ) signal
    * rectangular (IQ) to polar conversion (magnitude, phase)
    * first order IIR filter to smooth the measurement result
    * uses litex CSRs, the wishbone2axi bridge and litex_server to make the measurements available to linux running on the CPU

# Specs
  * Must support 125 MHz & 500 MHz signals
  * Same phase reading after power cycle (clock divider states!)
  * 360 degree unique measurement range
  * Phase accuracy (drift error) at the input ports over typical ALS temp range (20 - 30 degC) of at least 1 deg (0.2 %)
  * Amplitude measurement (2 % error is okay)
  * At least 2 input channels + 500 MHz phase ref channel (MO)
  * As simple, cheap and easy to use as possible, such that it can be easily installed in many places
  * Epics support

# Hardware modifications
## Zedboard
  * remove XADC header (J2) as it interferes with the DC1525A board

## DC1525A
  * Setup the board for differential sample clock input
  * Remove low-pass filter on all 4 analog input channels

# Installing litex
... on debian
```bash
$ sudo apt install libevent-dev libjson-c-dev
$ sudo pip3 install virtualenvwrapper
$ mkvirtualenv litex
$ git clone git@github.com:yetifrisstlama/litex.git --recursive
$ cd litex
$ python litex_setup.py init
$ python litex_setup.py install
$ python setup.py develop
```

# Building the .bit file
Most of the DSP blocks are from LBLs `Bedrock` repo, which needs to be cloned
in the same directory as `zed_vvm`.

Vivado needs to be installed an in the PATH. I use v2019.1.

Setup your zedboard host-name in `util/remote_config_fpga.sh` and
`util/remote_litex_server.sh`.

Note that the Zedboard PS will freeze if the FPGA is not loaded / in the process of being loaded and there is a
AXI memory access through litex_server. So make sure to close the python apps before doing `make upload`.

```bash
$ git clone https://github.com/yetifrisstlama/zed_vvm.git
$ git clone https://github.com/BerkeleyLab/Bedrock.git
$ cd zed_vvm
$ workon litex
$ make
# remote FPGA configuration
$ make upload
# start litex_server on zedboard for remote access to FPGA registers
$ make server
# Keep this terminal open and start a new one
```

### Demonstration apps
```bash
$ cd util
# displays raw ADC samples in time and frequency domain
$ python3 scope_app.py
# displays RF magnitude and phase over time
$ python3 vvm_app.py
# try -h to list supported command line arguments
```

# Steps to get debian running on zedboard
It's like having a raspberry pi in your FPGA :)

The main reason to go down that route is convenience for
application development:
  * `sudo apt install <whatever_you_need>`
  * python3 support with numpy / scipy or even jupyter notebook
  * ssh and scp make remote access secure and easy, even on the public internet
  * remote loading of bit-files through scp is very convenient
  * litex_server can run on the zedboard, making access to CSR-registers over
    ethernet easy and transparent. The TCP connection is tunneled trough ssh,
    making it secure
  * can run epics IOC, mosquitto client or even node-red to publish
    measurement results

This guide is mostly based on these two:
  * https://github.com/PyHDI/zynq-linux
  * https://blog.n621.de/2016/05/running-linux-on-a-zynq-without-vivado-madness/

## Bootloaders
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
    make
    export PATH=$PATH:/<..>/u-boot-xlnx/tools/

# Create a ~ 32 MB FAT16 partition on the SD card,
# follow the guide below or use gparted
# in this example it's mounted as /media/sdcard

# Copy first stage bootloader and u-boot image to SD card
    cp u-boot-xlnx/spl/boot.bin /media/sdcard
    cp u-boot-xlnx/u-boot.img /media/sdcard

# Now try it on the Zedboard, you should see u-boot starting on the UART

# compile Kernel
    git clone https://github.com/Xilinx/linux-xlnx.git --recursive
    cd linux-xlnx/
    make xilinx_zynq_defconfig
    make menuconfig
    make -j4 uImage LOADADDR=0x00008000
    make zynq-zed.dtb

# Copy kernel image and device-tree to SD card
    cp arch/arm/boot/uImage /media/sdcard/
    cp arch/arm/boot/dts/zynq-zed.dtb /media/sdcard

# to configure u-boot, create a uEnv.txt as shown below and copy it to SD card

# Try it on Zedboard, the linux kernel should boot and panic
# because of the missing root filesystem
```

## Debian `rootfs`
setup your initial bare-bones debian environment using chroot on the host.
```bash
# debian rootfs (on host)
    sudo apt install debootstrap qemu-user-static
    mkdir rootfs
    sudo debootstrap --arch=armhf --foreign stretch rootfs
    sudo cp /usr/bin/qemu-arm-static rootfs/usr/bin/
    sudo chroot rootfs/

# debian rootfs (chroot)
    distro=stretch
    export LANG=C
    debootstrap/debootstrap --second-stage
    vim /etc/apt/sources.list

deb http://deb.debian.org/debian stretch main
deb http://deb.debian.org/debian-security/ stretch/updates main
deb http://deb.debian.org/debian stretch-updates main

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

# Partitioning the SD card
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
# fpga_boot=fpga loadb 0 ${fpga_addr} $filesize

kernel_addr=0x8000
kernel_load=load mmc 0 ${kernel_addr} uImage

dtr_addr=0x100
dtr_load=load mmc 0 ${dtr_addr} zynq-zed.dtb

kernel_boot=setenv bootargs console=ttyPS0,115200 root=/dev/mmcblk0p2 rw rootwait; bootm ${kernel_addr} - ${dtr_addr}

# to load bitfile before boot, uncomment the above 3 lies
# and add this to beginning: run fpga_load; run fpga_boot;
bootcmd=run kernel_load; run dtr_load; setenv ethaddr 00:0a:35:00:01:87; run kernel_boot
```

# Load bitfile in linux
Bitfiles are loaded trough the [Linux FPGA Manager](https://www.kernel.org/doc/html/v4.18/driver-api/fpga/fpga-mgr.html).
For this to work, the .bit file needs its header removed and its bytes swapped.
This can either be done with the xilinx SDK or alternatively with `bitstream_fix.py`.
```bash
python3 util/bitstream_fix.py <bitfile>.bit
```

copy the resulting `<bitfile>.bit.bin` on the zedboard, then

```bash
    sudo -i
    cp <bitfile>.bit.bin /lib/firmware/
    echo 0 > /sys/class/fpga_manager/fpga0/flags
    echo <bitfile>.bit.bin > /sys/class/fpga_manager/fpga0/firmware
    dmesg

[ 1667.020520] fpga_manager fpga0: writing <bitfile>.bit.bin to Xilinx Zynq FPGA Manager
```

`make upload` automates all these steps.

# how to get `ip/processing_system7_0.xci`
This Xilinx IP file contains the PS7 block describing the connectivity between PS and PL and is required by the Litex `SoCZynq()` class. If the PS7 block is not included in the PL design, the CPU will freeze as soon as the the resulting bitfile is loaded on the zedboard. However, except for the CPU freezing issue, the PL part of the design seems to work fine.

  1. open vivado, new RTL project, `zedboard` hardware platform, don't add source files, next, next next ..
  2. open IP manager, add Zynq Processing system 7 IP
  3. configure it in GUI, Bank0 / 1 voltage = 2.5 V, clock0 100 MHz. By default, clock0 is connected to litex `sysclk`.
  4. Save and close
  5. `zed/zed.srcs/sources_1/ip/processing_system7_0/processing_system7_0.xci`

# remote litex_server
`./litex_server` contains a minimal version of which can run on the zedboard. It only requires python3 installed. It needs sudo to open `/dev/mem`, so it is dangerous! It then connects to the general purpose AXI master (gp0) at address 0x43c00000. On the PL side, this is connected to an AXI to Wishbone converter to read and write the CSRs.

## GP0 address range
The Zynq general purpose AXI master interfaces are mapped to these addresses in memory

| Start     | End      | Size               | Interface |
| --------- | -------- | ------------------ | --------- |
| 4000_0000 | 7FFF_FFF | 3800_0000 (896 MB) | M_AXI_GP0 |
| 8000_0000 | BFFF_FFF | 3800_0000 (896 MB) | M_AXI_GP1 |

The AXI to wishbone adapter subtracts an offset (base_address) and removes the 2 LSB bits so we get word addresses.
See mapping below.

```python
self.add_axi_to_wishbone(self.axi_gp0, base_address=0x4000_0000)
```

| AXI (devmem) | WB << 2     | WB           |
| ------------ | ----------- | ------------ |
| 0x4000_0000  | 0x0000_0000 | 0x0000_0000  |
| 0x4000_0004  | 0x0000_0004 | 0x0000_0001  |
| 0x7FFF_FFFC  | 0x3FFF_FFFC | 0x0FFF_FFFF  |
