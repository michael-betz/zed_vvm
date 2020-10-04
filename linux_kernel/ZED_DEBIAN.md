# Steps to get debian running on zedboard
It's like having a raspberry pi in your FPGA :)

This guide is mostly based on these two:
  * https://github.com/PyHDI/zynq-linux
  * https://blog.n621.de/2016/05/running-linux-on-a-zynq-without-vivado-madness/

## Bootloader
The stock version of U-Boot works perfectly fine for the Zynq7000 on the zedboard. No need for the Xilinx version.
```bash
# Cross compiler
    sudo apt install libc6-armel-cross libc6-dev-armel-cross binutils-arm-linux-gnueabi libncurses-dev
    sudo apt-get install gcc-arm-linux-gnueabi g++-arm-linux-gnueabi libssl-dev
    export CROSS_COMPILE=arm-linux-gnueabi-
    export ARCH=arm

# compile U-Boot
    git clone https://github.com/u-boot/u-boot.git
    cd u-boot/
    git checkout 0f3e2942c9e01b5dfc01f3dabe0e2f2ab8fd8b84
    export DEVICE_TREE=zynq-zed  # for zedboard
    make xilinx_zynq_virt_defconfig
    make menuconfig

# We want u-boot to read uEnv.txt from SD-card to setup its environment.
# Tick `Enable a default value for bootcmd`
# ... for `bootcmd value` enter the line below:
fatload mmc 0 0x10000 uEnv.txt;env import -t 0x10000 $filesize;boot

# Optional, apply a customized Zynq PS configuration on startup:
# under ARM architecture --> Zynq/ZynqMP PS init file(s) location
# enter:
<path to zed_vvm>/gateware/ip/ps7_init_gpl.c
# see also: `PS_PERIPHERALS.md`

    make

    # `mkimage` will be needed for building the kernel
    export PATH=$PATH:<..>/u-boot/tools/

# Create a ~ 64 MB FAT32 partition on the SD card,
# follow the guide below or use gparted
# in this example it's mounted as /media/sdcard

# Copy first stage bootloader and u-boot image to SD card
    cp spl/boot.bin /media/sdcard
    cp u-boot.img /media/sdcard

# Now try it on the Zedboard, you should see u-boot starting on the UART
```
### Erasing the flash
There's a caveat here. U-Boot can store its environment in the SPI flash, which will override the default $bootcmd we set up in menuconfig. To fix this, erase the flash from within the u-boot shell:

