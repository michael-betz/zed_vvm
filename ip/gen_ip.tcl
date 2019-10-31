# This is the place for the Zynq PS configuration
create_project zed_ps7 . -part xc7z020clg484-1
set_property board_part em.avnet.com:zed:part0:1.4 [current_project]
create_ip -name processing_system7 -vendor xilinx.com -library ip -version 5.5 -module_name processing_system7_0
set_property -dict [list CONFIG.preset {ZedBoard}] [get_ips processing_system7_0]
set_property -dict [list CONFIG.PCW_QSPI_GRP_SINGLE_SS_ENABLE {1} CONFIG.PCW_SPI1_PERIPHERAL_ENABLE {1}] [get_ips processing_system7_0]
quit
