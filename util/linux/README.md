# linux

__.config__ my current linux kernel configuration file for `make menuconfig`.
Copy / link it to `linux/.config`.

__zynq-zed.dts__ my current device tree.
Copy / link it to `linux/arch/arm/boot/dts/zynq-zed.dts`.

__fpga-mgr.patch__ Patch for the linux mainline kernel to get the /sys/class/fpga_mgr/fpga0/firmware file which is needed to easily configure the fpga from linux. The xilinx version of the kernel has this little convenience feature already builtin.

All the other stuff are applications which are supposed to run on the zedboard.
