#!/bin/bash
# Remotely starts up the litex server with shared memory access,
# then it tunnels the etherbone port 1234 over ssh
# needs the files from `util/litex_server` installed on zedboard
# HOSTNAME=spaetzle.dhcp.lbl.gov
HOSTNAME=128.3.131.28
ssh -L 1234:localhost:1234 $HOSTNAME "sudo systemctl stop vvmd; cd litex_server_light; sudo python3 litex_server.py --devmem --devmem-offset 0x40000000"
