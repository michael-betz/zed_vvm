# This is the place for the Zynq PS configuration
# To customize:
#   * run this with `make ip/processing_system7_0.xci` from the project root
#   * open project: `vivado zed_ps7.xpr`
#   * open `processing_system7_0` in the project manager
#   * customize Peripheral I/O Pins / Fabric clocks / etc, OK
#   * Generate Output Products: Skip
#   * File, Project, Open Journal File
#   * Copy the lines with `set_proerty` and insert them here before quit
create_project zed_ps7 . -part xc7z020clg484-1
set_property board_part em.avnet.com:zed:part0:1.4 [current_project]
create_ip -name processing_system7 -vendor xilinx.com -library ip -version 5.5 -module_name processing_system7_0
set_property -dict [list CONFIG.preset {ZedBoard}] [get_ips processing_system7_0]

# SPI0: EMIO, SPI1: MIO 10 .. 15, 32 EMIO GPIO pins
set_property -dict [list CONFIG.PCW_QSPI_GRP_SINGLE_SS_ENABLE {1} CONFIG.PCW_SPI0_PERIPHERAL_ENABLE {1} CONFIG.PCW_SPI1_PERIPHERAL_ENABLE {1} CONFIG.PCW_SPI1_SPI1_IO {MIO 10 .. 15} CONFIG.PCW_GPIO_EMIO_GPIO_ENABLE {1} CONFIG.PCW_GPIO_EMIO_GPIO_IO {32}] [get_ips processing_system7_0]

quit