```bash
# This is a sign that uEnv.txt was not loaded correctly from MMC
Zynq> echo $bootcmd
run $modeboot

# Flash needs to be erased ...
Zynq> sf probe
Zynq> sf erase 0 0x2000000
Zynq> reset

# Now it looks good:
Zynq> echo $bootcmd
run kernel_load; run dtr_load; setenv ethaddr 00:0a:35:00:01:87; run kernel_boot
```
## Linux kernel
The [vanilla mainline kernel](https://github.com/torvalds/linux) works perfectly fine on the zedboard for this application (see note below).
Here's instructions on how to apply two tiny patches to enable FPGA configuration from the command line and OLED support. If you go with the Xilinx version of the kernel, you don't need the two patches, but most of the instructions below still apply.

```bash
    git clone https://github.com/torvalds/linux.git
    cd linux/
    git checkout 22fbc037cd32e4e6771d2271b565806cfb8c134c

# Load my kernel config and device tree for zed_vvm
    cp <..>/zed_vvm/linux_kernel/zedboard_defconfig arch/arm/configs/
    cp <..>/zed_vvm/linux_kernel/zynq-zed.dts arch/arm/boot/dts/

# Patch to get /sys/class/fpga_mgr/fpga0/firmware
# Not needed with the xilinx version of the kernel
    patch --strip=1 --input=<..>/zed_vvm/linux_kernel/fpga-mgr.patch

# If you want to use the tiny ssd1306 based display on the zed-board,
# replace the kernel fbtft driver with a working version:
    cd drivers/staging
    rm -rf fbtft
    git clone https://github.com/yetifrisstlama/fbtft.git

# Apply any kernel customization you might need
    cd ../..
    export CROSS_COMPILE=arm-linux-gnueabi- ARCH=arm
    make zedboard_defconfig
    make menuconfig
    # make sure the display drivers are all enabled under
    # Device Drivers --> Staging drivers --> Support for small TFT LCD display modules
```

Then build the kernel and device-tree ...

```bash
    make -j4 uImage LOADADDR=0x00008000
    # good time to get a cup of coffee
    make zynq-zed.dtb
```

copy kernel image and device-tree to SD card

```bash
    cp arch/arm/boot/uImage /media/sdcard/
# for zedboard
    cp arch/arm/boot/dts/zynq-zed.dtb /media/sdcard
# for microzed
    cp arch/arm/boot/dts/zynq-microzed.dtb /media/sdcard
```

to configure u-boot, create a `uEnv.txt` as shown below and copy it to SD card.

SD card contents should look like this now:
```bash
ls -hl /media/<..>
total 5.6M
-rw-r--r-- 1 michael michael 117K Oct  3 19:42 boot.bin
-rw-r--r-- 1 michael michael 1.1M Oct  3 19:42 u-boot.img
-rw-r--r-- 1 michael michael  735 Oct  3 19:42 uEnv.txt
-rw-r--r-- 1 michael michael 4.4M Oct  3 19:43 uImage
-rw-r--r-- 1 michael michael  12K Oct  3 19:43 zynq-zed.dtb
```
Now is a good time to give it a test-run on the Zedboard,
the linux kernel should boot and panic because of the missing root filesystem

## Mainline kernel
Pros of going mainline
  * more widely adopted
  * hence better peer-reviewed

The Zynq7000 is pretty well supported now in the mainline kernel.

[Mainline vs. Xilinx Kernel](https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18841873/Linux+Drivers)

I started this project on the Xilinx kernel-fork. When I first tried switching over to mainline, I just copied `linux-xlnx/.config` to `linux/.config` and compiled as of the instructions above.

  * Both OLED displays, GPIOs and rotary encoder worked as expected
  * It booted without errors in dmesg
  * `/sys/class/fpga_manager/fpga0` was there, so the linux FPGA manager driver was working

However I was missing `/sys/class/fpga_manager/fpga0/firmware`,
which is used to pipe the name of a `.bit.bin` file to re-program the FPGA PL from linux. After some investigation, it looks like the fpga-manager was not intended to be accessed from user-space and Xilinx added this feature as a convenience for developers. I brought it back with a [tiny patch](fpga-mgr.patch) to the mainline kernel.

With the patch I was able to load bit-files in the same way as with the
 Xilinx kernel. However the fabric clocks were still disabled and the FPGA
 appeared completely un-responsive after configuration.
 Some intensive diff-ing later I could trace this down to different default settings in `zynq-7000.dtsi`.
 Switching the clocks back on was easily done in [`zynq-zed.dts`](zynq-zed.dts)
 and life on mainline is good now.

## Debian buster rootfs

### Shortcut: install pre-made rootfs
This assumes `/dev/mmcblk0p2` is the large ext4 partition on the SD card/.
```bash
    wget https://github.com/yetifrisstlama/zed_vvm/releases/download/v0.1/rootfs_buster_clean.tar.gz
    sudo mkfs.ext4 -v /dev/mmcblk0p2 -L rootfs
    # Mount the partition (easiest in gui file manger)
    cd /media/<..>/rootfs
    sudo tar -xzvf <..>/rootfs_buster_clean.tar.gz
```

Put the SD-card in the zedboard, connect to its UART and
watch it booting into debian. There should be a login prompt on the UART.

__If you've downloaded `rootfs_buster_clean.tar.gz` change the passwords !!!__
login as each of the two users below and run the `passwd` command.

```bash
    #user: root, default pw: root
    #user: zed, default pw: zed
```

Also remote login over ssh should work now if the network is up.

The last step (if ssh works) is to copy the `linux_apps` directory
form the host machine onto the zedboard:

```bash
    scp -r <..>/zed_vvm/linux_apps <user_name>@<hostname>:~
```

Alternatively, just install my [litex-fork](https://github.com/yetifrisstlama/litex) on the zedboard, which includes
litex_server with mmap access support.

### Taking the scenic route ...
setup your initial bare-bones debian environment using chroot on a debian based linux host PC.

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
    nano /etc/apt/sources.list

deb http://deb.debian.org/debian buster main
deb http://deb.debian.org/debian-security/ buster/updates main
deb http://deb.debian.org/debian buster-updates main

    apt update
    apt upgrade
    apt install locales sudo ntp openssh-server python3

    # Enable `en_US.UTF-8` and set it as default locale
    dpkg-reconfigure locales

    # Set root password
    passwd

    # Add a user with sudo permissions
    adduser <user_name>
    visudo

root        ALL=(ALL:ALL) ALL
<user_name> ALL=(ALL:ALL) NOPASSWD: ALL
# Note: the `NOPASSWD: ` flag means sudo will not ask for a password.
# convenient for development but dangerous. Don't do this in production!

    # Enable DHCP
    nano /etc/network/interfaces

allow-hotplug eth0
iface eth0 inet dhcp

    # Set hostname
    nano /etc/hostname

<hostname>

    nano /etc/hosts

127.0.0.1   localhost <hostname>
::1     localhost ip6-localhost ip6-loopback
ff02::1     ip6-allnodes
ff02::2     ip6-allrouters

# Mount the fat16 boot partition
# This is useful for remote updates of
#   * first stage boot-loader (boot.bin)
#   * u-boot.img
#   * device tree (.dts)
#   * kernel image (uImage)
#   * u-boot config (uEnv.txt)
    mkdir /boot  # only if it does not exist already
    nano /etc/fstab

/dev/mmcblk0p1 /boot auto defaults 0 0

# For remote fpga loading
    mkdir /lib/firmware

# Optional Hacks
# get cross-compiled binaries to run
# otherwise I get `bash: ./hw: No such file or directory`
    sudo ln -s /lib/arm-linux-gnueabihf/ld-2.28.so /lib/ld-linux.so.3

# to prevent sshd taking forever to start after reboot and
# `random: 7 urandom warning(s) missed due to ratelimiting`
    sudo apt install haveged

# ------------------------
#  Exit the chroot shell
# ------------------------

# Archive rootfs in a .tar.gz file
    cd rootfs
    sudo tar -cpzvf ../rootfs_buster_clean.tar.gz .
```

Un-tar the rootfs onto a large ext4 partition on the SD card as shown [here](ZED_DEBIAN.md#shortcut-install-pre-made-rootfs).

## Partitioning the SD card
What we need

  * FAT16 partition of size 32 MB
  * Linux (ext4) over the remaining available space

Using `fdisk` on a 2 GB SD card, it should look like this:

```
Device         Boot Start     End Sectors  Size Id Type
/dev/mmcblk0p1       2048   67583   65536   32M  e W95 FAT16
/dev/mmcblk0p2      67584 3842047 3774464  1.8G 83 Linux
```

then format the partitions as FAT16 and ext4

```bash
sudo mkfs.vfat -F16 -v /dev/mmcblk0p1 -n boot
sudo mkfs.ext4 -v /dev/mmcblk0p2 -L rootfs
```

__make sure to replace `mmcblk0p1` and `mmcblk0p2` with the actual partition names__

# uEnv.txt
U-Boot startup script to boot and optionally load a bitfile. Make sure `ethaddr` is unique on network.
```bash
fpga_addr=0x10000000
fpga_load=load mmc 0 ${fpga_addr} zed_wrapper.bit.bin
fpga_boot=fpga load 0 ${fpga_addr} $filesize

kernel_addr=0x8000
kernel_load=load mmc 0 ${kernel_addr} uImage

dtr_addr=0x100
dtr_load=load mmc 0 ${dtr_addr} zynq-zed.dtb

kernel_boot=setenv bootargs console=ttyPS0,115200 root=/dev/mmcblk0p2 rw rootwait; bootm ${kernel_addr} - ${dtr_addr}

# Boot from MMC without loading a bit-file, make sure to change ethaddr to a random value
bootcmd=run kernel_load; run dtr_load; setenv ethaddr 00:0a:35:00:42:87; run kernel_boot

# Load a bit-file and boot from MMC, make sure .bit.bin file from line 2 exists
# bootcmd=run fpga_load; run fpga_boot; run kernel_load; run dtr_load; setenv ethaddr 00:0a:35:00:42:87; run kernel_boot

# network boot: load uImage and zynq-zed.dtb over tftp and boot it
# ipaddr=192.168.1.2
# serverip=192.168.1.1
# netmask=255.255.255.0
# bootcmd=tftpboot $kernel_addr uImage; tftpboot $dtr_addr zynq-zed.dtb; run kernel_boot
```
